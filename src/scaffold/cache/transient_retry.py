from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def is_transient_cache_error(exc: BaseException) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, OSError):
        errno = getattr(exc, "errno", None)
        if errno in (
            104,
            32,
            110,
            111,
        ):
            return True
    try:
        import redis.exceptions as redis_exc

        if isinstance(
            exc,
            (
                redis_exc.ConnectionError,
                redis_exc.TimeoutError,
                redis_exc.BusyLoadingError,
                redis_exc.TryAgainError,
                redis_exc.ClusterDownError,
                redis_exc.MasterDownError,
                redis_exc.MaxConnectionsError,
            ),
        ):
            return True
    except ImportError:
        pass
    return False


async def run_with_transient_retry(
    op: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    base_delay_s: float,
) -> T:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await op()
        except BaseException as exc:
            last = exc
            if attempt >= max_attempts - 1 or not is_transient_cache_error(exc):
                raise
            delay = base_delay_s * (2**attempt) * random.uniform(0.8, 1.2)
            await asyncio.sleep(delay)
    assert last is not None
    raise last
