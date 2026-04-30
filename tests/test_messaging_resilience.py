from __future__ import annotations

import pytest

from scaffold.messaging.resilience import publish_with_retry, reconnect_queues


class _FakeQueue:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.published: list[dict[str, object]] = []
        self.reconnect_count = 0

    async def publish(
        self,
        body: dict[str, object],
        *,
        correlation_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("publish failed")
        self.published.append({"body": body, "correlation_id": correlation_id, "headers": headers or {}})

    async def reconnect(self) -> None:
        self.reconnect_count += 1


@pytest.mark.asyncio
async def test_publish_with_retry_recovers_after_one_failure() -> None:
    queue = _FakeQueue(fail_times=1)
    await publish_with_retry(
        queue,
        {"k": "v"},
        correlation_id="cid-1",
        max_attempts=2,
        retry_base_s=0.0,
        retry_max_s=0.0,
    )
    assert queue.reconnect_count == 1
    assert len(queue.published) == 1


@pytest.mark.asyncio
async def test_publish_with_retry_raises_after_exhaustion() -> None:
    queue = _FakeQueue(fail_times=3)
    with pytest.raises(RuntimeError, match="publish failed"):
        await publish_with_retry(
            queue,
            {"k": "v"},
            max_attempts=2,
            retry_base_s=0.0,
            retry_max_s=0.0,
        )
    assert queue.reconnect_count == 1


@pytest.mark.asyncio
async def test_reconnect_queues_reconnects_all() -> None:
    q1 = _FakeQueue()
    q2 = _FakeQueue()
    await reconnect_queues([q1, q2])
    assert q1.reconnect_count == 1
    assert q2.reconnect_count == 1
