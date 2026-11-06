from typing import Literal

from pydantic import BaseModel, Field


class RequirementAssessment(BaseModel):
    """One requirement's assessment, keyed by the short "R1"-style tag the
    prompt assigns — not the database UUID, which models are unreliable at
    reproducing verbatim.
    """

    requirement_key: str
    status: Literal["met", "not_met", "unverified"]
    explanation: str
    evidence_quotes: list[str]


class NoteworthyStrength(BaseModel):
    description: str
    evidence_quote: str


class AIEvaluationResponse(BaseModel):
    """The full structured contract an AI provider must return.

    Every field is required (no Optionals) to keep the JSON schema simple
    and robust for strict structured-output parsing — "nothing to report"
    is represented by an empty list/string, not null.
    """

    requirement_assessments: list[RequirementAssessment]
    strengths: list[NoteworthyStrength]
    follow_up_questions: list[str]
    uncertainty_notes: str


class RequirementSuggestion(BaseModel):
    """One AI-proposed rubric line, not yet persisted — the hiring manager
    reviews and edits these before they become real JobRequirement rows.
    """

    description: str
    category: Literal["mandatory", "preferred"]
    # Same bound as the real JobRequirementCreate (app/schemas/job.py) —
    # keep them in sync so a draft that validates here won't turn around
    # and get rejected when the hiring manager confirms it.
    weight: float = Field(gt=0, le=10)


class RequirementInferenceResponse(BaseModel):
    requirements: list[RequirementSuggestion]
