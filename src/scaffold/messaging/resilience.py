from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Iterable

from scaffold.messaging.queue_client import QueueClient


async def reconnect_queue(queue: QueueClient) -> None:
    await queue.reconnect()


async def reconnect_queues(queues: Iterable[QueueClient]) -> None:
    await asyncio.gather(*(queue.reconnect() for queue in queues))


async def publish_with_retry(
    queue: QueueClient,
    body: dict[str, object],
    *,
    correlation_id: str | None = None,
    headers: dict[str, str] | None = None,
    reconnect: Callable[[], Awaitable[None]] | None = None,
    max_attempts: int | None = None,
    retry_base_s: float | None = None,
    retry_max_s: float | None = None,
) -> None:
    attempts = max(1, int(max_attempts if max_attempts is not None else _read_int("MQ_PUBLISH_MAX_ATTEMPTS", 8)))
    base = max(
        0.0,
        float(retry_base_s if retry_base_s is not None else _read_float("MQ_PUBLISH_RETRY_BASE_S", 0.45)),
    )
    ceiling = max(
        0.0,
        float(retry_max_s if retry_max_s is not None else _read_float("MQ_PUBLISH_RETRY_MAX_S", 30.0)),
    )
    delay = base
    last_exc: BaseException | None = None
    reconnect_cb = reconnect or (lambda: queue.reconnect())

    for attempt in range(attempts):
        try:
            if headers is None:
                await queue.publish(body, correlation_id=correlation_id)
            else:
                await queue.publish(body, correlation_id=correlation_id, headers=headers)
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= attempts:
                break
            await reconnect_cb()
            await asyncio.sleep(min(delay, ceiling))
            delay = min(ceiling, delay * 2 if delay > 0 else base if base > 0 else 0)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("publish exhausted")


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default
