import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RequirementCategory, pg_enum

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.evaluation import RequirementResult
    from app.models.upload_batch import UploadBatch


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description_md: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_version: Mapped[int] = mapped_column(nullable=False, default=1)

    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="job",
        order_by="JobRequirement.sort_order",
        cascade="save-update, merge",
    )
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    upload_batches: Mapped[list["UploadBatch"]] = relationship(back_populates="job")


class JobRequirement(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "job_requirements"
    __table_args__ = (
        CheckConstraint("weight > 0", name="positive_weight"),
        Index("ix_job_requirements_job_id", "job_id"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RequirementCategory] = mapped_column(
        pg_enum(RequirementCategory, name="requirement_category"), nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    job: Mapped["Job"] = relationship(back_populates="requirements")
    requirement_results: Mapped[list["RequirementResult"]] = relationship(
        back_populates="requirement"
    )
