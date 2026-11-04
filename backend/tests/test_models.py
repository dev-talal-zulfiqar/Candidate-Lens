from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.db.queries import get_current_evaluation
from app.models import Evaluation, JobRequirement, RequirementResult
from app.models.enums import (
    EvaluationStage,
    EvaluationStatus,
    RequirementCategory,
    RequirementResultStatus,
)
from tests.factories import (
    make_application,
    make_candidate,
    make_job,
    make_job_requirement,
    make_resume,
)


def test_job_requirement_relationship_round_trip(db_session):
    job = make_job(db_session)
    requirement = make_job_requirement(db_session, job)
    db_session.flush()
    db_session.expire_all()

    reloaded_job = db_session.get(type(job), job.id)
    assert [r.id for r in reloaded_job.requirements] == [requirement.id]
    assert requirement.job.id == job.id


def test_job_requirement_rejects_non_positive_weight(db_session):
    job = make_job(db_session)
    db_session.add(
        JobRequirement(
            job_id=job.id,
            description="Must be a wizard",
            category=RequirementCategory.MANDATORY,
            weight=Decimal("0"),
            sort_order=0,
        )
    )
    with pytest.raises(IntegrityError, match="positive_weight"):
        db_session.flush()


def test_job_requirement_rejects_invalid_category(db_session):
    job = make_job(db_session)
    with pytest.raises(DataError, match="invalid input value for enum requirement_category"):
        db_session.execute(
            JobRequirement.__table__.insert().values(
                job_id=job.id,
                description="Invalid category",
                category="not_a_real_category",
                weight=Decimal("1"),
                sort_order=0,
            )
        )
        db_session.flush()


def test_application_requires_matching_foreign_keys_to_exist(db_session):
    job = make_job(db_session)
    candidate = make_candidate(db_session)
    resume = make_resume(db_session, candidate)

    application = make_application(db_session, job, candidate, resume)

    assert application.job_id == job.id
    assert application.candidate_id == candidate.id
    assert application.resume_id == resume.id
    assert application.review_status.value == "unreviewed"


def test_deleting_job_with_requirements_is_restricted(db_session):
    job = make_job(db_session)
    make_job_requirement(db_session, job)
    db_session.flush()

    db_session.delete(job)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_requirement_result_unique_per_evaluation_and_requirement(db_session):
    job = make_job(db_session)
    requirement = make_job_requirement(db_session, job)
    candidate = make_candidate(db_session)
    resume = make_resume(db_session, candidate)
    application = make_application(db_session, job, candidate, resume)

    evaluation = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.PRELIMINARY,
        status=EvaluationStatus.COMPLETED,
    )
    db_session.add(evaluation)
    db_session.flush()

    db_session.add(
        RequirementResult(
            evaluation_id=evaluation.id,
            requirement_id=requirement.id,
            status=RequirementResultStatus.MET,
            explanation="Resume mentions 6 years of Python.",
        )
    )
    db_session.flush()

    db_session.add(
        RequirementResult(
            evaluation_id=evaluation.id,
            requirement_id=requirement.id,
            status=RequirementResultStatus.NOT_MET,
            explanation="Duplicate result for the same requirement.",
        )
    )
    with pytest.raises(IntegrityError, match="uq_requirement_results_evaluation_requirement"):
        db_session.flush()


def test_get_current_evaluation_returns_latest_completed_only(db_session):
    job = make_job(db_session)
    candidate = make_candidate(db_session)
    resume = make_resume(db_session, candidate)
    application = make_application(db_session, job, candidate, resume)

    assert get_current_evaluation(db_session, application.id, EvaluationStage.PRELIMINARY) is None

    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    failed = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.PRELIMINARY,
        status=EvaluationStatus.FAILED,
        error_message="Extraction failed",
        completed_at=base_time + timedelta(hours=5),
    )
    older_completed = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.PRELIMINARY,
        status=EvaluationStatus.COMPLETED,
        score=Decimal("50"),
        completed_at=base_time,
    )
    newer_completed = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.PRELIMINARY,
        status=EvaluationStatus.COMPLETED,
        score=Decimal("80"),
        completed_at=base_time + timedelta(hours=1),
    )
    db_session.add_all([failed, older_completed, newer_completed])
    db_session.flush()

    current = get_current_evaluation(db_session, application.id, EvaluationStage.PRELIMINARY)
    assert current is not None
    assert current.id == newer_completed.id
    assert current.score == Decimal("80")


def test_evaluation_json_columns_default_to_empty_list(db_session):
    job = make_job(db_session)
    candidate = make_candidate(db_session)
    resume = make_resume(db_session, candidate)
    application = make_application(db_session, job, candidate, resume)

    evaluation = Evaluation(
        application_id=application.id,
        rubric_version=job.rubric_version,
        stage=EvaluationStage.AI,
        status=EvaluationStatus.PENDING,
    )
    db_session.add(evaluation)
    db_session.flush()

    assert evaluation.strengths_json == []
    assert evaluation.questions_json == []
