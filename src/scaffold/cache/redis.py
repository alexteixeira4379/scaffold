from __future__ import annotations

import json
from typing import Any

from scaffold.cache.ports import JsonValue


class RedisCache:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Any | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError("redis package is required to use the cache client") from exc
        self._client = Redis.from_url(self._url, decode_responses=True)
        await self._client.ping()

    async def close(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def getdel(self, key: str) -> str | None:
        return await self._redis.getdel(key)

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        self._validate_ttl(ttl_s)
        await self._redis.set(key, value, ex=ttl_s)

    async def get_json(self, key: str) -> JsonValue | None:
        value = await self.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def set_json(self, key: str, value: JsonValue, *, ttl_s: int | None = None) -> None:
        await self.set(key, json.dumps(value, separators=(",", ":"), sort_keys=True), ttl_s=ttl_s)

    async def delete(self, key: str) -> bool:
        deleted = await self._redis.delete(key)
        return deleted > 0

    async def delete_if_value(self, key: str, expected: str) -> bool:
        script = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end"
        return bool(await self._redis.eval(script, 1, key, expected))

    async def acquire_pool_slot(self, key: str, owner: str, limit: int, ttl_s: int) -> bool:
        script = """
        local now = redis.call('TIME')
        local seconds = tonumber(now[1]) + tonumber(now[2]) / 1000000
        redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', seconds)
        if redis.call('ZSCORE', KEYS[1], ARGV[1]) then return 0 end
        if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
        redis.call('ZADD', KEYS[1], seconds + tonumber(ARGV[3]), ARGV[1])
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]) * 2)
        return 1
        """
        return bool(await self._redis.eval(script, 1, key, owner, limit, ttl_s))

    async def renew_pool_slot(self, key: str, owner: str, ttl_s: int) -> bool:
        script = """
        local now = redis.call('TIME')
        local seconds = tonumber(now[1]) + tonumber(now[2]) / 1000000
        local expiry = redis.call('ZSCORE', KEYS[1], ARGV[1])
        if not expiry or tonumber(expiry) <= seconds then return 0 end
        redis.call('ZADD', KEYS[1], seconds + tonumber(ARGV[2]), ARGV[1])
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]) * 2)
        return 1
        """
        return bool(await self._redis.eval(script, 1, key, owner, ttl_s))

    async def release_pool_slot(self, key: str, owner: str) -> bool:
        return bool(await self._redis.zrem(key, owner))

    async def exists(self, key: str) -> bool:
        found = await self._redis.exists(key)
        return found > 0

    async def expire(self, key: str, ttl_s: int) -> bool:
        self._validate_ttl(ttl_s)
        return bool(await self._redis.expire(key, ttl_s))

    async def ttl(self, key: str) -> int | None:
        ttl = await self._redis.ttl(key)
        if ttl < 0:
            return None
        return int(ttl)

    @property
    def _redis(self) -> Any:
        if self._client is None:
            raise RuntimeError("cache client is not connected")
        return self._client

    @staticmethod
    def _validate_ttl(ttl_s: int | None) -> None:
        if ttl_s is not None and ttl_s <= 0:
            raise ValueError("ttl_s must be greater than zero")
