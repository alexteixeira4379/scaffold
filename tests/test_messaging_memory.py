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


@pytest.mark.asyncio
async def test_memory_fetch_one_transfer_moves_and_finalizes_message() -> None:
    bus = InMemoryMessaging()
    await bus.connect()
    await bus.publish(
        OutboundMessage(queue="jobs.new", body={"id": "a1"}, correlation_id="c1"),
    )

    message = await bus.fetch_one("jobs.new")

    assert message is not None
    await message.transfer("jobs.new.dlq", {"id": "a1", "status": "failed"}, correlation_id="c1")

    assert await bus.fetch_one("jobs.new") is None
    dlq_message = await bus.fetch_one("jobs.new.dlq")
    assert dlq_message is not None
    assert dlq_message.body == {"id": "a1", "status": "failed"}
