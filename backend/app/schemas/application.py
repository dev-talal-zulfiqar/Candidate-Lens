import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CandidateDecision, ReviewStatus


class ReviewStatusUpdate(BaseModel):
    review_status: ReviewStatus


class DecisionUpdate(BaseModel):
    decision: CandidateDecision | None


class ApplicationRead(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID
    batch_id: uuid.UUID | None
    review_status: ReviewStatus
    decision: CandidateDecision | None
    created_at: datetime

    model_config = {"from_attributes": True}
