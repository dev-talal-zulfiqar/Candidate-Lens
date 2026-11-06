import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application
from app.models.enums import EvaluationStage, EvaluationStatus, ExtractionStatus
from app.models.evaluation import Evaluation, RequirementResult
from app.models.job import Job, JobRequirement
from app.services.evaluation_cache import compute_input_hash
from app.services.preliminary_matching import match_requirement
from app.services.scoring import ScoredRequirement, compute_preliminary_score

logger = logging.getLogger(__name__)


def _find_by_input_hash(
    db: Session, application_id: uuid.UUID, input_hash: str
) -> Evaluation | None:
    return db.execute(
        select(Evaluation).where(
            Evaluation.application_id == application_id,
            Evaluation.stage == EvaluationStage.PRELIMINARY,
            Evaluation.input_hash == input_hash,
        )
    ).scalar_one_or_none()


def run_preliminary_evaluation(
    db: Session, application: Application, job: Job, requirements: list[JobRequirement]
) -> Evaluation | None:
    """Run deterministic preliminary matching for one application.

    Returns None (and does nothing) if an evaluation for this exact resume
    content + rubric version already exists, or if there are no confirmed
    requirements yet to evaluate against.
    """
    if not requirements:
        return None

    resume = application.resume
    input_hash = compute_input_hash(
        resume_file_hash=resume.file_hash,
        rubric_version=job.rubric_version,
        stage="preliminary",
    )
    if _find_by_input_hash(db, application.id, input_hash) is not None:
        return None

    evaluation = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.PRELIMINARY,
        status=EvaluationStatus.RUNNING,
        input_hash=input_hash,
    )
    db.add(evaluation)
    try:
        db.flush()
    except IntegrityError:
        # Resume upload and requirement confirmation can both trigger this
        # for the same application; the unique constraint on
        # (application_id, stage, input_hash) is what actually prevents a
        # duplicate when both land close enough together to both pass the
        # check above.
        db.rollback()
        return None

    if resume.extraction_status != ExtractionStatus.COMPLETED or not resume.extracted_text:
        evaluation.status = EvaluationStatus.FAILED
        evaluation.error_message = "No extracted resume text available for matching."
        evaluation.completed_at = datetime.now(UTC)
        db.commit()
        return evaluation

    scored: list[ScoredRequirement] = []
    for requirement in requirements:
        match = match_requirement(requirement.description, resume.extracted_text)
        db.add(
            RequirementResult(
                evaluation_id=evaluation.id,
                requirement_id=requirement.id,
                status=match.status,
                evidence_json=[{"term": m.term, "quote": m.quote} for m in match.matches],
                explanation=match.explanation,
            )
        )
        scored.append(ScoredRequirement(requirement=requirement, status=match.status))

    score, coverage_score = compute_preliminary_score(scored)
    evaluation.score = score
    evaluation.coverage_score = coverage_score
    evaluation.status = EvaluationStatus.COMPLETED
    evaluation.completed_at = datetime.now(UTC)
    db.commit()
    return evaluation


def backfill_preliminary_evaluations(
    db: Session, job: Job, requirements: list[JobRequirement]
) -> list[uuid.UUID]:
    """Evaluate any applications uploaded before this job's requirements were
    confirmed. Resume upload and requirement confirmation can happen in
    either order in the UI, so both paths trigger evaluation; the idempotency
    guard in `run_preliminary_evaluation` keeps this from double-running.

    Each application commits its own evaluation as soon as it completes, so
    (as with run_ai_evaluations_for_job) an unexpected exception partway
    through must not be allowed to abort the whole loop — earlier
    applications are already durable by then. Roll back just the broken
    one, log it, and keep going; return the ids that failed unexpectedly.
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
        try:
            run_preliminary_evaluation(db, application, job, requirements)
        except Exception:
            db.rollback()
            logger.exception(
                "preliminary_evaluation_unexpected_failure application_id=%s job_id=%s",
                application.id,
                job.id,
            )
            unexpected_failures.append(application.id)
    return unexpected_failures
