import re

from app.integrations.ai_schemas import AIEvaluationResponse, RequirementAssessment


def _normalize(text: str) -> str:
    """Collapse whitespace only — the one normalization safe enough that it
    can't turn a fabricated quote into a "verified" one.
    """
    return re.sub(r"\s+", " ", text).strip()


def quote_is_verified(quote: str, resume_text: str) -> bool:
    if not quote.strip():
        return False
    return _normalize(quote) in _normalize(resume_text)


def verify_evidence(
    response: AIEvaluationResponse, resume_text: str
) -> AIEvaluationResponse:
    """Re-check every evidence quote the model returned against the actual
    resume text, downgrading or dropping anything that doesn't verify.

    This is the core anti-hallucination guardrail: the model's own claim
    that a quote exists is never trusted without checking it ourselves.
    """
    verified_assessments = [
        _verify_assessment(assessment, resume_text)
        for assessment in response.requirement_assessments
    ]
    verified_strengths = [
        strength
        for strength in response.strengths
        if quote_is_verified(strength.evidence_quote, resume_text)
    ]
    return AIEvaluationResponse(
        requirement_assessments=verified_assessments,
        strengths=verified_strengths,
        follow_up_questions=response.follow_up_questions,
        uncertainty_notes=response.uncertainty_notes,
    )


def _verify_assessment(
    assessment: RequirementAssessment, resume_text: str
) -> RequirementAssessment:
    verified_quotes = [
        quote for quote in assessment.evidence_quotes if quote_is_verified(quote, resume_text)
    ]

    if assessment.status in ("met", "not_met") and not verified_quotes:
        return RequirementAssessment(
            requirement_key=assessment.requirement_key,
            status="unverified",
            explanation=(
                f"{assessment.explanation} (the model's cited evidence could not be "
                "verified against the actual resume text, so this was downgraded to "
                "unverified)"
            ),
            evidence_quotes=[],
        )

    return RequirementAssessment(
        requirement_key=assessment.requirement_key,
        status=assessment.status,
        explanation=assessment.explanation,
        evidence_quotes=verified_quotes,
    )
