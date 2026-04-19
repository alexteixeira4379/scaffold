import asyncio

import pytest

from scaffold.messaging.contracts import OutboundMessage, QueueSubscription
from scaffold.messaging.memory import InMemoryMessaging
from scaffold.messaging.ports import ConsumedEnvelope


@pytest.mark.asyncio
async def test_memory_publish_consume_ack() -> None:
    bus = InMemoryMessaging()
    await bus.connect()
    received: list[object] = []
    done = asyncio.Event()

    async def handler(env: ConsumedEnvelope) -> None:
        received.append(env.body)
        await env.ack()
        done.set()

    consumer = asyncio.create_task(
        bus.consume(QueueSubscription(queue_name="jobs.ingest"), handler),
    )
    await asyncio.sleep(0)
    await bus.publish(
        OutboundMessage(queue="jobs.ingest", body={"id": "a1"}, correlation_id="c1"),
    )
    await asyncio.wait_for(done.wait(), timeout=2.0)
    assert received == [{"id": "a1"}]
    await bus.close()
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
