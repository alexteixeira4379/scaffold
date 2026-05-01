from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from scaffold.cache.client import CacheClient
from scaffold.cache.ports import JsonValue
from scaffold.cache.sync import run_sync
from scaffold.cache.transient_retry import run_with_transient_retry
from scaffold.config import (
    DEFAULT_CACHE_MAX_RETRIES,
    DEFAULT_CACHE_RETRY_BASE_DELAY_S,
    Settings,
    get_settings,
)

T = TypeVar("T")


class SyncJsonSessionStore:
    def __init__(
        self,
        *,
        key: str,
        cache_client: CacheClient | None = None,
        settings: Settings | None = None,
        cache_max_retries: int | None = None,
        cache_retry_base_delay_s: float | None = None,
    ) -> None:
        self._key = key
        self._cache_client = cache_client
        self._settings = settings
        self._cache_max_retries = cache_max_retries
        self._cache_retry_base_delay_s = cache_retry_base_delay_s
        self._connected = False

    def _retry_params(self) -> tuple[int, float]:
        if self._cache_max_retries is not None and self._cache_retry_base_delay_s is not None:
            return (self._cache_max_retries, self._cache_retry_base_delay_s)
        if self._cache_client is not None:
            settings = self._settings
            if settings is not None:
                return (
                    self._cache_max_retries
                    if self._cache_max_retries is not None
                    else settings.cache_max_retries,
                    self._cache_retry_base_delay_s
                    if self._cache_retry_base_delay_s is not None
                    else settings.cache_retry_base_delay_s,
                )
            return (
                self._cache_max_retries
                if self._cache_max_retries is not None
                else DEFAULT_CACHE_MAX_RETRIES,
                self._cache_retry_base_delay_s
                if self._cache_retry_base_delay_s is not None
                else DEFAULT_CACHE_RETRY_BASE_DELAY_S,
            )
        settings = self._settings or get_settings()
        return (
            self._cache_max_retries
            if self._cache_max_retries is not None
            else settings.cache_max_retries,
            self._cache_retry_base_delay_s
            if self._cache_retry_base_delay_s is not None
            else settings.cache_retry_base_delay_s,
        )

    def _run_with_retry(self, op: Callable[[], Awaitable[T]]) -> T:
        max_retries, base_delay = self._retry_params()
        return run_sync(
            run_with_transient_retry(op, max_attempts=max_retries, base_delay_s=base_delay)
        )

    def healthcheck(self, *, key: str | None = None, ttl_s: int = 30) -> None:
        hc_key = key or f"{self._key}:HEALTHCHECK"

        async def _check() -> None:
            cache = await self._client()
            await cache.set(hc_key, "ok", ttl_s=ttl_s)
            value = await cache.get(hc_key)
            if value != "ok":
                raise RuntimeError("cache healthcheck returned an invalid value")
            await cache.delete(hc_key)

        self._run_with_retry(lambda: _check())

    def load(self) -> JsonValue | None:
        async def _load() -> JsonValue | None:
            cache = await self._client()
            return await cache.get_json(self._key)

        return self._run_with_retry(lambda: _load())

    def save(self, value: JsonValue, *, ttl_s: int | None = None) -> None:
        async def _save() -> None:
            cache = await self._client()
            await cache.set_json(self._key, value, ttl_s=ttl_s)

        self._run_with_retry(lambda: _save())

    def clear(self) -> None:
        async def _clear() -> None:
            cache = await self._client()
            await cache.delete(self._key)

        self._run_with_retry(lambda: _clear())

    async def _client(self) -> CacheClient:
        if self._cache_client is None:
            settings = self._settings or get_settings()
            self._cache_client = CacheClient.from_settings(settings)
        if not self._connected:
            await self._cache_client.connect()
            self._connected = True
        return self._cache_client
