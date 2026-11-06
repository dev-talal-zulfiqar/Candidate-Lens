from decimal import Decimal

from app.models.enums import RequirementCategory, RequirementResultStatus
from app.models.job import JobRequirement
from app.services.scoring import ScoredRequirement, compute_ai_score, compute_preliminary_score


def make_requirement(category: RequirementCategory, weight: str) -> JobRequirement:
    return JobRequirement(category=category, weight=Decimal(weight), description="x")


def test_all_mandatory_met_scores_seventy():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.MET
        )
    ]
    score, coverage = compute_preliminary_score(scored)
    assert score == Decimal("70.00")
    assert coverage == Decimal("100.00")


def test_all_preferred_met_scores_twenty():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.PREFERRED, "1"), RequirementResultStatus.MET
        )
    ]
    score, _ = compute_preliminary_score(scored)
    assert score == Decimal("20.00")


def test_mixed_mandatory_and_preferred_caps_at_ninety():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.MET
        ),
        ScoredRequirement(
            make_requirement(RequirementCategory.PREFERRED, "1"), RequirementResultStatus.MET
        ),
    ]
    score, coverage = compute_preliminary_score(scored)
    # 70 + 20 = 90, never 100 — the remaining 10 points require AI-identified
    # strengths that don't exist until a deep evaluation actually runs.
    assert score == Decimal("90.00")
    assert coverage == Decimal("100.00")


def test_unverified_requirement_earns_no_credit():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"),
            RequirementResultStatus.UNVERIFIED,
        )
    ]
    score, coverage = compute_preliminary_score(scored)
    assert score == Decimal("0.00")
    assert coverage == Decimal("0.00")


def test_weight_proportional_credit_within_category():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "3"), RequirementResultStatus.MET
        ),
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"),
            RequirementResultStatus.UNVERIFIED,
        ),
    ]
    score, coverage = compute_preliminary_score(scored)
    # 3 of 4 weight units met -> 3/4 * 70 = 52.5
    assert score == Decimal("52.50")
    assert coverage == Decimal("50.00")


def test_empty_category_contributes_zero_not_excluded():
    # Only mandatory requirements exist; preferred's 20 points are simply
    # unreachable for this job rather than redistributed elsewhere.
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.MET
        )
    ]
    score, _ = compute_preliminary_score(scored)
    assert score == Decimal("70.00")


def test_no_requirements_returns_none_coverage():
    score, coverage = compute_preliminary_score([])
    assert score == Decimal("0.00")
    assert coverage is None


def test_ai_score_with_no_strengths_matches_preliminary_ceiling():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.MET
        ),
        ScoredRequirement(
            make_requirement(RequirementCategory.PREFERRED, "1"), RequirementResultStatus.MET
        ),
    ]
    score, _ = compute_ai_score(scored, verified_strength_count=0)
    assert score == Decimal("90.00")


def test_ai_score_one_strength_earns_half_credit():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.MET
        )
    ]
    score, _ = compute_ai_score(scored, verified_strength_count=1)
    assert score == Decimal("75.00")  # 70 + 5


def test_ai_score_two_or_more_strengths_earns_full_credit_and_reaches_100():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.MET
        ),
        ScoredRequirement(
            make_requirement(RequirementCategory.PREFERRED, "1"), RequirementResultStatus.MET
        ),
    ]
    score, _ = compute_ai_score(scored, verified_strength_count=2)
    assert score == Decimal("100.00")

    score_more, _ = compute_ai_score(scored, verified_strength_count=5)
    assert score_more == Decimal("100.00")  # capped, not unbounded


def test_ai_score_can_reflect_a_genuine_not_met():
    scored = [
        ScoredRequirement(
            make_requirement(RequirementCategory.MANDATORY, "1"), RequirementResultStatus.NOT_MET
        )
    ]
    score, coverage = compute_ai_score(scored, verified_strength_count=0)
    assert score == Decimal("0.00")
    assert coverage == Decimal("0.00")
