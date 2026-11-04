import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    EvaluationStage,
    EvaluationStatus,
    RequirementResultStatus,
    pg_enum,
)

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job import JobRequirement


class Evaluation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (Index("ix_evaluations_application_id", "application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False
    )
    rubric_version: Mapped[int] = mapped_column(nullable=False)
    stage: Mapped[EvaluationStage] = mapped_column(
        pg_enum(EvaluationStage, name="evaluation_stage"), nullable=False
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        pg_enum(EvaluationStatus, name="evaluation_status"),
        nullable=False,
        default=EvaluationStatus.PENDING,
    )
    score: Mapped[Decimal | None] = mapped_column(default=None)
    coverage_score: Mapped[Decimal | None] = mapped_column(default=None)
    model_version: Mapped[str | None] = mapped_column(default=None)
    prompt_version: Mapped[str | None] = mapped_column(default=None)
    input_hash: Mapped[str | None] = mapped_column(default=None)
    strengths_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    questions_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    application: Mapped["Application"] = relationship(back_populates="evaluations")
    requirement_results: Mapped[list["RequirementResult"]] = relationship(
        back_populates="evaluation"
    )


class RequirementResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "requirement_results"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "requirement_id", name="uq_requirement_results_evaluation_requirement"
        ),
        Index("ix_requirement_results_evaluation_id", "evaluation_id"),
        Index("ix_requirement_results_requirement_id", "requirement_id"),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[RequirementResultStatus] = mapped_column(
        pg_enum(RequirementResultStatus, name="requirement_result_status"), nullable=False
    )
    evidence_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="requirement_results")
    requirement: Mapped["JobRequirement"] = relationship(back_populates="requirement_results")
