import uuid
from decimal import Decimal
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.integrations.ai_prompt import RequirementInferenceRequest
from app.integrations.ai_provider import (
    AICreditsExhaustedError,
    AIProviderError,
    build_ai_provider,
)
from app.models.enums import RequirementResultStatus, ReviewStatus
from app.models.job import Job
from app.models.upload_batch import UploadBatch
from app.schemas.candidate import CandidatePoolResponse
from app.schemas.job import (
    JobCreate,
    JobRead,
    JobRequirementRead,
    JobRequirementsCreate,
    JobSummary,
    RequirementSuggestionRead,
)
from app.schemas.upload import UploadBatchRead
from app.services import candidates as candidates_service
from app.services import evaluation, resume_upload
from app.services import jobs as jobs_service
from app.services.candidates import CandidatePoolFilters

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _get_job_or_404(db: Session, job_id: uuid.UUID) -> Job:
    job = jobs_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(data: JobCreate, db: Session = Depends(get_db)) -> Job:
    job = jobs_service.create_job(db, data)
    db.commit()
    return job


@router.get("", response_model=list[JobSummary])
def list_jobs(db: Session = Depends(get_db)) -> list[JobSummary]:
    return jobs_service.list_jobs(db)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Job:
    return _get_job_or_404(db, job_id)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    job = _get_job_or_404(db, job_id)
    jobs_service.delete_job(db, job)
    db.commit()


@router.post(
    "/{job_id}/requirements",
    response_model=list[JobRequirementRead],
    status_code=status.HTTP_201_CREATED,
)
def create_requirements(
    job_id: uuid.UUID, data: JobRequirementsCreate, db: Session = Depends(get_db)
) -> list[JobRequirementRead]:
    job = _get_job_or_404(db, job_id)
    try:
        requirements = jobs_service.create_requirements(db, job, data.requirements)
    except jobs_service.RequirementsAlreadySetError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job's requirements have already been confirmed and cannot be replaced.",
        ) from error
    db.commit()
    evaluation.backfill_preliminary_evaluations(db, job, requirements)
    return requirements


def _build_provider_or_503(settings: Settings) -> tuple[object, str]:
    try:
        provider = build_ai_provider(
            provider_name=settings.ai_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
    except AIProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    model_version = (
        provider.MODEL_VERSION if hasattr(provider, "MODEL_VERSION") else settings.openai_model
    )
    return provider, model_version


@router.put("/{job_id}/requirements", response_model=list[JobRequirementRead])
def edit_requirements(
    job_id: uuid.UUID,
    data: JobRequirementsCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[JobRequirementRead]:
    """Replace an already-confirmed rubric and fully redo evaluation — both
    stages, every candidate — against it in this same request, rather than
    leaving the AI stage to a client-side queue that stops if the browser
    tab isn't left open on this page.
    """
    job = _get_job_or_404(db, job_id)
    provider, model_version = _build_provider_or_503(settings)
    try:
        requirements = jobs_service.edit_requirements(
            db, job, data.requirements, provider, model_version
        )
    except jobs_service.NoRequirementsToEditError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This job has no confirmed requirements yet — confirm some first.",
        ) from error
    db.commit()
    return requirements


@router.post("/{job_id}/evaluations/rerun", status_code=status.HTTP_204_NO_CONTENT)
def rerun_evaluations(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Wipe every evaluation for this job (same rubric) and fully redo
    evaluation — both stages, every candidate — against the current job
    description, requirements, and resumes, all within this one request.
    """
    job = _get_job_or_404(db, job_id)
    if not job.requirements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job has no confirmed requirements to evaluate against yet.",
        )
    provider, model_version = _build_provider_or_503(settings)
    jobs_service.rerun_all_evaluations(db, job, provider, model_version)
    db.commit()


@router.get("/{job_id}/requirements", response_model=list[JobRequirementRead])
def list_requirements(job_id: uuid.UUID, db: Session = Depends(get_db)) -> list[JobRequirementRead]:
    _get_job_or_404(db, job_id)
    return jobs_service.list_requirements(db, job_id)


@router.post("/{job_id}/requirements/infer", response_model=list[RequirementSuggestionRead])
def infer_requirements(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[RequirementSuggestionRead]:
    """Propose a draft rubric from the job's title and description — a
    starting point the hiring manager reviews and edits, never persisted
    directly. Confirming still goes through POST .../requirements as usual.
    """
    job = _get_job_or_404(db, job_id)
    if job.requirements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job's requirements have already been confirmed.",
        )

    try:
        provider = build_ai_provider(
            provider_name=settings.ai_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
        suggestions = provider.infer_requirements(
            RequirementInferenceRequest(
                job_title=job.title, description_md=job.description_md
            )
        )
    except AICreditsExhaustedError as error:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(error)
        ) from error
    except AIProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    return [
        RequirementSuggestionRead(
            description=s.description, category=s.category, weight=Decimal(str(s.weight))
        )
        for s in suggestions
    ]


@router.post(
    "/{job_id}/resumes",
    response_model=UploadBatchRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_resumes(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadBatchRead:
    """Accepts the upload and hands the actual processing (validation,
    storage, extraction, preliminary evaluation — one DB round trip per
    file) to a background task, returning as soon as the batch exists.

    Extraction and validation for a large batch can take well past a
    reasonable request timeout; the batch starts in "processing" with
    empty results, and the client polls GET .../batches/{batch_id} (same
    response shape) until its status is no longer "processing".
    """
    job = _get_job_or_404(db, job_id)

    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No files provided"
        )
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Too many files — at most {settings.max_files_per_upload} per upload",
        )

    # Reading the upload bodies still has to happen on this request — once
    # the response is sent, FastAPI tears down the UploadFile objects along
    # with everything else request-scoped.
    file_contents = [(file.filename or "unnamed", await file.read()) for file in files]

    batch = resume_upload.create_batch(db, job, total_count=len(files))
    background_tasks.add_task(
        resume_upload.run_upload_batch_in_background, job.id, batch.id, file_contents, settings
    )

    return UploadBatchRead.model_validate(batch)


@router.get("/{job_id}/batches/{batch_id}", response_model=UploadBatchRead)
def get_batch(job_id: uuid.UUID, batch_id: uuid.UUID, db: Session = Depends(get_db)) -> UploadBatch:
    _get_job_or_404(db, job_id)
    batch = resume_upload.get_batch(db, job_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload batch not found")
    return batch


@router.get("/{job_id}/candidates", response_model=CandidatePoolResponse)
def list_candidates(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: Literal["score", "created_at", "display_name"] = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    search: str | None = Query(None, max_length=200),
    min_score: Decimal | None = Query(None, ge=0, le=100),
    requirement_status: RequirementResultStatus | None = Query(None),
    review_status: ReviewStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> CandidatePoolResponse:
    _get_job_or_404(db, job_id)
    filters = CandidatePoolFilters(
        search=search,
        min_score=min_score,
        requirement_status=requirement_status,
        review_status=review_status,
    )
    return candidates_service.list_candidate_pool(
        db,
        job_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filters=filters,
    )
