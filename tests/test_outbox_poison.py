"""Historical outbox poison isolation and audited publisher recovery."""
import hashlib
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import aio_pika
import pytest
from sqlalchemy import func, select, update

from scaffold.messaging.domain import enqueue, relay_once
from scaffold.messaging.quarantine import replay
from scaffold.messaging.queue_client import QueueClient
from scaffold.models.domain_delivery import DomainOutbox, WorkerDelivery, WorkerQuarantine
from tests.test_durable_processing import delivery_db as _delivery_db
from tests.test_durable_transport import transport as _transport, read_until

delivery_db = _delivery_db
transport = _transport
SOURCE = "outbox-poison-test"


async def historical(factory, payload=None, *, queue="test.output", headers=None, raw=None, exchange=""):
    async with factory() as session, session.begin():
        row = DomainOutbox(source=SOURCE, destination=queue, exchange=exchange,
                           payload=payload, dedupe_key=uuid4().hex, headers=headers, raw_body=raw,
                           available_at=datetime.utcnow().replace(microsecond=0))
        session.add(row)
        await session.flush()
        return row.id


async def quarantine(factory):
    async with factory() as session:
        return await session.scalar(select(WorkerQuarantine).order_by(WorkerQuarantine.created_at.desc()))


async def make_due(factory):
    async with factory() as session, session.begin():
        await session.execute(update(DomainOutbox).values(
            available_at=datetime.utcnow() - timedelta(seconds=1), claimed_until=None,
        ))


@pytest.mark.parametrize("invalid", [None, ["invalid"], "invalid"])
async def test_historical_poison_between_valid_rows_preserves_and_replays_on_real_broker(delivery_db, transport, invalid):
    broker, destination = transport
    exchange_name = "outbox-poison-exchange-" + uuid4().hex
    exchange = await broker._publisher.declare_exchange(exchange_name, aio_pika.ExchangeType.DIRECT, durable=True)
    queue = await broker._channel.declare_queue(destination, passive=True)
    await queue.bind(exchange, routing_key=destination)
    try:
        async with delivery_db() as session, session.begin():
            await enqueue(session, SOURCE, destination, {"id": 1}, key="before", exchange=exchange_name)
        invalid_id = await historical(delivery_db, invalid, queue=destination, exchange=exchange_name)
        async with delivery_db() as session, session.begin():
            await enqueue(session, SOURCE, destination, {"id": 3}, key="after", exchange=exchange_name)
        assert await relay_once(delivery_db, broker, SOURCE)
        client = QueueClient(broker, destination)
        delivered = [await read_until(client), await read_until(client)]
        assert sorted(msg.body["id"] for msg in delivered) == [1, 3]
        for msg in delivered:
            await msg.delete()
        record = await quarantine(delivery_db)
        assert record.consumer == "outbox-publisher"
        assert record.raw_body == json.dumps(invalid, ensure_ascii=False, separators=(",", ":")).encode()
        assert record.payload_sha256 == hashlib.sha256(record.raw_body).hexdigest()
        assert record.headers["x-original-exchange"] == exchange_name
        async with delivery_db() as session:
            original = await session.get(DomainOutbox, invalid_id)
            assert original.quarantined_at is not None and original.delivered_at is None
            assert original.payload == invalid and original.claim_token is None
            assert await session.scalar(select(func.count()).select_from(DomainOutbox).where(
                DomainOutbox.delivered_at.is_not(None))) == 2
        await replay(delivery_db, record.id, source=SOURCE, actor="operator", reason="payload-repaired",
                     replacement=json.dumps({"event_id": "repaired", "id": 2}).encode())
        assert await relay_once(delivery_db, broker, SOURCE)
        recovered = await read_until(client)
        assert recovered.body["id"] == 2
        await recovered.delete()
        async with delivery_db() as session:
            control = await session.get(WorkerDelivery, ("outbox-publisher", record.event_id))
            assert control.status == "completed" and control.attempts == 2
            assert control.claim_token is None and control.receipt["outbox_id"] != invalid_id
            original = await session.get(DomainOutbox, invalid_id)
            assert original.payload == invalid and original.delivered_at is None
            audited = await session.get(WorkerQuarantine, record.id)
            assert audited.replayed_by == "operator" and audited.replay_metadata["reason"] == "payload-repaired"
        assert not await relay_once(delivery_db, broker, SOURCE)
    finally:
        await exchange.delete(if_unused=False)


@pytest.mark.parametrize("payload", [None, [], "bad"])
async def test_enqueue_rejects_new_non_object_payload_without_writing(payload):
    session = SimpleNamespace(scalar=AsyncMock())
    with pytest.raises(ValueError, match="outbox_payload_must_be_object"):
        await enqueue(session, SOURCE, "test.output", payload, key="bad")
    session.scalar.assert_not_awaited()


async def test_broker_failure_keeps_valid_and_replayed_outbox_pending(delivery_db):
    bad_id = await historical(delivery_db)
    broker = SimpleNamespace(publish=AsyncMock())
    assert await relay_once(delivery_db, broker, SOURCE)
    record = await quarantine(delivery_db)
    await replay(delivery_db, record.id, source=SOURCE, actor="operator", reason="repaired",
                 replacement=b'{"id":2}')
    broker.publish.side_effect = ConnectionError("broker unavailable")
    assert await relay_once(delivery_db, broker, SOURCE)
    async with delivery_db() as session:
        control = await session.get(WorkerDelivery, ("outbox-publisher", record.event_id))
        assert control.status == "retry" and control.claim_token is None
        assert await session.scalar(select(func.count()).select_from(WorkerQuarantine)) == 1
        pending = await session.scalar(select(DomainOutbox).where(DomainOutbox.id != bad_id))
        assert pending.delivered_at is None and pending.quarantined_at is None and pending.attempts == 1
    await make_due(delivery_db)
    broker.publish.side_effect = None
    assert await relay_once(delivery_db, broker, SOURCE)
    async with delivery_db() as session:
        assert (await session.get(WorkerDelivery, ("outbox-publisher", record.event_id))).status == "completed"


async def test_stale_replay_confirmation_cannot_complete_new_owner(delivery_db):
    await historical(delivery_db)
    await relay_once(delivery_db, SimpleNamespace(publish=AsyncMock()), SOURCE)
    record = await quarantine(delivery_db)
    await replay(delivery_db, record.id, source=SOURCE, actor="operator", reason="repaired",
                 replacement=b'{"id":2}')
    async def publish(msg):
        async with delivery_db() as session, session.begin():
            await session.execute(update(DomainOutbox).where(DomainOutbox.quarantined_at.is_(None)).values(claim_token="new-owner"))
            await session.execute(update(WorkerDelivery).values(claim_token="new-owner"))
    await relay_once(delivery_db, SimpleNamespace(publish=publish), SOURCE)
    async with delivery_db() as session:
        state = await session.get(WorkerDelivery, ("outbox-publisher", record.event_id))
        assert state.status == "retry" and state.claim_token == "new-owner"
        pending = await session.scalar(select(DomainOutbox).where(DomainOutbox.quarantined_at.is_(None)))
        assert pending.delivered_at is None


async def test_invalid_replacement_is_quarantined_again_without_stuck_scheduled_control(delivery_db):
    await historical(delivery_db)
    broker = SimpleNamespace(publish=AsyncMock())
    await relay_once(delivery_db, broker, SOURCE)
    original = await quarantine(delivery_db)
    await replay(delivery_db, original.id, source=SOURCE, actor="operator", reason="first-fix",
                 replacement=b'{"id":2,"correlation_id":{"invalid":true}}')
    assert await relay_once(delivery_db, broker, SOURCE)
    broker.publish.assert_not_awaited()
    async with delivery_db() as session:
        records = list(await session.scalars(select(WorkerQuarantine)))
        assert len(records) == 2
        corrected = next(row for row in records if row.id != original.id)
        state = await session.get(WorkerDelivery, ("outbox-publisher", original.event_id))
        assert state.status == "quarantined" and corrected.event_id == original.event_id
    await replay(delivery_db, corrected.id, source=SOURCE, actor="operator", reason="second-fix",
                 replacement=b'{"id":2}')
    assert await relay_once(delivery_db, broker, SOURCE)
    broker.publish.assert_awaited_once()
    async with delivery_db() as session:
        assert (await session.get(WorkerDelivery, ("outbox-publisher", original.event_id))).status == "completed"


async def test_large_original_uses_durable_sql_reference_without_copying_large_blob(delivery_db):
    raw = b"original" * (16 * 1024 * 1024 // 8 + 1)
    identity = await historical(delivery_db, raw=raw)
    broker = SimpleNamespace(publish=AsyncMock())
    assert await relay_once(delivery_db, broker, SOURCE)
    record = await quarantine(delivery_db)
    assert record.raw_body is None and record.storage_key == f"domain-outbox:{identity}"
    assert record.payload_sha256 == hashlib.sha256(raw).hexdigest()
    async with delivery_db() as session:
        assert (await session.get(DomainOutbox, identity)).raw_body == raw
    with pytest.raises(ValueError, match="export_external_payload_before_replay"):
        await replay(delivery_db, record.id, source=SOURCE, actor="operator", reason="repair")
    broker.publish.assert_not_awaited()


async def test_integer_broker_headers_remain_publishable(delivery_db):
    await historical(delivery_db, {"id": 1}, headers={"x-delivery-count": 2})
    broker = SimpleNamespace(publish=AsyncMock())
    assert await relay_once(delivery_db, broker, SOURCE)
    assert broker.publish.call_args.args[0].headers["x-delivery-count"] == "2"
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(WorkerQuarantine)) == 0


@pytest.mark.parametrize("invalid_identity", [{"id": "invalid"}, ["invalid"]])
async def test_invalid_replay_metadata_cannot_abort_healthy_batch(delivery_db, invalid_identity):
    malformed = await historical(delivery_db, {"id": 1}, headers={"x-quarantine-replay": invalid_identity})
    async with delivery_db() as session, session.begin():
        row = await session.get(DomainOutbox, malformed)
        row.dedupe_key = f"quarantine-replay:{invalid_identity}"
        await enqueue(session, SOURCE, "test.output", {"id": 2}, key="healthy-sibling")
    broker = SimpleNamespace(publish=AsyncMock())
    assert await relay_once(delivery_db, broker, SOURCE)
    assert sorted(call.args[0].body["id"] for call in broker.publish.await_args_list) == [1, 2]
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(DomainOutbox).where(
            DomainOutbox.delivered_at.is_not(None))) == 2
