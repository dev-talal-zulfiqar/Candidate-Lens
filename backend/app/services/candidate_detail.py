import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation, RequirementResult
from app.schemas.candidate_detail import ApplicationDetail, CandidateDetail
from app.schemas.evaluation import EvaluationRead


def get_candidate_detail(db: Session, candidate_id: uuid.UUID) -> CandidateDetail | None:
    statement = (
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.applications).options(
                selectinload(Application.job),
                selectinload(Application.resume),
                selectinload(Application.evaluations)
                .selectinload(Evaluation.requirement_results)
                .selectinload(RequirementResult.requirement),
            )
        )
    )
    candidate = db.execute(statement).scalar_one_or_none()
    if candidate is None:
        return None

    applications = [
        ApplicationDetail(
            application_id=application.id,
            job_id=application.job.id,
            job_title=application.job.title,
            resume_id=application.resume.id,
            resume_filename=application.resume.original_filename,
            extraction_status=application.resume.extraction_status,
            review_status=application.review_status,
            decision=application.decision,
            created_at=application.created_at,
            evaluations=[
                EvaluationRead.from_evaluation(e)
                for e in sorted(
                    application.evaluations, key=lambda e: e.created_at, reverse=True
                )
            ],
        )
        for application in sorted(
            candidate.applications, key=lambda a: a.created_at, reverse=True
        )
    ]

    return CandidateDetail(
        id=candidate.id,
        display_name=candidate.display_name,
        created_at=candidate.created_at,
        applications=applications,
    )
