import pytest

from scaffold.cache import CacheClient, InMemoryCache, create_cache_backend
from scaffold.cache.redis import RedisCache
from scaffold.config import Settings


@pytest.mark.asyncio
async def test_cache_client_reads_and_writes_strings() -> None:
    cache = CacheClient(InMemoryCache())

    await cache.connect()
    await cache.set("candidate:1", "ready")

    assert await cache.get("candidate:1") == "ready"
    assert await cache.exists("candidate:1") is True
    assert await cache.delete("candidate:1") is True
    assert await cache.get("candidate:1") is None
    await cache.close()


@pytest.mark.asyncio
async def test_cache_client_reads_and_writes_json() -> None:
    cache = CacheClient(InMemoryCache())

    await cache.connect()
    await cache.set_json("job:1", {"id": 1, "tags": ["python", "remote"]}, ttl_s=60)

    assert await cache.get_json("job:1") == {"id": 1, "tags": ["python", "remote"]}
    assert await cache.ttl("job:1") is not None
    assert await cache.expire("job:1", 120) is True
    await cache.close()


def test_cache_backend_from_settings_uses_cache_url() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "cache_url": "redis://localhost:6379/0",
        },
    )

    backend = create_cache_backend(settings)

    assert isinstance(backend, RedisCache)


def test_cache_backend_requires_cache_url() -> None:
    settings = Settings.model_validate({"database_url": "mysql+asyncmy://u:p@localhost:3306/db"})

    with pytest.raises(ValueError, match="cache_url is required"):
        create_cache_backend(settings)


@pytest.mark.asyncio
async def test_getdel_has_one_winner_and_honors_expiry(monkeypatch):
    import asyncio

    backend = InMemoryCache()
    cache = CacheClient(backend)
    await cache.set("one-use", "42", ttl_s=10)
    results = await asyncio.gather(*(cache.getdel("one-use") for _ in range(20)))
    assert results.count("42") == 1
    assert results.count(None) == 19
    await cache.set("expired", "42", ttl_s=1)
    monkeypatch.setattr("scaffold.cache.memory.monotonic", lambda: float("inf"))
    assert await cache.getdel("expired") is None


@pytest.mark.asyncio
async def test_redis_consumes_with_single_getdel_command():
    from unittest.mock import AsyncMock

    backend = RedisCache("redis://unused")
    backend._client = AsyncMock()
    backend._client.getdel.return_value = "42"
    assert await CacheClient(backend).getdel("token") == "42"
    backend._client.getdel.assert_awaited_once_with("token")
    backend._client.get.assert_not_awaited()
    backend._client.delete.assert_not_awaited()
