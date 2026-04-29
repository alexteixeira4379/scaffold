from __future__ import annotations

from scaffold.cache.ports import CachePort
from scaffold.cache.redis import RedisCache
from scaffold.config import Settings


def create_cache_backend(settings: Settings) -> CachePort:
    if not settings.cache_url:
        raise ValueError("cache_url is required to create a cache client")
    return RedisCache(settings.cache_url)
