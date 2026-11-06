import math
import re
from dataclasses import dataclass

from app.models.enums import RequirementResultStatus

# Words too generic to serve as evidence on their own ("5+ years of backend
# experience" shouldn't match on "years" or "experience"). Not exhaustive —
# this is a cheap heuristic, not a proficiency assessment.
STOPWORDS = {
    "a", "an", "the", "and", "or", "with", "in", "of", "for", "to", "on", "at",
    "is", "are", "be", "as", "this", "that", "will", "have", "has", "had",
    "years", "year", "experience", "working", "strong", "excellent", "good",
    "solid", "deep", "knowledge", "skills", "skill", "ability", "proficiency",
    "plus", "preferred", "required", "must", "using", "across", "within",
    "proven", "track", "record", "background", "familiarity", "familiar",
    "understanding", "related", "field", "degree", "equivalent", "etc",
    # Generic verbs/nouns that show up in almost any job-requirement sentence
    # regardless of domain ("design, build, train, evaluate, and improve
    # advanced machine learning systems" vs "design, build, and ship web
    # apps") — on their own they say nothing about the actual skill, so
    # letting one of these alone satisfy a requirement produces exactly the
    # false-positive matches (e.g. "design" from "API design" "confirming"
    # an unrelated machine-learning requirement) this list exists to avoid.
    "design", "designing", "designed", "build", "building", "built",
    "train", "training", "trained", "evaluate", "evaluating", "evaluated",
    "improve", "improving", "improved", "develop", "developing", "developed",
    "create", "creating", "created", "implement", "implementing",
    "implemented", "deliver", "delivering", "delivered", "ensure",
    "ensuring", "maintain", "maintaining", "maintained", "support",
    "supporting", "supported", "manage", "managing", "managed", "lead",
    "leading", "led", "own", "owning", "owned", "drive", "driving", "drove",
    "collaborate", "collaborating", "collaborated", "including", "include",
    "includes", "systems", "system", "products", "product", "solutions",
    "solution", "platform", "platforms", "applications", "application",
    "based", "complex", "advanced", "technical", "execution", "domain",
}

# Multi-clause requirements (several distinct skills in one sentence) need
# genuine overlap, not a single incidental word, before they count as met —
# see match_requirement. Short, single-concept requirements ("Python
# experience" -> one keyword) are unaffected: ceil(1 * 0.5) is still 1.
MIN_KEYWORD_COVERAGE_RATIO = 0.5

# A small, explicitly non-exhaustive alias table for common abbreviations —
# "known skill aliases" per the product spec. Extend as real gaps are found;
# this is not meant to be a complete technology taxonomy.
SKILL_ALIASES: dict[str, set[str]] = {
    "javascript": {"js"},
    "typescript": {"ts"},
    "postgresql": {"postgres"},
    "kubernetes": {"k8s"},
    "node.js": {"nodejs", "node"},
    "python": set(),
    "golang": {"go"},
}

MIN_KEYWORD_LENGTH = 2
SNIPPET_RADIUS = 60

# A requirement like "5+ years of Python" currently reduces, after stopword
# removal, to just the keyword "python" — any bare mention satisfies it
# regardless of stated duration. YEARS_PATTERN pulls the number back out of
# both the requirement text and the resume so a stated duration can be
# checked for, without ever asserting not_met when it can't be confirmed
# (see match_requirement) — this stays a cheap heuristic, not a parser.
YEARS_PATTERN = re.compile(r"(\d+)\+?\s*years?", re.IGNORECASE)
YEARS_PROXIMITY_RADIUS = 100


@dataclass(frozen=True)
class KeywordMatch:
    term: str
    quote: str


@dataclass(frozen=True)
class RequirementMatch:
    status: RequirementResultStatus
    matches: list[KeywordMatch]
    explanation: str


def extract_keywords(description: str) -> list[str]:
    """Pull plausible skill/technology terms out of a requirement description.

    Deliberately simple: split on word boundaries (keeping characters like
    `+`, `#`, `.` that appear in real technology names), lowercase, and drop
    stopwords and very short tokens. This is inexpensive keyword extraction,
    not NLP — it will miss nuance and that is by design (see module docs on
    preliminary matching never asserting proficiency).
    """
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]*", description.lower())
    seen: list[str] = []
    for token in tokens:
        cleaned = token.strip(".-")
        if (
            cleaned
            and cleaned not in STOPWORDS
            and len(cleaned) >= MIN_KEYWORD_LENGTH
            and cleaned not in seen
        ):
            seen.append(cleaned)
    return seen


def _term_variants(term: str) -> set[str]:
    variants = {term}
    variants |= SKILL_ALIASES.get(term, set())
    for canonical, aliases in SKILL_ALIASES.items():
        if term in aliases:
            variants.add(canonical)
    return variants


def _find_in_text(term: str, text_lower: str) -> tuple[int, int] | None:
    if re.search(r"[^\w]", term):
        # Terms with symbols (c++, c#, node.js) don't play well with \b —
        # a plain substring search is good enough for these.
        index = text_lower.find(term)
        return (index, index + len(term)) if index != -1 else None

    match = re.search(rf"\b{re.escape(term)}\b", text_lower)
    return (match.start(), match.end()) if match else None


def _extract_required_years(description: str) -> int | None:
    """Pulls a minimum years-of-experience figure out of a requirement
    description ("5+ years" / "3-5 years" -> 5 / 3). None if the
    requirement doesn't state a duration at all.
    """
    match = YEARS_PATTERN.search(description)
    return int(match.group(1)) if match else None


def _years_confirmed_near(text_lower: str, span: tuple[int, int], required_years: int) -> bool:
    """Whether a years figure meeting the requirement appears near a
    keyword match, not just anywhere in the resume — "10 years of Java,
    some exposure to Python" shouldn't satisfy "5+ years of Python" just
    because a large number appears elsewhere in the document.
    """
    start = max(0, span[0] - YEARS_PROXIMITY_RADIUS)
    end = min(len(text_lower), span[1] + YEARS_PROXIMITY_RADIUS)
    window = text_lower[start:end]
    return any(int(value) >= required_years for value in YEARS_PATTERN.findall(window))


def _quote_around(text: str, start: int, end: int) -> str:
    quote_start = max(0, start - SNIPPET_RADIUS)
    quote_end = min(len(text), end + SNIPPET_RADIUS)
    prefix = "…" if quote_start > 0 else ""
    suffix = "…" if quote_end < len(text) else ""
    return f"{prefix}{text[quote_start:quote_end].strip()}{suffix}"


def match_requirement(description: str, resume_text: str) -> RequirementMatch:
    """Deterministically check a resume for explicit evidence of a requirement.

    This never returns `not_met` — the absence of a keyword match does not
    prove a candidate lacks a skill (different phrasing, synonyms, or simply
    not mentioning it explicitly are all possible). Keyword matching can
    only confirm presence, so an unmatched requirement is `unverified`, not
    a failure. See the product spec's guardrails against treating keyword
    matching as proof of proficiency or grounds for automatic rejection.
    """
    keywords = extract_keywords(description)
    text_lower = resume_text.lower()
    required_years = _extract_required_years(description)
    years_confirmed = required_years is None

    matches: list[KeywordMatch] = []
    for keyword in keywords:
        for variant in _term_variants(keyword):
            span = _find_in_text(variant, text_lower)
            if span is not None:
                matches.append(
                    KeywordMatch(term=variant, quote=_quote_around(resume_text, *span))
                )
                if required_years is not None and _years_confirmed_near(
                    text_lower, span, required_years
                ):
                    years_confirmed = True
                break

    if not keywords:
        return RequirementMatch(
            status=RequirementResultStatus.UNVERIFIED,
            matches=[],
            explanation="Could not extract a checkable keyword from this requirement's wording.",
        )

    required_matches = max(1, math.ceil(len(keywords) * MIN_KEYWORD_COVERAGE_RATIO))

    if len(matches) >= required_matches:
        terms = ", ".join(sorted({m.term for m in matches}))
        if not years_confirmed:
            return RequirementMatch(
                status=RequirementResultStatus.UNVERIFIED,
                matches=matches,
                explanation=(
                    f"Found explicit mention of: {terms}, but couldn't confirm "
                    f"{required_years}+ years of experience with it stated nearby "
                    "in the resume text. Needs manual review."
                ),
            )
        return RequirementMatch(
            status=RequirementResultStatus.MET,
            matches=matches,
            explanation=f"Found explicit mention of: {terms}.",
        )

    keyword_list = ", ".join(keywords)
    if matches:
        matched_terms = ", ".join(sorted({m.term for m in matches}))
        return RequirementMatch(
            status=RequirementResultStatus.UNVERIFIED,
            matches=matches,
            explanation=(
                f"Only partial overlap found ({matched_terms}) against this multi-part "
                f"requirement ({keyword_list}) — not enough to confirm it was met. "
                "Needs manual review."
            ),
        )

    return RequirementMatch(
        status=RequirementResultStatus.UNVERIFIED,
        matches=[],
        explanation=(
            f"No explicit mention of {keyword_list} found in the extracted resume text. "
            "This does not confirm the candidate lacks this skill — only that it "
            "wasn't stated in these exact terms. Needs manual review."
        ),
    )
