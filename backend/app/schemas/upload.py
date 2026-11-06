import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import BatchStatus
from app.services.resume_upload import OutcomeStatus


class ResumeUploadResult(BaseModel):
    filename: str
    status: OutcomeStatus
    candidate_id: uuid.UUID | None = None
    resume_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    error: str | None = None


class UploadBatchRead(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: BatchStatus
    total_count: int
    processed_count: int
    failed_count: int
    created_at: datetime
    completed_at: datetime | None
    results: list[ResumeUploadResult]

    model_config = {"from_attributes": True}
