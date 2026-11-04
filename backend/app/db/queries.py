import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EvaluationStage, EvaluationStatus
from app.models.evaluation import Evaluation


def get_current_evaluation(
    db: Session, application_id: uuid.UUID, stage: EvaluationStage
) -> Evaluation | None:
    """Return the most recent completed evaluation for an application and stage.

    Evaluations are append-only processing attempts (retries, re-runs after a
    rubric change, etc.), so "current" is not simply the latest row — it is
    the latest row that actually completed successfully.
    """
    statement = (
        select(Evaluation)
        .where(
            Evaluation.application_id == application_id,
            Evaluation.stage == stage,
            Evaluation.status == EvaluationStatus.COMPLETED,
        )
        .order_by(Evaluation.completed_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()
