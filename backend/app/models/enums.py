from enum import Enum, StrEnum

from sqlalchemy import Enum as SAEnum


class RequirementCategory(StrEnum):
    MANDATORY = "mandatory"
    PREFERRED = "preferred"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"


class EvaluationStage(StrEnum):
    PRELIMINARY = "preliminary"
    AI = "ai"


class EvaluationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RequirementResultStatus(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    UNVERIFIED = "unverified"


def pg_enum[EnumT: Enum](enum_cls: type[EnumT], *, name: str) -> SAEnum:
    """Build a native Postgres ENUM type storing lowercase string values.

    Centralizes the values_callable wiring every enum column needs so the
    database stores "mandatory" rather than Python's member name "MANDATORY".
    """
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
