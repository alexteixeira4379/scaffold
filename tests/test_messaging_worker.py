from __future__ import annotations

import asyncio
from typing import Any

import pytest

from scaffold.messaging.worker import QueueWorkerRunner


class _FakeMessage:
    def __init__(self) -> None:
        self.queue_name = "jobs.new"
        self.correlation_id = "cid-1"
        self.read_count = 1
        self.released = False

    async def release(self, requeue: bool = True) -> None:
        self.released = bool(requeue)


class _FakeQueue:
    def __init__(self, message: _FakeMessage, stop_event: asyncio.Event) -> None:
        self._message = message
        self._stop_event = stop_event
        self._reads = 0

    async def read(self):
        self._reads += 1
        if self._reads == 1:
            return self._message
        self._stop_event.set()
        return None


@pytest.mark.asyncio
async def test_worker_releases_message_on_timeout() -> None:
    stop_event = asyncio.Event()
    message = _FakeMessage()
    queue = _FakeQueue(message, stop_event)

    async def slow_handler(_message: Any) -> None:
        await asyncio.sleep(10)

    reconnect_calls = {"count": 0}

    async def reconnect() -> None:
        reconnect_calls["count"] += 1

    runner = QueueWorkerRunner(
        queue=queue,
        handler=slow_handler,
        reconnect=reconnect,
        message_timeout_s=0.01,
        idle_sleep_s=0.01,
    )

    await runner.run(stop_event)

    assert message.released is True
    assert reconnect_calls["count"] == 0
