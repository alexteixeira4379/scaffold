import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from scaffold.auth import TokenService, verify_candidate_access, verify_jwt, verify_jwt_or_service
from scaffold.cache import CacheClient, InMemoryCache


@pytest.mark.asyncio
async def test_all_shared_guards_reject_revoked_refresh_and_cross_candidate_tokens(monkeypatch):
    secret = "test-secret-that-is-at-least-32-bytes"
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("SERVICE_API_KEY", "private-service-key")
    app = FastAPI()
    cache = CacheClient(InMemoryCache())
    app.state.cache = cache
    service = TokenService(secret)

    @app.get("/user")
    def user(auth=Depends(verify_jwt)):
        return {"candidate_id": auth.candidate_id}

    @app.get("/mixed")
    def mixed(auth=Depends(verify_jwt_or_service)):
        return {"candidate_id": auth.candidate_id}

    @app.get("/candidates/{candidate_id}")
    def candidate(candidate_id: int, auth=Depends(verify_candidate_access)):
        return {"candidate_id": auth.candidate_id}

    access, jti, ttl = service.create_access_token(42)
    refresh, _, _ = service.create_refresh_token(42)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        for path in ["/user", "/mixed", "/candidates/42"]:
            assert (
                await client.get(path, headers={"Authorization": f"Bearer {access}"})
            ).status_code == 200
            assert (
                await client.get(path, headers={"Authorization": f"Bearer {refresh}"})
            ).status_code == 401
        assert (
            await client.get("/candidates/43", headers={"Authorization": f"Bearer {access}"})
        ).status_code == 403
        await service.blacklist_token(cache, jti, ttl)
        for path in ["/user", "/mixed", "/candidates/42"]:
            assert (
                await client.get(path, headers={"Authorization": f"Bearer {access}"})
            ).status_code == 401
        assert (
            await client.get("/candidates/43", headers={"X-Service-Key": "private-service-key"})
        ).status_code == 200
        assert (
            await client.get("/user", headers={"X-Service-Key": "private-service-key"})
        ).status_code == 401


@pytest.mark.asyncio
async def test_cache_outage_fails_closed(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-at-least-32-bytes")
    app = FastAPI()
    app.state.cache = AsyncMock()
    app.state.cache.exists.side_effect = ConnectionError("unavailable")

    @app.get("/user")
    def user(auth=Depends(verify_jwt)):
        return {}

    access, _, _ = TokenService("test-secret-that-is-at-least-32-bytes").create_access_token(42)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (
            await client.get("/user", headers={"Authorization": f"Bearer {access}"})
        ).status_code == 503
