from __future__ import annotations

import asyncio

import pytest
import redis.exceptions

from scaffold.cache.session_store import SyncJsonSessionStore


class _FakeCacheClient:
    def __init__(self) -> None:
        self.connected = False
        self.data: dict[str, object] = {}
        self.deleted: set[str] = set()

    async def connect(self) -> None:
        self.connected = True

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        value = self.data.get(key)
        return value if isinstance(value, str) else None

    async def set_json(self, key: str, value, *, ttl_s: int | None = None) -> None:
        self.data[key] = value

    async def get_json(self, key: str):
        return self.data.get(key)

    async def delete(self, key: str) -> bool:
        self.deleted.add(key)
        self.data.pop(key, None)
        return True


def test_sync_json_session_store_load_save_clear_and_healthcheck() -> None:
    cache = _FakeCacheClient()
    store = SyncJsonSessionStore(key="SESSION_KEY", cache_client=cache)

    store.healthcheck()
    store.save({"cookies": [{"name": "li_at"}]})
    loaded = store.load()
    store.clear()

    assert cache.connected is True
    assert loaded == {"cookies": [{"name": "li_at"}]}
    assert "SESSION_KEY:HEALTHCHECK" in cache.deleted
    assert "SESSION_KEY" in cache.deleted


class _FlakyJsonCacheClient(_FakeCacheClient):
    def __init__(self, get_json_failures: int) -> None:
        super().__init__()
        self._get_json_failures_left = get_json_failures

    async def get_json(self, key: str):
        if self._get_json_failures_left > 0:
            self._get_json_failures_left -= 1
            raise redis.exceptions.ConnectionError("Connection reset by peer")
        return self.data.get(key)


def test_sync_json_session_store_retries_transient_get_json_failures() -> None:
    cache = _FlakyJsonCacheClient(get_json_failures=2)
    store = SyncJsonSessionStore(
        key="SESSION_KEY",
        cache_client=cache,
        cache_max_retries=5,
        cache_retry_base_delay_s=0.01,
    )
    cache.data["SESSION_KEY"] = {"cookies": [{"name": "li_at"}]}
    loaded = store.load()
    assert loaded == {"cookies": [{"name": "li_at"}]}
    assert cache._get_json_failures_left == 0


class _AlwaysFailingGetJsonClient(_FakeCacheClient):
    async def get_json(self, key: str):
        raise redis.exceptions.ConnectionError("persistent failure")


def test_sync_json_session_store_propagates_after_retry_exhaustion() -> None:
    cache = _AlwaysFailingGetJsonClient()
    store = SyncJsonSessionStore(
        key="SESSION_KEY",
        cache_client=cache,
        cache_max_retries=3,
        cache_retry_base_delay_s=0.01,
    )
    with pytest.raises(redis.exceptions.ConnectionError):
        store.load()


class _LoopBoundCacheClient:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self.connected = False
        self.data: dict[str, object] = {}

    def _check_loop(self) -> None:
        current = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = current
            return
        if self._loop is not current:
            raise RuntimeError("cache client reused on a different event loop")

    async def connect(self) -> None:
        self._check_loop()
        self.connected = True

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        self._check_loop()
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        self._check_loop()
        value = self.data.get(key)
        return value if isinstance(value, str) else None

    async def set_json(self, key: str, value, *, ttl_s: int | None = None) -> None:
        self._check_loop()
        self.data[key] = value

    async def get_json(self, key: str):
        self._check_loop()
        return self.data.get(key)

    async def delete(self, key: str) -> bool:
        self._check_loop()
        self.data.pop(key, None)
        return True


@pytest.mark.asyncio
async def test_sync_json_session_store_reuses_cache_client_on_stable_loop() -> None:
    cache = _LoopBoundCacheClient()
    store = SyncJsonSessionStore(key="SESSION_KEY", cache_client=cache)

    store.save({"cookies": [{"name": "li_at"}]})
    loaded = store.load()
    store.clear()

    assert cache.connected is True
    assert loaded == {"cookies": [{"name": "li_at"}]}
