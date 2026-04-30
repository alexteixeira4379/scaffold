from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable

from scaffold.messaging.ports import FetchedMessage
from scaffold.messaging.queue_client import QueueClient


def _default_trace_id(message: FetchedMessage) -> str:
    cid = getattr(message, "correlation_id", None)
    if isinstance(cid, str) and cid.strip():
        return cid.strip()
    return "<missing>"


class QueueWorkerRunner:
    def __init__(
        self,
        *,
        queue: QueueClient,
        handler: Callable[[FetchedMessage], Awaitable[None]],
        reconnect: Callable[[], Awaitable[None]],
        idle_sleep_s: float = 1.0,
        message_timeout_s: float = 0.0,
        logger: logging.Logger | None = None,
        trace_id: Callable[[FetchedMessage], str] = _default_trace_id,
        on_collected: Callable[[FetchedMessage], Awaitable[None] | None] | None = None,
    ) -> None:
        self._queue = queue
        self._handler = handler
        self._reconnect = reconnect
        self._idle_sleep_s = max(0.05, idle_sleep_s)
        self._message_timeout_s = max(0.0, message_timeout_s)
        self._logger = logger or logging.getLogger(__name__)
        self._trace_id = trace_id
        self._on_collected = on_collected

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                message = await self._queue.read()
            except Exception:
                self._logger.exception("failed to read message")
                await self._safe_reconnect("reconnect_after_read_failure")
                await asyncio.sleep(self._idle_sleep_s)
                continue

            if message is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._idle_sleep_s)
                except asyncio.TimeoutError:
                    pass
                continue

            traced = self._trace_id(message)
            self._logger.info(
                "collected queue=%s correlation_id=%s read_count=%s",
                message.queue_name,
                traced,
                message.read_count,
            )
            if self._on_collected is not None:
                maybe_awaitable = self._on_collected(message)
                if maybe_awaitable is not None and inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable

            try:
                if self._message_timeout_s > 0:
                    await asyncio.wait_for(self._handler(message), timeout=self._message_timeout_s)
                else:
                    await self._handler(message)
            except asyncio.TimeoutError:
                self._logger.exception(
                    "message_processing_timeout; releasing for retry correlation_id=%s timeout_s=%s",
                    traced,
                    self._message_timeout_s,
                )
                await self._safe_release(message, traced, "reconnect_after_timeout_release_failure")
            except Exception:
                self._logger.exception("unhandled error processing message; releasing for retry")
                await self._safe_release(message, traced, "reconnect_after_release_failure")

    async def _safe_release(self, message: FetchedMessage, traced: str, reconnect_err: str) -> None:
        try:
            await message.release(requeue=True)
        except Exception:
            self._logger.warning("release_failed message may redeliver correlation_id=%s", traced)
            await self._safe_reconnect(reconnect_err)

    async def _safe_reconnect(self, label: str) -> None:
        try:
            await self._reconnect()
        except Exception:
            self._logger.exception(label)
