import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import CandidateDecision, EvaluationStatus, ExtractionStatus, ReviewStatus


class EvaluationSummary(BaseModel):
    status: EvaluationStatus
    score: Decimal | None
    coverage_score: Decimal | None
    completed_at: datetime | None


class BaselineSummary(BaseModel):
    """Mandatory-requirement coverage from the AI evaluation only — a
    preliminary evaluation can never assert "not met" (only met/unverified),
    so it can't produce a trustworthy met/total fraction.
    """

    met: int
    total: int


class CandidatePoolEntry(BaseModel):
    application_id: uuid.UUID
    candidate_id: uuid.UUID
    display_name: str | None
    resume_filename: str
    extraction_status: ExtractionStatus
    review_status: ReviewStatus
    decision: CandidateDecision | None
    created_at: datetime
    preliminary_evaluation: EvaluationSummary | None
    ai_evaluation: EvaluationSummary | None
    baseline: BaselineSummary | None


class CandidatePoolSummary(BaseModel):
    total_applications: int
    extraction_completed: int
    extraction_failed: int


class CandidatePoolResponse(BaseModel):
    items: list[CandidatePoolEntry]
    page: int
    page_size: int
    total: int
    summary: CandidatePoolSummary
