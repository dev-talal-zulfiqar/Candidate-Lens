import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import CandidateDecision, ReviewStatus, pg_enum

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.evaluation import Evaluation
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.upload_batch import UploadBatch


class Application(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_job_id_review_status", "job_id", "review_status"),
        Index("ix_applications_job_id_decision", "job_id", "decision"),
        Index("ix_applications_candidate_id", "candidate_id"),
        Index("ix_applications_resume_id", "resume_id"),
        Index("ix_applications_batch_id", "batch_id"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="SET NULL"), default=None
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, name="review_status"),
        nullable=False,
        default=ReviewStatus.UNREVIEWED,
    )
    decision: Mapped[CandidateDecision | None] = mapped_column(
        pg_enum(CandidateDecision, name="candidate_decision"), default=None
    )

    job: Mapped["Job"] = relationship(back_populates="applications")
    candidate: Mapped["Candidate"] = relationship(back_populates="applications")
    resume: Mapped["Resume"] = relationship(back_populates="applications")
    batch: Mapped["UploadBatch | None"] = relationship(back_populates="applications")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="application")
