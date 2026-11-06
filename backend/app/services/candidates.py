import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.enums import (
    EvaluationStage,
    EvaluationStatus,
    ExtractionStatus,
    RequirementCategory,
    RequirementResultStatus,
    ReviewStatus,
)
from app.models.evaluation import Evaluation, RequirementResult
from app.models.job import JobRequirement
from app.models.resume import Resume
from app.schemas.candidate import (
    BaselineSummary,
    CandidatePoolEntry,
    CandidatePoolResponse,
    CandidatePoolSummary,
    EvaluationSummary,
)

SortBy = Literal["score", "created_at", "display_name"]
SortDir = Literal["asc", "desc"]


@dataclass(frozen=True)
class CandidatePoolFilters:
    search: str | None = None
    min_score: Decimal | None = None
    requirement_status: str | None = None
    review_status: ReviewStatus | None = None


def _current_evaluation_subquery(job_id: uuid.UUID, stage: EvaluationStage, label_prefix: str):
    """Latest *completed* evaluation per application for one stage, scoped
    to one job.

    Mirrors the definition in app.db.queries.get_current_evaluation, but as
    a joinable subquery — evaluations are append-only, so "current" means
    the most recently completed attempt, not simply the newest row. Columns
    are prefixed so preliminary and AI subqueries can be joined side by side
    without name collisions.

    Joins against Application and filters by job_id *before* the
    ROW_NUMBER() window runs, rather than windowing over every evaluation
    in the table and relying on the caller's later join to Application to
    narrow it down — ranking globally first is a known optimization fence
    that can block the planner from pushing the job_id filter down.
    """
    rank = (
        func.row_number()
        .over(partition_by=Evaluation.application_id, order_by=Evaluation.completed_at.desc())
        .label("rank")
    )
    ranked = (
        select(
            Evaluation.id.label(f"{label_prefix}_evaluation_id"),
            Evaluation.application_id.label("application_id"),
            Evaluation.status.label(f"{label_prefix}_status"),
            Evaluation.score.label(f"{label_prefix}_score"),
            Evaluation.coverage_score.label(f"{label_prefix}_coverage_score"),
            Evaluation.completed_at.label(f"{label_prefix}_completed_at"),
            rank,
        )
        .join(Application, Application.id == Evaluation.application_id)
        .where(
            Application.job_id == job_id,
            Evaluation.stage == stage,
            Evaluation.status == EvaluationStatus.COMPLETED,
        )
        .subquery()
    )
    return select(ranked).where(ranked.c.rank == 1).subquery()


def _mandatory_requirement_count_subquery(ai_eval, *, met_only: bool):
    """Count mandatory JobRequirements covered by an AI evaluation's results,
    correlated to the current row's ai_eval subquery (so it yields NULL
    counts, not zero, when there is no AI evaluation yet).
    """
    statement = (
        select(func.count(RequirementResult.id))
        .join(JobRequirement, RequirementResult.requirement_id == JobRequirement.id)
        .where(
            RequirementResult.evaluation_id == ai_eval.c.ai_evaluation_id,
            JobRequirement.category == RequirementCategory.MANDATORY,
        )
    )
    if met_only:
        statement = statement.where(RequirementResult.status == RequirementResultStatus.MET)
    return statement.correlate(ai_eval).scalar_subquery()


def get_pool_summary(db: Session, job_id: uuid.UUID) -> CandidatePoolSummary:
    row = db.execute(
        select(
            func.count(Application.id),
            func.count().filter(Resume.extraction_status == ExtractionStatus.COMPLETED),
            func.count().filter(Resume.extraction_status == ExtractionStatus.FAILED),
        )
        .select_from(Application)
        .join(Resume, Application.resume_id == Resume.id)
        .where(Application.job_id == job_id)
    ).one()
    return CandidatePoolSummary(
        total_applications=row[0], extraction_completed=row[1], extraction_failed=row[2]
    )


def list_candidate_pool(
    db: Session,
    job_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    sort_by: SortBy,
    sort_dir: SortDir,
    filters: CandidatePoolFilters,
) -> CandidatePoolResponse:
    preliminary_eval = _current_evaluation_subquery(job_id, EvaluationStage.PRELIMINARY, "prelim")
    ai_eval = _current_evaluation_subquery(job_id, EvaluationStage.AI, "ai")

    base = (
        select(
            Application,
            Candidate,
            Resume,
            preliminary_eval.c.prelim_evaluation_id,
            preliminary_eval.c.prelim_status,
            preliminary_eval.c.prelim_score,
            preliminary_eval.c.prelim_coverage_score,
            preliminary_eval.c.prelim_completed_at,
            ai_eval.c.ai_evaluation_id,
            ai_eval.c.ai_status,
            ai_eval.c.ai_score,
            ai_eval.c.ai_coverage_score,
            ai_eval.c.ai_completed_at,
            _mandatory_requirement_count_subquery(ai_eval, met_only=False).label(
                "baseline_total"
            ),
            _mandatory_requirement_count_subquery(ai_eval, met_only=True).label("baseline_met"),
        )
        .join(Candidate, Application.candidate_id == Candidate.id)
        .join(Resume, Application.resume_id == Resume.id)
        .outerjoin(preliminary_eval, preliminary_eval.c.application_id == Application.id)
        .outerjoin(ai_eval, ai_eval.c.application_id == Application.id)
        .where(Application.job_id == job_id)
    )

    if filters.search:
        pattern = f"%{filters.search}%"
        base = base.where(
            Candidate.display_name.ilike(pattern) | Resume.original_filename.ilike(pattern)
        )
    if filters.review_status is not None:
        base = base.where(Application.review_status == filters.review_status)
    if filters.min_score is not None:
        base = base.where(preliminary_eval.c.prelim_score >= filters.min_score)
    if filters.requirement_status is not None:
        requirement_match = select(RequirementResult.evaluation_id).where(
            RequirementResult.evaluation_id == preliminary_eval.c.prelim_evaluation_id,
            RequirementResult.status == filters.requirement_status,
        )
        base = base.where(requirement_match.exists())

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    base = base.order_by(*_order_clauses(preliminary_eval, sort_by, sort_dir))
    base = base.offset((page - 1) * page_size).limit(page_size)

    items = [_to_entry(row) for row in db.execute(base).all()]

    summary = get_pool_summary(db, job_id)
    return CandidatePoolResponse(
        items=items, page=page, page_size=page_size, total=total, summary=summary
    )


def _order_clauses(preliminary_eval, sort_by: SortBy, sort_dir: SortDir):
    descending = sort_dir == "desc"
    if sort_by == "score":
        column = preliminary_eval.c.prelim_score
        return [column.is_(None), column.desc() if descending else column.asc()]
    if sort_by == "display_name":
        column = Candidate.display_name
        return [column.is_(None), column.desc() if descending else column.asc()]
    column = Application.created_at
    return [column.desc() if descending else column.asc()]


def _to_entry(row) -> CandidatePoolEntry:
    preliminary_evaluation = (
        EvaluationSummary(
            status=row.prelim_status,
            score=row.prelim_score,
            coverage_score=row.prelim_coverage_score,
            completed_at=row.prelim_completed_at,
        )
        if row.prelim_evaluation_id is not None
        else None
    )
    ai_evaluation = (
        EvaluationSummary(
            status=row.ai_status,
            score=row.ai_score,
            coverage_score=row.ai_coverage_score,
            completed_at=row.ai_completed_at,
        )
        if row.ai_evaluation_id is not None
        else None
    )
    baseline = (
        BaselineSummary(met=row.baseline_met or 0, total=row.baseline_total)
        if row.ai_evaluation_id is not None and row.baseline_total
        else None
    )
    return CandidatePoolEntry(
        application_id=row.Application.id,
        candidate_id=row.Candidate.id,
        display_name=row.Candidate.display_name,
        resume_filename=row.Resume.original_filename,
        extraction_status=row.Resume.extraction_status,
        review_status=row.Application.review_status,
        decision=row.Application.decision,
        created_at=row.Application.created_at,
        preliminary_evaluation=preliminary_evaluation,
        ai_evaluation=ai_evaluation,
        baseline=baseline,
    )
