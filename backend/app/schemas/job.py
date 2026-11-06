import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import RequirementCategory

# Zero-width/invisible characters that paste in silently from web pages,
# Word, and Google Docs -- harmless to look at but can break line-based
# parsing (e.g. the AI requirement-inference heuristic splitting on "\n")
# in ways the person pasting has no way to notice. Built from chr() codes
# rather than literal characters so nothing invisible lives in the source
# file itself.
_INVISIBLE_CODEPOINTS = (0x200B, 0x200C, 0x200D, 0xFEFF)  # ZWSP, ZWNJ, ZWJ, BOM
_INVISIBLE_CHARS_PATTERN = re.compile("[" + "".join(chr(c) for c in _INVISIBLE_CODEPOINTS) + "]")
_NON_BREAKING_SPACE = chr(0xA0)


def _normalize_pasted_text(value: str) -> str:
    """Clean up common copy-paste artifacts before text is stored or used
    for anything: different OS line endings, non-breaking spaces, invisible
    zero-width characters, and trailing whitespace on individual lines.
    """
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace(_NON_BREAKING_SPACE, " ")
    normalized = _INVISIBLE_CHARS_PATTERN.sub("", normalized)
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field(min_length=1, max_length=20_000)

    @field_validator("title", "description_md")
    @classmethod
    def strip_and_require_non_blank(cls, value: str) -> str:
        stripped = _normalize_pasted_text(value)
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class JobRequirementCreate(BaseModel):
    description: str = Field(min_length=1, max_length=2_000)
    category: RequirementCategory
    # Weight is relative within its own category (mandatory/preferred), not
    # absolute -- the scoring formula splits each category's point share by
    # weight ratio (see app/services/scoring.py). An unbounded weight would
    # let one requirement silently swamp every other requirement in its
    # category; 10 is generous for real differentiation while catching
    # fat-finger entries like 1000.
    weight: Decimal = Field(gt=0, le=10)
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("description")
    @classmethod
    def strip_and_require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class JobRequirementsCreate(BaseModel):
    requirements: list[JobRequirementCreate] = Field(min_length=1, max_length=100)


class RequirementSuggestionRead(BaseModel):
    """An AI-proposed draft requirement -- not persisted, not a JobRequirement.
    The hiring manager edits these client-side before confirming, at which
    point they're submitted through the normal requirements-create endpoint.
    """

    description: str
    category: RequirementCategory
    weight: Decimal


class JobRequirementRead(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    description: str
    category: RequirementCategory
    weight: Decimal
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class JobRead(BaseModel):
    id: uuid.UUID
    title: str
    description_md: str
    rubric_version: int
    created_at: datetime
    updated_at: datetime
    requirements: list[JobRequirementRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class JobSummary(BaseModel):
    id: uuid.UUID
    title: str
    rubric_version: int
    created_at: datetime
    requirement_count: int

    model_config = {"from_attributes": True}
