import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import ExtractionStatus, pg_enum

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.candidate import Candidate


class Resume(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (
        Index("ix_resumes_candidate_id", "candidate_id"),
        # Unique, not just indexed: this is what makes "dedupe uploads by
        # content hash" (see resume_upload.py) a real guarantee instead of a
        # check-then-act race between two near-simultaneous uploads of the
        # same file.
        UniqueConstraint("file_hash", name="uq_resumes_file_hash"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, default=None)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        pg_enum(ExtractionStatus, name="extraction_status"),
        nullable=False,
        default=ExtractionStatus.PENDING,
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="resumes")
    applications: Mapped[list["Application"]] = relationship(back_populates="resume")
