from __future__ import annotations

import asyncio
from typing import Any

import pytest

from scaffold.messaging.worker import QueueWorkerRunner


class _FakeMessage:
    def __init__(self) -> None:
        self.queue_name = "job.captured"
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


@pytest.mark.asyncio
async def test_worker_runs_two_messages_independently_and_drains() -> None:
    stop = asyncio.Event()
    started = 0
    simultaneous = asyncio.Event()
    completed = []

    class Queue:
        def __init__(self):
            self.reads = 0

        async def read(self):
            self.reads += 1
            if self.reads <= 2:
                return _FakeMessage()
            stop.set()
            return None

    async def handler(message):
        nonlocal started
        started += 1
        if started == 2:
            simultaneous.set()
        await asyncio.wait_for(simultaneous.wait(), timeout=1)
        completed.append(message)

    runner = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=lambda: asyncio.sleep(0),
                               max_in_flight=2, idle_sleep_s=0.01)
    await asyncio.wait_for(runner.run(stop), timeout=2)
    assert len(completed) == 2


@pytest.mark.asyncio
async def test_worker_failure_does_not_cancel_other_delivery() -> None:
    stop = asyncio.Event()
    other_finished = asyncio.Event()
    messages = [_FakeMessage(), _FakeMessage()]

    class Queue:
        async def read(self):
            if messages:
                return messages.pop(0)
            stop.set()
            return None

    first, second = messages

    async def handler(message):
        if message is first:
            raise RuntimeError("isolated failure")
        await asyncio.sleep(0.05)
        other_finished.set()

    runner = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=lambda: asyncio.sleep(0),
                               max_in_flight=2, idle_sleep_s=0.01)
    await asyncio.wait_for(runner.run(stop), timeout=2)
    assert first.released and other_finished.is_set() and not second.released


@pytest.mark.asyncio
async def test_worker_stop_cancels_after_bounded_drain() -> None:
    stop = asyncio.Event()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class Queue:
        def __init__(self):
            self.sent = False

        async def read(self):
            if not self.sent:
                self.sent = True
                return _FakeMessage()
            await stop.wait()
            return None

    async def handler(_message):
        started.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    runner = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=lambda: asyncio.sleep(0),
                               max_in_flight=1, drain_timeout_s=0.02)
    task = asyncio.create_task(runner.run(stop))
    await started.wait()
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_reconnect_waits_for_other_delivery_to_finish() -> None:
    stop = asyncio.Event()
    second_started = asyncio.Event()
    second_finish = asyncio.Event()
    reconnect_done = asyncio.Event()

    class FailedRelease(_FakeMessage):
        async def release(self, requeue=True):
            raise ConnectionError("channel closed")

    first, second = FailedRelease(), _FakeMessage()

    class Queue:
        def __init__(self):
            self.messages = [first, second]

        async def read(self):
            return self.messages.pop(0) if self.messages else None

    async def handler(message):
        if message is first:
            await second_started.wait()
            raise RuntimeError("first failed")
        second_started.set()
        await second_finish.wait()

    async def reconnect():
        reconnect_done.set()
        stop.set()

    runner = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=reconnect,
                               max_in_flight=2, idle_sleep_s=0.01)
    task = asyncio.create_task(runner.run(stop))
    await asyncio.wait_for(second_started.wait(), timeout=1)
    await asyncio.sleep(0.05)
    assert not reconnect_done.is_set()
    second_finish.set()
    await asyncio.wait_for(task, timeout=2)
    assert reconnect_done.is_set()
