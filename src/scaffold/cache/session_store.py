from __future__ import annotations

from scaffold.cache.client import CacheClient
from scaffold.cache.ports import JsonValue
from scaffold.cache.sync import run_sync
from scaffold.config import Settings, get_settings


class SyncJsonSessionStore:
    def __init__(
        self,
        *,
        key: str,
        cache_client: CacheClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._key = key
        self._cache_client = cache_client
        self._settings = settings
        self._connected = False

    def healthcheck(self, *, key: str | None = None, ttl_s: int = 30) -> None:
        hc_key = key or f"{self._key}:HEALTHCHECK"

        async def _check() -> None:
            cache = await self._client()
            await cache.set(hc_key, "ok", ttl_s=ttl_s)
            value = await cache.get(hc_key)
            if value != "ok":
                raise RuntimeError("cache healthcheck returned an invalid value")
            await cache.delete(hc_key)

        run_sync(_check())

    def load(self) -> JsonValue | None:
        async def _load() -> JsonValue | None:
            cache = await self._client()
            return await cache.get_json(self._key)

        return run_sync(_load())

    def save(self, value: JsonValue, *, ttl_s: int | None = None) -> None:
        async def _save() -> None:
            cache = await self._client()
            await cache.set_json(self._key, value, ttl_s=ttl_s)

        run_sync(_save())

    def clear(self) -> None:
        async def _clear() -> None:
            cache = await self._client()
            await cache.delete(self._key)

        run_sync(_clear())

    async def _client(self) -> CacheClient:
        if self._cache_client is None:
            settings = self._settings or get_settings()
            self._cache_client = CacheClient.from_settings(settings)
        if not self._connected:
            await self._cache_client.connect()
            self._connected = True
        return self._cache_client
