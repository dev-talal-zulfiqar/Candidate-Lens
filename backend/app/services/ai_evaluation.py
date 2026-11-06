import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.integrations.ai_prompt import PROMPT_VERSION, AIEvaluationRequest, RequirementPromptItem
from app.integrations.ai_provider import AIProvider, AIProviderError
from app.integrations.evidence_verification import verify_evidence
from app.models.application import Application
from app.models.enums import (
    EvaluationStage,
    EvaluationStatus,
    ExtractionStatus,
    RequirementResultStatus,
)
from app.models.evaluation import Evaluation, RequirementResult
from app.models.job import Job, JobRequirement
from app.services.evaluation_cache import compute_input_hash
from app.services.scoring import ScoredRequirement, compute_ai_score

logger = logging.getLogger(__name__)


class NoExtractedTextError(Exception):
    """Raised when an application's resume has no usable extracted text."""


def get_cached_evaluation(
    db: Session, application_id: uuid.UUID, input_hash: str
) -> Evaluation | None:
    return _find_by_input_hash(
        db, application_id, input_hash, status=EvaluationStatus.COMPLETED
    )


def _find_by_input_hash(
    db: Session,
    application_id: uuid.UUID,
    input_hash: str,
    *,
    status: EvaluationStatus | None = None,
) -> Evaluation | None:
    conditions = [
        Evaluation.application_id == application_id,
        Evaluation.stage == EvaluationStage.AI,
        Evaluation.input_hash == input_hash,
    ]
    if status is not None:
        conditions.append(Evaluation.status == status)
    return db.execute(
        select(Evaluation)
        .where(*conditions)
        .options(
            selectinload(Evaluation.requirement_results).selectinload(
                RequirementResult.requirement
            )
        )
    ).scalar_one_or_none()


def run_ai_evaluation(
    db: Session,
    application: Application,
    job: Job,
    requirements: list[JobRequirement],
    provider: AIProvider,
    model_version: str,
) -> Evaluation:
    """Run a deep AI evaluation for one application, reusing a cached result
    when the resume, rubric, model, prompt, and scoring formula are all
    unchanged from a prior completed run.
    """
    resume = application.resume
    if resume.extraction_status != ExtractionStatus.COMPLETED or not resume.extracted_text:
        raise NoExtractedTextError(application.id)

    input_hash = compute_input_hash(
        resume_file_hash=resume.file_hash,
        rubric_version=job.rubric_version,
        stage="ai",
        model_version=model_version,
        prompt_version=PROMPT_VERSION,
    )
    cached = get_cached_evaluation(db, application.id, input_hash)
    if cached is not None:
        return cached

    evaluation = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.AI,
        status=EvaluationStatus.RUNNING,
        model_version=model_version,
        prompt_version=PROMPT_VERSION,
        input_hash=input_hash,
    )
    db.add(evaluation)
    try:
        db.flush()
    except IntegrityError:
        # Lost a race against a near-simultaneous trigger for the exact same
        # application/stage/inputs — the unique constraint caught it before
        # we spent anything calling the AI provider. Use whatever the winner
        # inserted instead of erroring.
        db.rollback()
        existing = _find_by_input_hash(db, application.id, input_hash)
        if existing is not None:
            return existing
        raise

    prompt_items = [
        RequirementPromptItem(key=f"R{i + 1}", description=r.description, category=r.category.value)
        for i, r in enumerate(requirements)
    ]
    request = AIEvaluationRequest(
        job_title=job.title, requirements=prompt_items, resume_text=resume.extracted_text
    )

    try:
        result = provider.evaluate(request)
    except AIProviderError as error:
        evaluation.status = EvaluationStatus.FAILED
        evaluation.error_message = str(error)
        evaluation.completed_at = datetime.now(UTC)
        db.commit()
        return evaluation

    logger.info(
        "ai_evaluation_completed model=%s duration_ms=%d input_tokens=%s output_tokens=%s "
        "cached_input_tokens=%s",
        result.model_version,
        result.duration_ms,
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.cached_input_tokens,
    )

    verified = verify_evidence(result.response, resume.extracted_text)
    requirements_by_key = {f"R{i + 1}": r for i, r in enumerate(requirements)}

    scored: list[ScoredRequirement] = []
    for assessment in verified.requirement_assessments:
        requirement = requirements_by_key.get(assessment.requirement_key)
        if requirement is None:
            continue
        status = RequirementResultStatus(assessment.status)
        db.add(
            RequirementResult(
                evaluation_id=evaluation.id,
                requirement_id=requirement.id,
                status=status,
                evidence_json=[{"quote": q} for q in assessment.evidence_quotes],
                explanation=assessment.explanation,
            )
        )
        scored.append(ScoredRequirement(requirement=requirement, status=status))

    score, coverage_score = compute_ai_score(scored, len(verified.strengths))

    evaluation.status = EvaluationStatus.COMPLETED
    evaluation.score = score
    evaluation.coverage_score = coverage_score
    evaluation.strengths_json = [s.model_dump() for s in verified.strengths]
    evaluation.questions_json = list(verified.follow_up_questions)
    evaluation.completed_at = datetime.now(UTC)
    db.commit()
    return evaluation
