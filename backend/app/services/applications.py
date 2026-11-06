import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application
from app.models.enums import CandidateDecision, ReviewStatus
from app.models.evaluation import Evaluation, RequirementResult
from app.models.job import Job


def get_application(db: Session, application_id: uuid.UUID) -> Application | None:
    statement = (
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.job).selectinload(Job.requirements),
            selectinload(Application.resume),
        )
    )
    return db.execute(statement).scalar_one_or_none()


def list_evaluations(db: Session, application_id: uuid.UUID) -> list[Evaluation]:
    statement = (
        select(Evaluation)
        .where(Evaluation.application_id == application_id)
        .options(
            selectinload(Evaluation.requirement_results).selectinload(
                RequirementResult.requirement
            )
        )
        .order_by(Evaluation.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def update_review_status(
    db: Session, application: Application, review_status: ReviewStatus
) -> Application:
    """Set the hiring manager's own review status for an application.

    Deliberately independent of evaluation state — a reviewer can mark a
    candidate reviewed regardless of whether an AI evaluation has run, and
    running an AI evaluation never changes this field. The AI assesses
    evidence; only a human decides review status.
    """
    application.review_status = review_status
    db.commit()
    return application


def update_decision(
    db: Session, application: Application, decision: CandidateDecision | None
) -> Application:
    """Record (or clear) a human's hiring-pipeline decision for an
    application. This is never set by AI evaluation — only a person clicking
    Advance/Hold/Decline in the UI sets it, and passing None clears it back
    to "no decision yet".
    """
    application.decision = decision
    db.commit()
    return application


def delete_application(db: Session, application: Application) -> None:
    """Remove one candidate's submission from this job's pipeline.

    Only the application and its own evaluations are deleted. The resume
    and candidate rows are deliberately left alone — the same resume can
    be deduplicated across multiple jobs' applications (see
    resume_upload.py), so deleting them here could break a different job's
    data. An orphaned resume file left on disk is harmless; deleting one
    still referenced elsewhere would not be.
    """
    db.execute(delete(Evaluation).where(Evaluation.application_id == application.id))
    db.delete(application)
    db.commit()
