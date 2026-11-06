import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import BatchStatus, pg_enum

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job import Job


class UploadBatch(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "upload_batches"
    __table_args__ = (Index("ix_upload_batches_job_id", "job_id"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[BatchStatus] = mapped_column(
        pg_enum(BatchStatus, name="batch_status"),
        nullable=False,
        default=BatchStatus.PENDING,
    )
    total_count: Mapped[int] = mapped_column(nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    # Per-file outcomes (filename, status, error, and the resulting
    # candidate/resume/application ids), appended to as processing runs in
    # the background. Durable so a client polling this batch after upload
    # processing has moved off the request thread can still see exactly
    # which files succeeded, were duplicates, or failed, and why — not
    # just the aggregate counts above.
    results_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    job: Mapped["Job"] = relationship(back_populates="upload_batches")
    applications: Mapped[list["Application"]] = relationship(back_populates="batch")

    @property
    def results(self) -> list[dict[str, Any]]:
        return self.results_json
