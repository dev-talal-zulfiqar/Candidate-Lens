from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import RequirementCategory, RequirementResultStatus
from app.models.job import JobRequirement

# Documented, versioned MVP rubric (see product spec section 7): mandatory
# requirements are worth 70% of the score, preferred 20%. The remaining 10%
# is reserved for AI-identified additional strengths and is only awarded
# once a deep AI evaluation actually runs (Milestone 6) — preliminary
# scoring never manufactures credit for evidence it doesn't have, so a
# preliminary score tops out at 90, not 100.
MANDATORY_MAX_POINTS = Decimal("70")
PREFERRED_MAX_POINTS = Decimal("20")
STRENGTHS_MAX_POINTS = Decimal("10")

# Bumped whenever the scoring formula itself changes, independent of the
# rubric content (job.rubric_version) or the AI prompt (PROMPT_VERSION) —
# part of the evaluation cache key so a formula change invalidates cached
# results even if nothing else did.
SCORING_VERSION = "v1"


@dataclass(frozen=True)
class ScoredRequirement:
    requirement: JobRequirement
    status: RequirementResultStatus


def compute_preliminary_score(
    scored: list[ScoredRequirement],
) -> tuple[Decimal, Decimal | None]:
    """Compute (score, coverage_score) for a preliminary evaluation.

    `score` is importance-weighted: each category's share of points is
    distributed across its requirements by `weight`, and only `met`
    requirements earn credit. A category with zero requirements simply
    contributes zero points rather than being excluded from the total —
    keeps the formula simple and the 90-point preliminary ceiling constant
    across jobs, at the cost of jobs with no preferred requirements never
    exceeding 70. This is a deliberate MVP trade-off, not a bug.

    `coverage_score` is a simpler, unweighted signal: the plain fraction of
    requirements with any matched evidence at all, regardless of category
    or weight — "how much of the rubric could we find anything for."
    """
    score = _requirements_score(scored)
    return score.quantize(Decimal("0.01")), _coverage_score(scored)


def compute_ai_score(
    scored: list[ScoredRequirement], verified_strength_count: int
) -> tuple[Decimal, Decimal | None]:
    """Compute (score, coverage_score) for a deep AI evaluation.

    Same mandatory/preferred weighting as the preliminary score, plus up to
    10 points for verified, evidence-backed strengths — the piece withheld
    at the preliminary stage because no AI reasoning had run yet. A single
    incidental strength earns half credit; two or more earns full credit.
    This tiering (not a smooth per-strength curve) is a deliberate, simple
    product rubric, not a precision metric.
    """
    score = _requirements_score(scored) + _strengths_score(verified_strength_count)
    return score.quantize(Decimal("0.01")), _coverage_score(scored)


def _strengths_score(verified_strength_count: int) -> Decimal:
    if verified_strength_count <= 0:
        return Decimal(0)
    if verified_strength_count == 1:
        return STRENGTHS_MAX_POINTS / 2
    return STRENGTHS_MAX_POINTS


def _requirements_score(scored: list[ScoredRequirement]) -> Decimal:
    return _category_score(
        scored, RequirementCategory.MANDATORY, MANDATORY_MAX_POINTS
    ) + _category_score(scored, RequirementCategory.PREFERRED, PREFERRED_MAX_POINTS)


def _coverage_score(scored: list[ScoredRequirement]) -> Decimal | None:
    total = len(scored)
    if total == 0:
        return None
    met = sum(1 for s in scored if s.status == RequirementResultStatus.MET)
    return ((Decimal(met) / Decimal(total)) * Decimal(100)).quantize(Decimal("0.01"))


def _category_score(
    scored: list[ScoredRequirement], category: RequirementCategory, max_points: Decimal
) -> Decimal:
    items = [s for s in scored if s.requirement.category == category]
    if not items:
        return Decimal(0)

    total_weight = sum((item.requirement.weight for item in items), Decimal(0))
    if total_weight == 0:
        return Decimal(0)

    met_weight = sum(
        (item.requirement.weight for item in items if item.status == RequirementResultStatus.MET),
        Decimal(0),
    )
    return (met_weight / total_weight) * max_points
