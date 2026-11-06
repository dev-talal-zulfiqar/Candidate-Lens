import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CandidateDecision, ExtractionStatus, ReviewStatus
from app.schemas.evaluation import EvaluationRead


class ApplicationDetail(BaseModel):
    """One candidate's application to one job — deliberately keeps job-specific
    context (review status, which resume, which job) separate from both the
    candidate's identity and the evaluation results themselves.
    """

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    resume_id: uuid.UUID
    resume_filename: str
    extraction_status: ExtractionStatus
    review_status: ReviewStatus
    decision: CandidateDecision | None
    created_at: datetime
    evaluations: list[EvaluationRead]


class CandidateDetail(BaseModel):
    id: uuid.UUID
    display_name: str | None
    created_at: datetime
    applications: list[ApplicationDetail]
