import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.models.enums import (
    EvaluationStage,
    EvaluationStatus,
    RequirementCategory,
    RequirementResultStatus,
)
from app.models.evaluation import Evaluation, RequirementResult


class RequirementResultRead(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_description: str
    requirement_category: RequirementCategory
    status: RequirementResultStatus
    evidence_json: list[dict[str, Any]]
    explanation: str

    @classmethod
    def from_result(cls, result: RequirementResult) -> "RequirementResultRead":
        """Denormalizes the requirement's description/category onto the
        result row for display — the ORM model only stores requirement_id,
        so this needs result.requirement eager-loaded by the caller.
        """
        return cls(
            id=result.id,
            requirement_id=result.requirement_id,
            requirement_description=result.requirement.description,
            requirement_category=result.requirement.category,
            status=result.status,
            evidence_json=result.evidence_json,
            explanation=result.explanation,
        )


class EvaluationRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    rubric_version: int
    stage: EvaluationStage
    status: EvaluationStatus
    score: Decimal | None
    coverage_score: Decimal | None
    model_version: str | None
    prompt_version: str | None
    strengths_json: list[dict[str, Any]]
    questions_json: list[str]
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    requirement_results: list[RequirementResultRead] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_evaluation(cls, evaluation: Evaluation) -> "EvaluationRead":
        """Like model_validate, but denormalizes each requirement result's
        description/category onto it — needs evaluation.requirement_results
        and each result's .requirement eager-loaded by the caller. Built
        field-by-field rather than via model_validate(evaluation), because
        from_attributes would try (and fail) to auto-map the nested
        requirement_results the same way model_validate on a bare
        RequirementResult does.
        """
        return cls(
            id=evaluation.id,
            application_id=evaluation.application_id,
            rubric_version=evaluation.rubric_version,
            stage=evaluation.stage,
            status=evaluation.status,
            score=evaluation.score,
            coverage_score=evaluation.coverage_score,
            model_version=evaluation.model_version,
            prompt_version=evaluation.prompt_version,
            strengths_json=evaluation.strengths_json,
            questions_json=evaluation.questions_json,
            error_message=evaluation.error_message,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
            requirement_results=[
                RequirementResultRead.from_result(r) for r in evaluation.requirement_results
            ],
        )
