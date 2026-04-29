from __future__ import annotations

import json
from time import monotonic

from scaffold.cache.ports import JsonValue


class InMemoryCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float | None]] = {}
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def get(self, key: str) -> str | None:
        record = self._get_record(key)
        if record is None:
            return None
        value, _expires_at = record
        return value

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        self._values[key] = (value, self._expires_at(ttl_s))

    async def get_json(self, key: str) -> JsonValue | None:
        value = await self.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def set_json(self, key: str, value: JsonValue, *, ttl_s: int | None = None) -> None:
        await self.set(key, json.dumps(value, separators=(",", ":"), sort_keys=True), ttl_s=ttl_s)

    async def delete(self, key: str) -> bool:
        existed = self._get_record(key) is not None
        self._values.pop(key, None)
        return existed

    async def exists(self, key: str) -> bool:
        return self._get_record(key) is not None

    async def expire(self, key: str, ttl_s: int) -> bool:
        record = self._get_record(key)
        if record is None:
            return False
        value, _expires_at = record
        self._values[key] = (value, self._expires_at(ttl_s))
        return True

    async def ttl(self, key: str) -> int | None:
        record = self._get_record(key)
        if record is None:
            return None
        _value, expires_at = record
        if expires_at is None:
            return None
        return max(0, int(expires_at - monotonic()))

    def _get_record(self, key: str) -> tuple[str, float | None] | None:
        record = self._values.get(key)
        if record is None:
            return None
        _value, expires_at = record
        if expires_at is not None and expires_at <= monotonic():
            self._values.pop(key, None)
            return None
        return record

    @staticmethod
    def _expires_at(ttl_s: int | None) -> float | None:
        if ttl_s is None:
            return None
        if ttl_s <= 0:
            raise ValueError("ttl_s must be greater than zero")
        return monotonic() + ttl_s
