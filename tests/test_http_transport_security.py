import asyncio

import pytest
from fastapi import HTTPException

from scaffold.auth import get_jwt_secret, get_service_api_key
from scaffold.security import BodyLimitMiddleware, validate_auth_configuration, validate_secret


@pytest.mark.parametrize("name", ["JWT_SECRET", "SERVICE_API_KEY"])
@pytest.mark.parametrize("value", [None, "", "change-me", "internal-key", "change-me-256-bit-secret"])
def test_missing_or_example_auth_configuration_fails_closed(monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(HTTPException) as error:
        (get_jwt_secret if name == "JWT_SECRET" else get_service_api_key)()
    assert error.value.status_code == 503


def test_production_secret_strength_and_startup_validation(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "production-test")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("SERVICE_API_KEY", "k" * 40)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_auth_configuration()
    monkeypatch.setenv("JWT_SECRET", "j" * 40)
    validate_auth_configuration()
    assert validate_secret("test-fixture", "test", production=False) == "test-fixture"


async def run_request(chunks, headers=(), *, timeout=1, path="/", limits=None, delay=0):
    received = []
    responses = []
    incoming = iter(chunks)

    async def receive():
        if delay:
            await asyncio.sleep(delay)
        return next(incoming)

    async def send(message):
        responses.append(message)

    async def app(scope, receive, send):
        while True:
            message = await receive()
            received.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = BodyLimitMiddleware(app, max_bytes=5, path_limits=limits,
                                     read_timeout_seconds=timeout)
    await middleware({"type": "http", "path": path, "headers": list(headers)}, receive, send)
    return responses[0]["status"], b"".join(received)


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
async def test_real_chunk_bytes_rejected_before_application(headers):
    chunks = [{"type": "http.request", "body": b"123", "more_body": True},
              {"type": "http.request", "body": b"456", "more_body": False}]
    assert await run_request(chunks, headers) == (413, b"")


@pytest.mark.asyncio
async def test_exact_limit_replays_all_chunks_and_path_override():
    chunks = [{"type": "http.request", "body": b"12", "more_body": True},
              {"type": "http.request", "body": b"345", "more_body": False}]
    assert await run_request(chunks) == (204, b"12345")
    assert await run_request(chunks, path="/small", limits={"/small": 4}) == (413, b"")


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [b"-1", b"bad", b"99999999999999"])
async def test_declared_size_rejected_without_reading(header):
    status, received = await run_request([], [(b"content-length", header)])
    assert status == (413 if header.isdigit() else 400)
    assert received == b""


@pytest.mark.asyncio
async def test_slow_body_times_out_before_application():
    assert await run_request([], timeout=0.001, delay=0.1) == (408, b"")
