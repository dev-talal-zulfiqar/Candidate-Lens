import httpx2
from openai import AuthenticationError, PermissionDeniedError, RateLimitError

from app.integrations.ai_provider import (
    AI_CREDITS_EXHAUSTED_MESSAGE,
    AICreditsExhaustedError,
    AIProviderError,
    _translate_openai_error,
)


def _fake_response(status_code: int) -> httpx2.Response:
    return httpx2.Response(
        status_code, request=httpx2.Request("POST", "https://api.openai.com/v1/x")
    )


def test_insufficient_quota_rate_limit_becomes_credits_exhausted():
    error = RateLimitError(
        "quota exceeded", response=_fake_response(429), body={"code": "insufficient_quota"}
    )

    translated = _translate_openai_error(error)

    assert isinstance(translated, AICreditsExhaustedError)
    assert str(translated) == AI_CREDITS_EXHAUSTED_MESSAGE


def test_ordinary_throttling_rate_limit_stays_a_generic_provider_error():
    error = RateLimitError(
        "too many requests", response=_fake_response(429), body={"code": "rate_limit_exceeded"}
    )

    translated = _translate_openai_error(error)

    assert isinstance(translated, AIProviderError)
    assert not isinstance(translated, AICreditsExhaustedError)


def test_revoked_key_authentication_error_becomes_credits_exhausted():
    error = AuthenticationError(
        "invalid api key", response=_fake_response(401), body={"code": "invalid_api_key"}
    )

    translated = _translate_openai_error(error)

    assert isinstance(translated, AICreditsExhaustedError)


def test_permission_denied_becomes_credits_exhausted():
    error = PermissionDeniedError(
        "forbidden", response=_fake_response(403), body={"code": "forbidden"}
    )

    translated = _translate_openai_error(error)

    assert isinstance(translated, AICreditsExhaustedError)


def test_credits_exhausted_is_a_subtype_of_provider_error():
    # Callers that only know about AIProviderError (e.g. the generic 503
    # handler) must still catch this without special-casing it.
    assert issubclass(AICreditsExhaustedError, AIProviderError)
