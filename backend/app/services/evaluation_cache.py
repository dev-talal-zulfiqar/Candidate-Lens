import hashlib

from app.services.scoring import SCORING_VERSION


def compute_input_hash(
    *,
    resume_file_hash: str,
    rubric_version: int,
    stage: str,
    model_version: str = "",
    prompt_version: str = "",
) -> str:
    """Cache / idempotency key shared by both evaluation stages.

    Combines everything that could change the result: the exact resume
    content, the rubric version, which stage produced it, and — for AI
    evaluations — the model and prompt version. Bumping SCORING_VERSION
    invalidates every cached result even if nothing else changed, since the
    formula itself is part of what "the same evaluation" means.
    """
    key = (
        f"{resume_file_hash}|{rubric_version}|{stage}|{model_version}|"
        f"{prompt_version}|{SCORING_VERSION}"
    )
    return hashlib.sha256(key.encode()).hexdigest()
