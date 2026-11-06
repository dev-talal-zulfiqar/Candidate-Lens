import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import open_background_session
from app.integrations.ai_provider import AIProvider
from app.models.application import Application
from app.models.enums import ExtractionStatus
from app.models.evaluation import Evaluation
from app.models.job import Job, JobRequirement
from app.models.upload_batch import UploadBatch
from app.schemas.job import JobCreate, JobRequirementCreate, JobSummary
from app.services import ai_evaluation
from app.services.evaluation import backfill_preliminary_evaluations

logger = logging.getLogger(__name__)


class RequirementsAlreadySetError(Exception):
    """Raised when requirements are submitted for a job that already has
    some — use edit_requirements to replace a confirmed rubric instead.
    """


class NoRequirementsToEditError(Exception):
    """Raised when editing is attempted on a job with no confirmed
    requirements yet — there's nothing to replace; use create_requirements
    for the first confirmation.
    """


def create_job(db: Session, data: JobCreate) -> Job:
    job = Job(title=data.title, description_md=data.description_md)
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: uuid.UUID) -> Job | None:
    statement = (
        select(Job).where(Job.id == job_id).options(selectinload(Job.requirements))
    )
    return db.execute(statement).scalar_one_or_none()


def list_jobs(db: Session) -> list[JobSummary]:
    requirement_counts = (
        select(
            JobRequirement.job_id,
            func.count(JobRequirement.id).label("requirement_count"),
        )
        .group_by(JobRequirement.job_id)
        .subquery()
    )
    statement = (
        select(Job, func.coalesce(requirement_counts.c.requirement_count, 0))
        .outerjoin(requirement_counts, requirement_counts.c.job_id == Job.id)
        .order_by(Job.created_at.desc())
    )
    return [
        JobSummary(
            id=job.id,
            title=job.title,
            rubric_version=job.rubric_version,
            created_at=job.created_at,
            requirement_count=requirement_count,
        )
        for job, requirement_count in db.execute(statement).all()
    ]


def create_requirements(
    db: Session, job: Job, requirements: list[JobRequirementCreate]
) -> list[JobRequirement]:
    existing_count = db.scalar(
        select(func.count(JobRequirement.id)).where(JobRequirement.job_id == job.id)
    )
    if existing_count:
        raise RequirementsAlreadySetError(job.id)

    rows = [
        JobRequirement(
            job_id=job.id,
            description=requirement.description,
            category=requirement.category,
            weight=requirement.weight,
            sort_order=requirement.sort_order if requirement.sort_order is not None else index,
        )
        for index, requirement in enumerate(requirements)
    ]
    db.add_all(rows)
    db.flush()
    rows.sort(key=lambda r: r.sort_order)
    return rows


def list_requirements(db: Session, job_id: uuid.UUID) -> list[JobRequirement]:
    statement = (
        select(JobRequirement)
        .where(JobRequirement.job_id == job_id)
        .order_by(JobRequirement.sort_order)
    )
    return list(db.execute(statement).scalars().all())


def wipe_evaluations_for_job(db: Session, job_id: uuid.UUID) -> None:
    """Delete every evaluation (preliminary + AI, both stages) for every
    application under a job. requirement_results cascade automatically via
    their FK's ON DELETE CASCADE. Used whenever a job's evaluation history
    needs to be treated as invalid: editing requirements (the old scores no
    longer match the new rubric) and the explicit "re-run" action.
    """
    application_ids = select(Application.id).where(Application.job_id == job_id)
    db.execute(delete(Evaluation).where(Evaluation.application_id.in_(application_ids)))
    db.flush()


def run_ai_evaluations_for_job(
    db: Session,
    job: Job,
    requirements: list[JobRequirement],
    provider: AIProvider,
    model_version: str,
) -> list[uuid.UUID]:
    """Run the AI evaluation stage for every application under a job that
    has readable resume text. Per-application provider failures (including
    AICreditsExhaustedError) are swallowed by run_ai_evaluation itself —
    it stores them as a "failed" Evaluation row rather than raising — so
    one bad call never aborts the rest of the batch.

    run_ai_evaluation commits each application's result as soon as it
    completes, so earlier applications in this loop are already durable by
    the time a later one runs. An *unexpected* exception (anything beyond
    the two handled cases above) must therefore never be allowed to
    propagate out of this loop: doing so would abort the request with a
    500 while earlier applications' commits — and, when called from
    edit_requirements, the rubric edit itself — remain persisted, leaving
    the client believing the whole operation failed when it partially (or
    mostly) succeeded. Instead, roll back just the broken application's
    partial work, log it, and keep going. Returns the ids of applications
    that failed unexpectedly, so callers can surface that distinctly from
    an ordinary AI-provider failure if useful.
    """
    applications = (
        db.execute(
            select(Application)
            .where(Application.job_id == job.id)
            .options(selectinload(Application.resume))
        )
        .scalars()
        .all()
    )
    unexpected_failures: list[uuid.UUID] = []
    for application in applications:
        if application.resume.extraction_status != ExtractionStatus.COMPLETED:
            continue
        try:
            ai_evaluation.run_ai_evaluation(
                db, application, job, requirements, provider, model_version
            )
        except ai_evaluation.NoExtractedTextError:
            continue
        except Exception:
            db.rollback()
            logger.exception(
                "ai_evaluation_unexpected_failure application_id=%s job_id=%s",
                application.id,
                job.id,
            )
            unexpected_failures.append(application.id)
    return unexpected_failures


def run_ai_evaluations_for_job_in_background(
    job_id: uuid.UUID, provider: AIProvider, model_version: str
) -> None:
    """Background-task entry point for the AI evaluation stage, scheduled
    by edit_requirements/rerun_all_evaluations' callers after the
    triggering request has already returned.

    A full AI re-evaluation run against every candidate in a pipeline —
    potentially hundreds of real, rate-limited provider calls — was
    previously a single synchronous loop inside the request, the same
    scaling problem resume upload had before it was backgrounded. The
    requirements/rubric change and the preliminary (keyword) re-match stay
    synchronous (they're fast, no external calls); only the AI stage,
    the genuinely slow and expensive part, moves off the request thread.

    AIProvider instances are plain stateless objects (an API key + HTTP
    client, no DB session bound to them), so the one already built for the
    triggering request can be reused here directly — no need to rebuild it
    with a fresh session the way the job/requirements do.
    """
    with open_background_session() as db:
        job = db.execute(
            select(Job).where(Job.id == job_id).options(selectinload(Job.requirements))
        ).scalar_one_or_none()
        if job is None:
            logger.error("ai_evaluation_background_missing_job job_id=%s", job_id)
            return
        unexpected_failures = run_ai_evaluations_for_job(
            db, job, job.requirements, provider, model_version
        )
        if unexpected_failures:
            logger.warning(
                "background_ai_evaluation_partial_failure job_id=%s failed_application_ids=%s",
                job_id,
                unexpected_failures,
            )


def edit_requirements(
    db: Session, job: Job, requirements: list[JobRequirementCreate]
) -> list[JobRequirement]:
    """Replace a job's confirmed requirements with a new set, wipe every
    evaluation scored against the old rubric (they no longer match), and
    redo the preliminary (keyword) stage immediately. The AI stage is
    scheduled separately by the caller as a background task — see
    run_ai_evaluations_for_job_in_background.
    """
    existing_count = db.scalar(
        select(func.count(JobRequirement.id)).where(JobRequirement.job_id == job.id)
    )
    if not existing_count:
        raise NoRequirementsToEditError(job.id)

    wipe_evaluations_for_job(db, job.id)
    db.execute(delete(JobRequirement).where(JobRequirement.job_id == job.id))

    rows = [
        JobRequirement(
            job_id=job.id,
            description=requirement.description,
            category=requirement.category,
            weight=requirement.weight,
            sort_order=requirement.sort_order if requirement.sort_order is not None else index,
        )
        for index, requirement in enumerate(requirements)
    ]
    db.add_all(rows)
    job.rubric_version += 1
    db.flush()
    rows.sort(key=lambda r: r.sort_order)

    # Commit the rubric replacement on its own, before touching evaluations.
    # Otherwise its durability would depend on an implicit side effect of
    # the first application's internal commit inside run_ai_evaluation —
    # if that never runs (e.g. zero applications) or an early one fails
    # unexpectedly, the edit's fate would be entangled with evaluation
    # outcomes it has nothing to do with (QA-004).
    db.commit()

    backfill_preliminary_evaluations(db, job, rows)
    return rows


def rerun_all_evaluations(db: Session, job: Job) -> None:
    """Wipe every evaluation for this job (same rubric — no requirement
    changes) and redo the preliminary (keyword) stage immediately. The AI
    stage is scheduled separately by the caller as a background task — see
    run_ai_evaluations_for_job_in_background.
    """
    wipe_evaluations_for_job(db, job.id)
    db.commit()

    backfill_preliminary_evaluations(db, job, job.requirements)


def delete_job(db: Session, job: Job) -> None:
    """Delete a job and everything that exists only for it — applications,
    their evaluations, upload batches, and requirements.

    Resumes and candidates are deliberately NOT deleted: the same resume
    can be deduplicated across multiple jobs (see resume_upload.py), so
    deleting them here could break a different job's data. An orphaned
    resume file left on disk is harmless; deleting one still referenced by
    another job would not be.
    """
    application_ids = select(Application.id).where(Application.job_id == job.id)
    db.execute(delete(Evaluation).where(Evaluation.application_id.in_(application_ids)))
    db.execute(delete(Application).where(Application.job_id == job.id))
    db.execute(delete(UploadBatch).where(UploadBatch.job_id == job.id))
    db.execute(delete(JobRequirement).where(JobRequirement.job_id == job.id))
    db.delete(job)
    db.flush()
