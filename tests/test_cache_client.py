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
