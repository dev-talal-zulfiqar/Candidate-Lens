from sqlalchemy import select

from app.integrations.ai_provider import AICallResult, MockAIProvider
from app.models.enums import EvaluationStage, EvaluationStatus
from app.models.evaluation import Evaluation
from app.services.jobs import run_ai_evaluations_for_job
from tests.factories import (
    make_application,
    make_candidate,
    make_job,
    make_job_requirement,
    make_resume,
)

TRIGGER = "TRIGGER_UNEXPECTED_BUG"


class FlakyProvider:
    """Behaves like MockAIProvider except it raises a plain, unexpected
    exception (not AIProviderError) for any resume containing a marker —
    simulating a genuine bug in evaluation logic rather than an ordinary
    provider failure.
    """

    MODEL_VERSION = MockAIProvider.MODEL_VERSION

    def evaluate(self, request) -> AICallResult:
        if TRIGGER in request.resume_text:
            raise RuntimeError("boom — simulated unexpected bug")
        return MockAIProvider().evaluate(request)


def _completed_ai_evaluation(db, application_id):
    return db.execute(
        select(Evaluation).where(
            Evaluation.application_id == application_id,
            Evaluation.stage == EvaluationStage.AI,
            Evaluation.status == EvaluationStatus.COMPLETED,
        )
    ).scalar_one_or_none()


def test_unexpected_failure_mid_batch_does_not_abort_or_lose_earlier_commits(db_session):
    """QA-004 regression: a non-AIProviderError exception partway through a
    batch must not propagate (which would 500 the whole request) and must
    not undo earlier applications' already-committed evaluations.
    """
    job = make_job(db_session)
    requirement = make_job_requirement(db_session, job)

    candidate_a = make_candidate(db_session, display_name="Candidate A")
    resume_a = make_resume(db_session, candidate_a, file_hash="hash-a")
    resume_a.extracted_text = "Senior engineer, 6 years of Python experience."
    application_a = make_application(db_session, job, candidate_a, resume_a)

    candidate_b = make_candidate(db_session, display_name="Candidate B")
    resume_b = make_resume(db_session, candidate_b, file_hash="hash-b")
    resume_b.extracted_text = f"{TRIGGER} — Python developer."
    application_b = make_application(db_session, job, candidate_b, resume_b)
    db_session.flush()

    failures = run_ai_evaluations_for_job(
        db_session, job, [requirement], FlakyProvider(), FlakyProvider.MODEL_VERSION
    )

    assert failures == [application_b.id]
    assert _completed_ai_evaluation(db_session, application_a.id) is not None
    assert _completed_ai_evaluation(db_session, application_b.id) is None
