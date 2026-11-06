import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.integrations.ai_provider import AIProviderError, build_ai_provider
from app.models.application import Application
from app.schemas.application import ApplicationRead, DecisionUpdate, ReviewStatusUpdate
from app.schemas.evaluation import EvaluationRead
from app.services import ai_evaluation
from app.services import applications as applications_service

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _get_application_or_404(db: Session, application_id: uuid.UUID) -> Application:
    application = applications_service.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.post(
    "/{application_id}/evaluations",
    response_model=EvaluationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EvaluationRead:
    application = _get_application_or_404(db, application_id)
    job = application.job
    requirements = job.requirements

    if not requirements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job has no confirmed requirements to evaluate against yet.",
        )

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
        provider.MODEL_VERSION
        if hasattr(provider, "MODEL_VERSION")
        else settings.openai_model
    )

    try:
        evaluation = ai_evaluation.run_ai_evaluation(
            db, application, job, requirements, provider, model_version
        )
    except ai_evaluation.NoExtractedTextError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This resume has no extracted text available to evaluate.",
        ) from error

    return EvaluationRead.from_evaluation(evaluation)


@router.get("/{application_id}/evaluations", response_model=list[EvaluationRead])
def list_evaluations(
    application_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[EvaluationRead]:
    _get_application_or_404(db, application_id)
    evaluations = applications_service.list_evaluations(db, application_id)
    return [EvaluationRead.from_evaluation(e) for e in evaluations]


@router.patch("/{application_id}/review-status", response_model=ApplicationRead)
def update_review_status(
    application_id: uuid.UUID, data: ReviewStatusUpdate, db: Session = Depends(get_db)
) -> Application:
    application = _get_application_or_404(db, application_id)
    return applications_service.update_review_status(db, application, data.review_status)


@router.patch("/{application_id}/decision", response_model=ApplicationRead)
def update_decision(
    application_id: uuid.UUID, data: DecisionUpdate, db: Session = Depends(get_db)
) -> Application:
    application = _get_application_or_404(db, application_id)
    return applications_service.update_decision(db, application, data.decision)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    application = _get_application_or_404(db, application_id)
    applications_service.delete_application(db, application)
