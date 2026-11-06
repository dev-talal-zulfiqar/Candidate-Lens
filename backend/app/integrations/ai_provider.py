import re
import time
from dataclasses import dataclass
from typing import Protocol

from openai import (
    AuthenticationError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from app.integrations.ai_prompt import (
    PROMPT_VERSION,
    AIEvaluationRequest,
    RequirementInferenceRequest,
    build_messages,
    build_requirement_inference_messages,
)
from app.integrations.ai_schemas import (
    AIEvaluationResponse,
    NoteworthyStrength,
    RequirementAssessment,
    RequirementInferenceResponse,
    RequirementSuggestion,
)
from app.models.enums import RequirementResultStatus
from app.services.preliminary_matching import match_requirement

ELLIPSIS = "…"


def _exact_quote(quote: str) -> str:
    """preliminary_matching's quotes are decorated with "…" for display when
    truncated — strip that back off so the result is a real, exact
    substring of the resume text, suitable for evidence verification.
    """
    return quote.strip(ELLIPSIS)


def _strength_description(requirement_description: str, quote: str) -> str:
    """Builds a per-candidate strength description. Interpolating the
    candidate's own matched quote (not just the requirement text) keeps this
    from being byte-identical across every candidate who meets the same
    requirement.
    """
    snippet = quote if len(quote) <= 80 else quote[:77].rstrip() + ELLIPSIS
    return f'Evidence of {requirement_description}: "{snippet}"'

__all__ = [
    "PROMPT_VERSION",
    "AIEvaluationRequest",
    "AIProvider",
    "AIProviderError",
    "AICreditsExhaustedError",
    "AI_CREDITS_EXHAUSTED_MESSAGE",
    "AICallResult",
    "AIUsage",
    "MockAIProvider",
    "OpenAIProvider",
]

# Stable, user-facing text for the one failure mode the frontend singles out
# for its own toast — this exact string is what the UI matches against (in
# the evaluation's error_message, or the HTTP error body) to decide whether
# to show "contact your admin" rather than a generic retry message.
AI_CREDITS_EXHAUSTED_MESSAGE = "AI credits exhausted — contact your admin."


class AIProviderError(Exception):
    """Raised when a provider call fails — network, auth, rate limit, or an
    unparseable response. Callers must treat this as a failed evaluation,
    never fall back to a fabricated successful one.
    """


class AICreditsExhaustedError(AIProviderError):
    """The configured OpenAI account is out of quota/credits, or the API key
    has been revoked — an operations problem, not a transient one. Distinct
    from AIProviderError so callers can surface it differently (the
    hiring manager can't fix this by retrying; an admin has to).
    """


@dataclass(frozen=True)
class AIUsage:
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None


@dataclass(frozen=True)
class AICallResult:
    response: AIEvaluationResponse
    model_version: str
    usage: AIUsage
    duration_ms: int


class AIProvider(Protocol):
    def evaluate(self, request: AIEvaluationRequest) -> AICallResult: ...
    def infer_requirements(
        self, request: RequirementInferenceRequest
    ) -> list[RequirementSuggestion]: ...


# Markdown bullets, plus the unicode bullet characters and dashes that a
# paste from a webpage or Word/Google Docs commonly turns list items into
# once the original markup is stripped away.
_BULLET_PATTERN = re.compile(r"^\s*(?:[-*+•●▪‣◦·–—]|\d+[.)])\s+(.+)$")
_HASH_HEADING_PATTERN = re.compile(r"^\s*#{1,6}\s*(.+)$")
# A short bare label line like "Requirements:" / "Nice to have:" — the
# colon variant only matches when there's nothing but the label on the
# line, so "Experience: 5 years" (a real requirement, not a section
# header) is correctly left alone.
_LABEL_HEADING_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /&,'\-]{1,40}):\s*$")
# Most real job postings style section headers with bold/larger text, not
# a trailing colon — once pasted as plain text that styling is gone and
# "Requirements" is just a bare short line indistinguishable from a short
# requirement by punctuation alone. Match against known header phrases
# instead of guessing from shape.
_KNOWN_HEADING_PHRASES = frozenset(
    {
        "requirements", "qualifications", "responsibilities", "the role",
        "about the role", "about you", "about us", "about the team",
        "about the company", "who you are", "who we are", "overview",
        "role overview", "summary", "skills", "key skills",
        "minimum qualifications", "basic qualifications",
        "preferred qualifications", "must have", "must-haves",
        "nice to have", "nice-to-haves", "bonus points", "bonus",
        "benefits", "perks", "what you'll do", "what you will do",
        "what we're looking for", "what you'll bring", "why join us",
    }
)
# Generic opening-paragraph phrasing that's never itself a discrete,
# checkable requirement, even though it can be short enough to otherwise
# pass the plain-line length filter.
_FLUFF_PREFIXES = (
    "we're looking for", "we are looking for", "join our team", "join us",
)
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_PREFERRED_HEADING_HINTS = ("preferred", "nice to have", "nice-to-have", "bonus", "plus")
_MAX_INFERRED_REQUIREMENTS = 8
_MIN_LINE_LENGTH = 8
_MAX_LINE_LENGTH = 300


def _weight_for(category: str) -> float:
    return 2.0 if category == "mandatory" else 1.0


def _category_for_heading(heading_text: str) -> str:
    lowered = heading_text.lower()
    return "preferred" if any(hint in lowered for hint in _PREFERRED_HEADING_HINTS) else "mandatory"


def _bare_heading_text(line: str) -> str | None:
    """Catches a section-header line with no markup at all — just its text
    matching a known JD heading phrase, optionally with a trailing colon.
    """
    candidate = line.rstrip(":").strip().lower()
    return candidate if candidate in _KNOWN_HEADING_PHRASES else None


def _is_fluff_line(line: str) -> bool:
    lowered = line.lower()
    return any(lowered.startswith(prefix) for prefix in _FLUFF_PREFIXES)


def _extract_from_bullets(description_md: str) -> list[RequirementSuggestion]:
    """Primary pass: real bullet lists, grouped under whichever heading
    (Markdown or a bare "Label:" line) they fall under. Lines that are
    neither a recognized heading nor a recognized bullet are ignored here
    — e.g. a plain description paragraph sitting above the real bullets.
    """
    suggestions: list[RequirementSuggestion] = []
    category = "mandatory"

    for raw_line in description_md.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading_match = _HASH_HEADING_PATTERN.match(line) or _LABEL_HEADING_PATTERN.match(line)
        if heading_match:
            category = _category_for_heading(heading_match.group(1))
            continue
        bare_heading = _bare_heading_text(line)
        if bare_heading is not None:
            category = _category_for_heading(bare_heading)
            continue

        bullet_match = _BULLET_PATTERN.match(line)
        if not bullet_match:
            continue

        text = bullet_match.group(1).strip()
        if not text:
            continue
        suggestions.append(
            RequirementSuggestion(
                description=text[:200], category=category, weight=_weight_for(category)
            )
        )
        if len(suggestions) >= _MAX_INFERRED_REQUIREMENTS:
            break

    return suggestions


def _extract_from_plain_lines(description_md: str) -> list[RequirementSuggestion]:
    """Fallback for JDs with no recognizable bullet markup at all — plain
    text pasted one requirement per line. Skips heading lines (Markdown,
    "Label:", or a bare known heading phrase — same recognition as the
    bullets pass, so "Nice to have" still switches category here too),
    generic opening-paragraph fluff, and lines too short/long to plausibly
    be a single requirement — rather than treating the JD's own title or
    intro line as "the requirement" (the bug this fallback chain replaces).
    """
    suggestions: list[RequirementSuggestion] = []
    category = "mandatory"

    for raw_line in description_md.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading_match = _HASH_HEADING_PATTERN.match(line) or _LABEL_HEADING_PATTERN.match(line)
        if heading_match:
            category = _category_for_heading(heading_match.group(1))
            continue
        bare_heading = _bare_heading_text(line)
        if bare_heading is not None:
            category = _category_for_heading(bare_heading)
            continue

        if _is_fluff_line(line):
            continue
        if not (_MIN_LINE_LENGTH <= len(line) <= _MAX_LINE_LENGTH):
            continue
        suggestions.append(
            RequirementSuggestion(
                description=line[:200], category=category, weight=_weight_for(category)
            )
        )
        if len(suggestions) >= _MAX_INFERRED_REQUIREMENTS:
            break
    return suggestions


def _extract_from_sentences(description_md: str) -> list[RequirementSuggestion]:
    """Last-resort fallback for one unbroken paragraph with no line breaks
    at all — split on sentence boundaries instead of grabbing just the
    first sentence (which, same problem as the first-line fallback it
    replaces, is often a title or summary, not a requirement).
    """
    suggestions: list[RequirementSuggestion] = []
    for sentence in _SENTENCE_SPLIT_PATTERN.split(description_md.strip()):
        text = sentence.strip()
        if not (_MIN_LINE_LENGTH <= len(text) <= _MAX_LINE_LENGTH):
            continue
        suggestions.append(
            RequirementSuggestion(description=text[:200], category="mandatory", weight=1.0)
        )
        if len(suggestions) >= _MAX_INFERRED_REQUIREMENTS:
            break
    return suggestions


def _mock_infer_requirements(description_md: str) -> list[RequirementSuggestion]:
    """Deterministically turn a job description into draft requirements,
    with no AI call. Tries, in order: a real bullet list (Markdown or
    pasted-plain-text bullets); one requirement per line for plain text
    with genuine line-per-item structure; sentence splitting for a single
    unbroken paragraph (or whatever plain-line splitting didn't use).
    Always returns at least one usable draft requirement.
    """
    bullets = _extract_from_bullets(description_md)
    if bullets:
        return bullets

    # Plain line-per-requirement splitting only makes sense when there's
    # genuinely more than one line — a single long line is a paragraph,
    # not a list, and belongs to the sentence-splitting fallback instead.
    non_blank_lines = [line for line in description_md.splitlines() if line.strip()]
    if len(non_blank_lines) > 1:
        plain_lines = _extract_from_plain_lines(description_md)
        if plain_lines:
            return plain_lines

    sentences = _extract_from_sentences(description_md)
    if sentences:
        return sentences

    first_line = next(
        (line.strip() for line in description_md.splitlines() if line.strip()),
        "Relevant experience as described in the job description",
    )
    return [RequirementSuggestion(description=first_line[:200], category="mandatory", weight=1.0)]


class MockAIProvider:
    """Deterministic, credential-free provider for local development and
    tests. Reuses the same keyword-matching engine as preliminary evaluation
    so every piece of evidence it returns is genuinely grounded in the
    resume text — never fabricated — while being unmistakably labeled as a
    mock via its model_version and uncertainty_notes.
    """

    MODEL_VERSION = "mock-deterministic-v1"

    def evaluate(self, request: AIEvaluationRequest) -> AICallResult:
        start = time.monotonic()

        assessments: list[RequirementAssessment] = []
        strengths: list[NoteworthyStrength] = []
        follow_up_questions: list[str] = []

        for item in request.requirements:
            match = match_requirement(item.description, request.resume_text)
            assessments.append(
                RequirementAssessment(
                    requirement_key=item.key,
                    status=match.status.value,
                    explanation=match.explanation,
                    evidence_quotes=[_exact_quote(m.quote) for m in match.matches],
                )
            )
            if match.status == RequirementResultStatus.MET and len(strengths) < 2:
                quote = _exact_quote(match.matches[0].quote)
                strengths.append(
                    NoteworthyStrength(
                        description=_strength_description(item.description, quote),
                        evidence_quote=quote,
                    )
                )
            elif match.status == RequirementResultStatus.UNVERIFIED and len(
                follow_up_questions
            ) < 4:
                follow_up_questions.append(
                    f"Can you describe your experience with: {item.description}?"
                )

        response = AIEvaluationResponse(
            requirement_assessments=assessments,
            strengths=strengths,
            follow_up_questions=follow_up_questions,
            uncertainty_notes=(
                "This is a deterministic mock evaluation for local development and testing — "
                "no real AI model was called, and these findings are produced by the same "
                "keyword-matching engine as preliminary evaluation."
            ),
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return AICallResult(
            response=response,
            model_version=self.MODEL_VERSION,
            usage=AIUsage(input_tokens=None, output_tokens=None, cached_input_tokens=None),
            duration_ms=duration_ms,
        )

    def infer_requirements(
        self, request: RequirementInferenceRequest
    ) -> list[RequirementSuggestion]:
        return _mock_infer_requirements(request.description_md)


def _translate_openai_error(error: OpenAIError) -> AIProviderError:
    """Classify an OpenAI SDK error into our own exception hierarchy.

    `insufficient_quota` is OpenAI's code for "this account is out of
    billing credits" — it arrives as a RateLimitError (429) alongside
    ordinary throttling, which is why it needs the `.code` check rather
    than just catching RateLimitError. A revoked/invalid key surfaces as
    AuthenticationError/PermissionDeniedError instead; from the hiring
    manager's point of view both are the same actionable problem ("AI is
    down, contact an admin"), so both map to the same exception.
    """
    if isinstance(error, RateLimitError) and error.code == "insufficient_quota":
        return AICreditsExhaustedError(AI_CREDITS_EXHAUSTED_MESSAGE)
    if isinstance(error, (AuthenticationError, PermissionDeniedError)):
        return AICreditsExhaustedError(AI_CREDITS_EXHAUSTED_MESSAGE)
    return AIProviderError(f"OpenAI request failed: {error}")


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float):
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model

    def evaluate(self, request: AIEvaluationRequest) -> AICallResult:
        messages = build_messages(request)
        start = time.monotonic()
        try:
            completion = self._client.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=AIEvaluationResponse,
            )
        except OpenAIError as error:
            raise _translate_openai_error(error) from error
        duration_ms = int((time.monotonic() - start) * 1000)

        message = completion.choices[0].message
        if message.refusal:
            raise AIProviderError(f"Model refused to respond: {message.refusal}")
        if message.parsed is None:
            raise AIProviderError("Model did not return a parseable structured response")

        usage = completion.usage
        cached_tokens = (
            usage.prompt_tokens_details.cached_tokens
            if usage and usage.prompt_tokens_details
            else None
        )
        return AICallResult(
            response=message.parsed,
            model_version=self._model,
            usage=AIUsage(
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None,
                cached_input_tokens=cached_tokens,
            ),
            duration_ms=duration_ms,
        )

    def infer_requirements(
        self, request: RequirementInferenceRequest
    ) -> list[RequirementSuggestion]:
        messages = build_requirement_inference_messages(request)
        try:
            completion = self._client.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=RequirementInferenceResponse,
            )
        except OpenAIError as error:
            raise _translate_openai_error(error) from error

        message = completion.choices[0].message
        if message.refusal:
            raise AIProviderError(f"Model refused to respond: {message.refusal}")
        if message.parsed is None:
            raise AIProviderError("Model did not return a parseable structured response")
        return message.parsed.requirements


def build_ai_provider(
    *, provider_name: str, openai_api_key: str | None, openai_model: str, timeout_seconds: float
) -> AIProvider:
    if provider_name == "mock":
        return MockAIProvider()
    if provider_name == "openai":
        if not openai_api_key:
            raise AIProviderError(
                "AI_PROVIDER is set to 'openai' but OPENAI_API_KEY is not configured"
            )
        return OpenAIProvider(
            api_key=openai_api_key, model=openai_model, timeout_seconds=timeout_seconds
        )
    raise AIProviderError(f"Unknown AI provider: {provider_name!r}")
