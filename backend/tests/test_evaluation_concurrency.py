from decimal import Decimal

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.integrations.ai_provider import MockAIProvider
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.enums import (
    EvaluationStage,
    EvaluationStatus,
    ExtractionStatus,
    RequirementCategory,
)
from app.models.evaluation import Evaluation
from app.models.job import Job, JobRequirement
from app.models.resume import Resume
from app.services.ai_evaluation import run_ai_evaluation
from app.services.evaluation import run_preliminary_evaluation
from app.services.evaluation_cache import compute_input_hash
from tests.conftest import TEST_DATABASE_URL
from tests.factories import (
    make_application,
    make_candidate,
    make_job,
    make_job_requirement,
    make_resume,
)


def test_unique_constraint_blocks_true_duplicate_evaluation_rows(db_session):
    """The DB-level guarantee the rest of this file's recovery logic relies
    on: two evaluation rows with identical (application_id, stage,
    input_hash) cannot both exist, even if application code somehow tries.
    """
    job = make_job(db_session)
    candidate = make_candidate(db_session)
    resume = make_resume(db_session, candidate)
    application = make_application(db_session, job, candidate, resume)
    db_session.flush()

    shared_hash = "identical-input-hash-for-this-test"
    db_session.add(
        Evaluation(
            application_id=application.id,
            rubric_version=1,
            stage=EvaluationStage.AI,
            status=EvaluationStatus.COMPLETED,
            input_hash=shared_hash,
        )
    )
    db_session.flush()

    db_session.add(
        Evaluation(
            application_id=application.id,
            rubric_version=1,
            stage=EvaluationStage.AI,
            status=EvaluationStatus.COMPLETED,
            input_hash=shared_hash,
        )
    )
    with pytest.raises(IntegrityError, match="uq_evaluations_application_stage_input_hash"):
        db_session.flush()


def test_ai_evaluation_recovers_when_a_concurrent_run_is_already_in_flight():
    """Simulates the real race window: another request's evaluation for the
    exact same (application, stage, inputs) has already been committed but
    hasn't completed yet (status=running), so the cache lookup — which only
    matches *completed* evaluations — doesn't short-circuit early. This run
    must hit the unique constraint on its own insert and recover gracefully
    instead of crashing or calling the AI provider a second time.

    Uses its own real session/transaction rather than the shared `db_session`
    fixture: that fixture wraps every test in a SAVEPOINT so route-handler
    commits can be rolled back for isolation, but a mid-test
    `session.rollback()` there — which is exactly what the recovery code
    under test calls — rolls back the *outer* transaction too, wiping out
    even already-flushed setup data a real production session would never
    touch. A plain session matches how `get_db()` actually behaves in
    production.
    """
    engine = create_engine(TEST_DATABASE_URL)
    db = sessionmaker(bind=engine)()
    job = candidate = resume = None
    try:
        job = Job(title="Race Test", description_md="x")
        db.add(job)
        db.flush()
        requirement = JobRequirement(
            job_id=job.id,
            description="Python experience",
            category=RequirementCategory.MANDATORY,
            weight=Decimal("1"),
            sort_order=0,
        )
        db.add(requirement)
        candidate = Candidate()
        db.add(candidate)
        db.flush()
        resume = Resume(
            candidate_id=candidate.id,
            original_filename="r.pdf",
            storage_path="/tmp/concurrency-test-resume.pdf",
            file_hash="standalone-race-hash",
            extraction_status=ExtractionStatus.COMPLETED,
            extracted_text="Experienced Python engineer.",
        )
        db.add(resume)
        db.flush()
        application = Application(job_id=job.id, candidate_id=candidate.id, resume_id=resume.id)
        db.add(application)
        db.flush()

        in_flight_hash = compute_input_hash(
            resume_file_hash=resume.file_hash,
            rubric_version=job.rubric_version,
            stage="ai",
            model_version=MockAIProvider.MODEL_VERSION,
            prompt_version="v1",
        )
        in_flight = Evaluation(
            application_id=application.id,
            rubric_version=job.rubric_version,
            stage=EvaluationStage.AI,
            status=EvaluationStatus.RUNNING,  # not completed — cache lookup won't find it
            model_version=MockAIProvider.MODEL_VERSION,
            input_hash=in_flight_hash,
        )
        db.add(in_flight)
        db.commit()

        result = run_ai_evaluation(
            db, application, job, [requirement], MockAIProvider(), MockAIProvider.MODEL_VERSION
        )

        # Recovered the in-flight row rather than erroring or inserting a
        # second, duplicate one.
        assert result.id == in_flight.id
        assert result.status == EvaluationStatus.RUNNING
    finally:
        db.rollback()
        if job is not None:
            application_ids = select(Application.id).where(Application.job_id == job.id)
            db.execute(delete(Evaluation).where(Evaluation.application_id.in_(application_ids)))
            db.execute(delete(Application).where(Application.job_id == job.id))
            db.execute(delete(JobRequirement).where(JobRequirement.job_id == job.id))
            db.execute(delete(Job).where(Job.id == job.id))
        if resume is not None:
            db.execute(delete(Resume).where(Resume.id == resume.id))
        if candidate is not None:
            db.execute(delete(Candidate).where(Candidate.id == candidate.id))
        db.commit()
        db.close()
        engine.dispose()


def test_preliminary_evaluation_is_idempotent_for_identical_inputs(db_session):
    """The application-level pre-check for preliminary evaluation has no
    status filter, so in a single-threaded test it always short-circuits
    before reaching the insert — it can't independently exercise the
    IntegrityError-recovery branch the way the AI test above does (that
    would need two genuinely concurrent DB connections). What's verified
    here is the externally-observable guarantee: calling twice with
    identical inputs never produces two evaluations. The DB constraint
    proven in the first test above is what closes the true concurrent gap.
    """
    job = make_job(db_session)
    requirement = make_job_requirement(db_session, job)
    candidate = make_candidate(db_session)
    resume = make_resume(db_session, candidate, file_hash="prelim-idempotency-hash")
    # make_job_requirement's default description states "5+ years" — give
    # the resume a matching duration nearby so this reaches MET; the point
    # of this test is idempotency, not the quantitative-years heuristic.
    resume.extracted_text = "Experienced engineer with 6 years of professional Python development."
    application = make_application(db_session, job, candidate, resume)
    db_session.flush()

    first = run_preliminary_evaluation(db_session, application, job, [requirement])
    second = run_preliminary_evaluation(db_session, application, job, [requirement])

    assert first is not None
    assert first.score == Decimal("70.00")
    assert second is None  # no-op: an evaluation for these exact inputs already exists
