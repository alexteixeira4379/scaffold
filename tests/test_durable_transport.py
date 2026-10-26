"""Opt-in RabbitMQ failure scenarios against dedicated localhost services."""
import asyncio
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import aio_pika
import pytest
from sqlalchemy import func, insert, select, update

from scaffold.messaging.contracts import OutboundMessage
from scaffold.messaging.domain import enqueue, relay_once
from scaffold.messaging.processing import DeliveryPolicy, DurableDelivery, delivery_transaction, enqueue_output
from scaffold.messaging.queue_client import QueueClient
from scaffold.messaging.rabbitmq import RabbitMQMessaging
from scaffold.messaging.worker import QueueWorkerRunner
from scaffold.models.domain_delivery import DomainOutbox, WorkerDelivery, WorkerQuarantine
from tests.test_durable_processing import delivery_db as _delivery_db, effects

delivery_db = _delivery_db


@pytest.fixture
async def transport():
    url = os.getenv("TEST_WORKER_RABBITMQ_URL")
    if not url:
        pytest.skip("requires isolated TEST_WORKER_RABBITMQ_URL")
    from urllib.parse import urlparse
    assert urlparse(url).hostname in {"localhost", "127.0.0.1"}
    broker = RabbitMQMessaging(url)
    await broker.connect()
    name = "worker-refactor-test-" + uuid4().hex
    queue = await broker._channel.declare_queue(name, durable=True)
    yield broker, name
    await broker.stop_consumer(name)
    queue = await broker._channel.declare_queue(name, passive=True)
    await asyncio.wait_for(queue.delete(if_unused=False, if_empty=False), timeout=5)
    await broker.close()


async def read_until(queue):
    async def poll():
        while True:
            message = await queue.read()
            if message:
                return message
            await asyncio.sleep(0.01)
    return await asyncio.wait_for(poll(), timeout=5)


@pytest.mark.asyncio
async def test_streaming_consumer_preserves_invalid_bytes_and_advances(delivery_db, transport):
    broker, name = transport
    client = QueueClient(broker, name)
    for index in range(50):
        await broker.publish(OutboundMessage(queue=name, body={"event_id": f"valid-{index}", "id": index + 1}))
        if index % 10 == 0:
            await broker._publisher.default_exchange.publish(
                aio_pika.Message(b"\xff{invalid", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=name, mandatory=True,
            )
    stop = asyncio.Event()
    async def handler(message):
        async with delivery_transaction(delivery_db) as session:
            await session.execute(insert(effects).values(id=message.body["id"]))
        await message.delete()

    worker = QueueWorkerRunner(queue=client, handler=handler, reconnect=client.reconnect,
                              delivery=DurableDelivery(delivery_db, "test-stream"),
                              max_in_flight=4, continuous=True, idle_sleep_s=0.05)
    async def monitor():
        while worker._delivery.counters.values.get("received", 0) < 55:
            await asyncio.sleep(0.01)
        stop.set()
    await asyncio.wait_for(asyncio.gather(worker.run(stop), monitor()), timeout=20)
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(effects)) == 50
        quarantines = list(await session.scalars(select(WorkerQuarantine)))
        assert quarantines and all(row.raw_body == b"\xff{invalid" for row in quarantines)
    state = await broker._channel.declare_queue(name, passive=True)
    assert state.declaration_result.message_count == 0


@pytest.mark.asyncio
async def test_confirm_then_error_duplicates_delivery_without_duplicate_effect(delivery_db, transport):
    broker, name = transport
    async with delivery_db() as session, session.begin():
        await enqueue(session, "publisher-test", name, {"event_id": "stable-output", "id": 1}, key="one")
    async def ambiguous(message):
        await broker.publish(message)
        raise ConnectionError("confirm not observed")
    assert await relay_once(delivery_db, SimpleNamespace(publish=ambiguous), "publisher-test")
    async with delivery_db() as session, session.begin():
        await session.execute(update(DomainOutbox).values(available_at=datetime.now() - timedelta(seconds=1)))
    assert await relay_once(delivery_db, broker, "publisher-test")
    calls = 0
    async def handler(message):
        nonlocal calls
        async with delivery_transaction(delivery_db) as session:
            calls += 1
            await session.execute(insert(effects).values(id=1))
        await message.delete()
    queue = QueueClient(broker, name)
    worker = QueueWorkerRunner(queue=queue, handler=handler, reconnect=queue.reconnect,
                              delivery=DurableDelivery(delivery_db, "receiver-test"))
    await worker._process(await read_until(queue))
    await worker._process(await read_until(queue))
    assert calls == 1


@pytest.mark.asyncio
async def test_connection_restart_after_commit_replays_without_effect(delivery_db, transport):
    broker, name = transport
    await broker.publish(OutboundMessage(queue=name, body={"event_id": "restart-event", "id": 1}))
    queue = QueueClient(broker, name)
    committed = asyncio.Event()
    async def interrupted(message):
        async with delivery_transaction(delivery_db) as session:
            await session.execute(insert(effects).values(id=1))
            await enqueue_output(session, "restart-test", name, {"id": 2})
        committed.set()
        await asyncio.Event().wait()
    worker = QueueWorkerRunner(queue=queue, handler=interrupted, reconnect=queue.reconnect,
                              delivery=DurableDelivery(delivery_db, "restart-test", policy=DeliveryPolicy(lease_seconds=0.05)))
    task = asyncio.create_task(worker._process(await read_until(queue)))
    await asyncio.wait_for(committed.wait(), timeout=5)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await broker.close()
    await broker.connect()
    await asyncio.sleep(0.1)
    async def recovered(message):
        async with delivery_transaction(delivery_db) as session:
            await session.execute(insert(effects).values(id=1))
        await message.delete()
    fresh = QueueWorkerRunner(queue=queue, handler=recovered, reconnect=queue.reconnect,
                             delivery=DurableDelivery(delivery_db, "restart-test"))
    await fresh._process(await read_until(queue))
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(effects)) == 1
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 1
        state = await session.get(WorkerDelivery, ("restart-test", "restart-event"))
        assert state.status == "completed"
