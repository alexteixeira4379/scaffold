from __future__ import annotations

from scaffold.cache.factory import create_cache_backend
from scaffold.cache.ports import CachePort, JsonValue
from scaffold.config import Settings


class CacheClient:
    def __init__(self, backend: CachePort) -> None:
        self._backend = backend

    @classmethod
    def from_settings(cls, settings: Settings) -> CacheClient:
        return cls(create_cache_backend(settings))

    async def connect(self) -> None:
        await self._backend.connect()

    async def close(self) -> None:
        await self._backend.close()

    async def get(self, key: str) -> str | None:
        return await self._backend.get(key)

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        await self._backend.set(key, value, ttl_s=ttl_s)

    async def get_json(self, key: str) -> JsonValue | None:
        return await self._backend.get_json(key)

    async def set_json(self, key: str, value: JsonValue, *, ttl_s: int | None = None) -> None:
        await self._backend.set_json(key, value, ttl_s=ttl_s)

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)

    async def exists(self, key: str) -> bool:
        return await self._backend.exists(key)

    async def expire(self, key: str, ttl_s: int) -> bool:
        return await self._backend.expire(key, ttl_s)

    async def ttl(self, key: str) -> int | None:
        return await self._backend.ttl(key)
