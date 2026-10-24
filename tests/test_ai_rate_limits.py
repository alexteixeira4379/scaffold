import json
from datetime import UTC, datetime

import httpx
import pytest

from scaffold.ai.contracts import AIProviderError, ChatMessage
from scaffold.ai.groq import GroqLLM, structured_error_metadata
from scaffold.ai.rate_limits import safe_rate_limits


def test_headers_allowlist_units_and_privacy():
    headers = httpx.Headers({
        "x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "987",
        "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "20",
        "x-ratelimit-reset-requests": "1h2m3.4s", "x-ratelimit-reset-tokens": "7.66s",
        "retry-after": "93", "authorization": "PRIVATE_SECRET", "x-candidate": "PRIVATE_NAME",
    })
    result = safe_rate_limits(headers)
    assert result == {"limit_requests": 1000, "remaining_requests": 987, "limit_tokens": 8000,
                      "remaining_tokens": 20, "reset_requests_seconds": 3724,
                      "reset_tokens_seconds": 8, "retry_after_seconds": 93}
    assert "PRIVATE" not in json.dumps(result)
    error = structured_error_metadata(httpx.Response(429, headers=headers, json={"error": {"message": "PRIVATE"}}))
    assert error["retry_after_seconds"] == 93 and error["rate_limit"] == result
    assert "PRIVATE" not in json.dumps(error)


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "PRIVATE", "1sPRIVATE", "9" * 100, "1e999"])
def test_invalid_durations_and_counts_are_discarded(value):
    assert safe_rate_limits(httpx.Headers({"retry-after": value, "x-ratelimit-reset-tokens": value,
                                          "x-ratelimit-remaining-tokens": value})) == {}


def test_retry_after_http_date_and_duration_bound():
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    assert safe_rate_limits(httpx.Headers({"retry-after": "Sat, 24 Oct 2026 12:01:30 GMT"}), now=now)["retry_after_seconds"] == 90
    assert safe_rate_limits(httpx.Headers({"retry-after": "99999999"}))["retry_after_seconds"] == 604800


@pytest.mark.parametrize("status", [200, 429])
async def test_structured_boundary_preserves_numeric_limits_on_success_and_failure(monkeypatch, status):
    async def respond(request):
        return httpx.Response(status, headers={"x-ratelimit-remaining-tokens": "0", "x-ratelimit-reset-tokens": "20s", "retry-after": "120"}, json={
            "model": "test", "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "error": {"message": "private rate limit reached", "code": "rate_limit_exceeded"},
        })
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond)))
    backend = GroqLLM(api_key="PRIVATE", base_url="https://test.invalid", models={})
    call = backend.complete_structured(model="test", messages=[ChatMessage(role="user", content="private")], schema={}, max_tokens=10)
    if status == 200:
        assert (await call).rate_limit["remaining_tokens"] == 0
    else:
        with pytest.raises(AIProviderError) as error:
            await call
        assert error.value.provider_error["retry_after_seconds"] == 120
