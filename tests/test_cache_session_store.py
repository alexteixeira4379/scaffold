from __future__ import annotations

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
