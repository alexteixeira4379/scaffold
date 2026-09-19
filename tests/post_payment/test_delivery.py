from datetime import datetime, timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from scaffold.messaging.domain import emit, relay_once, consume_once
from scaffold.messaging.memory import InMemoryMessaging
from scaffold.messaging.queue_client import QueueClient
from scaffold.models.domain_delivery import DomainOutbox, DomainInbox


async def test_committed_event_survives_publish_failure_and_fans_out_once_per_consumer(db):
    async with db() as session, session.begin():
        event = await emit(
            session,
            "billing-worker",
            "subscription.activated",
            7,
            {"access_active": True},
            key="paid:7",
        )
        event_id = event.payload["event_id"]
    broken = AsyncMock()
    broken.publish.side_effect = ConnectionError("broker offline")
    await relay_once(db, broken, "billing-worker")
    async with db() as session, session.begin():
        row = await session.scalar(select(DomainOutbox))
        assert row.delivered_at is None and row.attempts == 1
        row.available_at = datetime.utcnow() - timedelta(seconds=1)
    broker = InMemoryMessaging()
    await relay_once(db, broker, "billing-worker")
    effects = []

    async def handler(session, event):
        effects.append(event["event_id"])

    for name in ("candidate.lifecycle", "tracking.lifecycle", "notification.lifecycle"):
        await consume_once(db, QueueClient(broker, name), name, handler)
    assert effects == [event_id] * 3
    async with db() as session:
        row = await session.scalar(select(DomainOutbox))
        payload = row.payload
    queue = QueueClient(broker, "candidate.lifecycle")
    await queue.publish(payload)
    await consume_once(db, queue, "candidate.lifecycle", handler)
    assert effects == [event_id] * 3


async def test_rollback_does_not_emit_and_consumer_failure_does_not_ack_effect(db):
    with pytest.raises(RuntimeError):
        async with db() as session, session.begin():
            await emit(session, "test", "subscription.activated", 1, {}, key="rollback")
            raise RuntimeError()
    async with db() as session:
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 0
    broker = InMemoryMessaging()
    queue = QueueClient(broker, "candidate.lifecycle")
    await queue.publish({"event_id": "e1", "event_name": "subscription.activated"})

    async def fail(session, event):
        raise RuntimeError("owner unavailable")

    await consume_once(db, queue, queue.queue_name, fail)
    assert await broker.fetch_one("candidate.lifecycle.retry") is not None
    async with db() as session:
        assert await session.scalar(select(func.count()).select_from(DomainInbox)) == 0
