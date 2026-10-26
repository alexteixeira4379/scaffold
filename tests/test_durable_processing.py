"""Failure-injection contract tests, runnable on SQLite and isolated MySQL.

TEST_WORKER_DATABASE_URL must point to a dedicated local schema ending _test.
"""
import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, func, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.exc import OperationalError

from scaffold.messaging.domain import enqueue, relay_once
from scaffold.messaging.memory import InMemoryMessaging
from scaffold.messaging.ports import FetchedMessage
from scaffold.messaging.processing import (
    DeferredMessage, DeliveryPolicy, DurableDelivery, FailureKind, InfrastructureUnavailable,
    PermanentMessageError, ReconciliationRequired, classify_failure, current_delivery,
    delivery_transaction, enqueue_output, event_identity,
)
from scaffold.messaging.worker import QueueWorkerRunner
from scaffold.models.domain_delivery import DomainInbox, DomainOutbox, WorkerDelivery, WorkerQuarantine

metadata = MetaData()
effects = Table("worker_test_effects", metadata, Column("id", Integer, primary_key=True))
tables = [DomainInbox.__table__, DomainOutbox.__table__, WorkerDelivery.__table__, WorkerQuarantine.__table__]


@pytest.fixture
async def delivery_db(tmp_path):
    url = os.getenv("TEST_WORKER_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path}/delivery.db"
    target = make_url(url)
    if target.get_backend_name() != "sqlite":
        assert target.host in {"localhost", "127.0.0.1"} and target.database.endswith("_test")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for table in tables:
            await conn.run_sync(table.create, checkfirst=True)
        await conn.run_sync(metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        for table in reversed(tables):
            await conn.run_sync(table.drop)
    await engine.dispose()


def message(index=1, *, body=None, raw=None, headers=None, decode_error=None, ack=None):
    return FetchedMessage(
        body if body is not None else {"event_id": f"event-{index}", "id": index},
        2, "correlation", "test.input", ack or AsyncMock(), AsyncMock(),
        raw_body=raw, headers=headers, decode_error=decode_error,
    )


def runner(factory, handler, *, policy=None, storage=None):
    return QueueWorkerRunner(
        queue=SimpleNamespace(), handler=handler, reconnect=AsyncMock(),
        delivery=DurableDelivery(factory, "test-consumer", source="test-service", policy=policy, storage=storage),
    )


async def due(factory):
    async with factory() as session, session.begin():
        await session.execute(update(DomainOutbox).values(available_at=datetime.now() - timedelta(seconds=1)))
        await session.execute(update(WorkerDelivery).where(WorkerDelivery.status == "retry").values(
            next_attempt_at=datetime.now() - timedelta(seconds=1)))


@pytest.mark.asyncio
async def test_invalid_message_does_not_stop_valid_commits(delivery_db):
    async def handler(msg):
        async with delivery_transaction(delivery_db) as session:
            await session.execute(insert(effects).values(id=msg.body["id"]))
            await enqueue_output(session, "test-service", "test.output", {"id": msg.body["id"]})
        await msg.delete()

    worker = runner(delivery_db, handler)
    # Real independent commits, with poison interleaved rather than just last.
    for index in range(101):
        msg = message(index) if index % 10 else message(index, body={}, raw=b"\xff{broken", decode_error="invalid_json")
        await worker._process(msg)
        assert msg.finalized
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(effects)) == 90
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 90
        # Identical raw poison is one observation, even when delivered repeatedly.
        quarantine = (await session.scalars(select(WorkerQuarantine))).all()
        assert len(quarantine) == 1 and quarantine[0].raw_body == b"\xff{broken"


@pytest.mark.asyncio
async def test_retry_budget_survives_new_runtime_and_constant_read_count(delivery_db):
    async def handler(msg):
        raise RuntimeError("SQL with secret payload must never be persisted")

    broker = InMemoryMessaging()
    msg = message()
    for attempt in range(1, 6):
        worker = runner(delivery_db, handler)
        await worker._process(msg)
        async with delivery_db() as session:
            state = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
            assert state.attempts == attempt and state.failures == attempt
            assert state.status == ("quarantined" if attempt == 5 else "retry")
        if attempt < 5:
            await due(delivery_db)
            assert await relay_once(delivery_db, broker, "test-service")
            msg = await broker.fetch_one("test.input")
            assert msg is not None and msg.correlation_id == "correlation"
    async with delivery_db() as session:
        row = await session.scalar(select(WorkerQuarantine))
        assert row.attempts == 5 and row.reason == "RuntimeError"
        assert "secret" not in row.reason


@pytest.mark.asyncio
async def test_infrastructure_preserves_origin_without_spending_budget(delivery_db):
    async def handler(msg):
        raise InfrastructureUnavailable("database_down")
    worker = runner(delivery_db, handler)
    msg = message()
    await worker._process(msg)
    msg._ack.assert_not_awaited()
    msg._nack.assert_awaited_once_with(True)
    async with delivery_db() as session:
        row = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert row.attempts == 1 and row.failures == 0 and row.status == "pending"
    assert worker._pause_until > asyncio.get_running_loop().time()


@pytest.mark.asyncio
async def test_return_without_outcome_is_quarantined(delivery_db):
    worker = runner(delivery_db, AsyncMock())
    await worker._process(message())
    async with delivery_db() as session:
        row = await session.scalar(select(WorkerQuarantine))
        assert row.reason.endswith("handler_returned_without_outcome")


@pytest.mark.asyncio
async def test_commit_survives_ambiguous_ack_and_deduplicates_effect(delivery_db):
    calls = 0
    async def handler(msg):
        nonlocal calls
        async with delivery_transaction(delivery_db) as session:
            calls += 1
            await session.execute(insert(effects).values(id=1))
            await enqueue_output(session, "test-service", "test.output", {"id": 1})
        await msg.delete()
    worker = runner(delivery_db, handler)
    await worker._process(message(ack=AsyncMock(side_effect=ConnectionError("ack lost"))))
    await runner(delivery_db, handler)._process(message())
    assert calls == 1
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(effects)) == 1
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 1


@pytest.mark.asyncio
async def test_expired_owner_cannot_commit_local_effects(delivery_db):
    delivery = DurableDelivery(delivery_db, "test-consumer")
    context = await delivery.claim(message())
    token = current_delivery.set(context)
    try:
        with pytest.raises(InfrastructureUnavailable):
            async with delivery_transaction(delivery_db) as session:
                # Simulate an already-fenced execution without another writer
                # contending on the test database's single SQLite writer lock.
                context.token = "stale-token"
                await session.execute(insert(effects).values(id=1))
    finally:
        current_delivery.reset(token)
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(effects)) == 0
        assert await session.scalar(select(func.count()).select_from(DomainInbox)) == 0


@pytest.mark.asyncio
async def test_deferred_wait_repeats_without_spending_failure_budget(delivery_db):
    async def handler(msg):
        raise DeferredMessage(10, "predecessor_pending")
    broker = InMemoryMessaging()
    msg = message()
    for _ in range(3):
        await runner(delivery_db, handler)._process(msg)
        await due(delivery_db)
        await relay_once(delivery_db, broker, "test-service")
        msg = await broker.fetch_one("test.input")
    async with delivery_db() as session:
        row = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert row.attempts == 3 and row.failures == 0 and row.retry_generation == 3
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), ConnectionError(), RuntimeError(),
                                 ValueError("malformed receipt"), TypeError("invalid receipt"),
                                 OperationalError("UPDATE after send", {}, Exception(2013, "lost connection"))])
async def test_uncertain_external_effect_is_never_automatically_retried(delivery_db, error):
    async def handler(msg):
        raise error
    await runner(delivery_db, handler, policy=DeliveryPolicy(external_effects=True))._process(message())
    async with delivery_db() as session:
        row = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert row.status == "uncertain"
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 0


@pytest.mark.asyncio
async def test_quarantine_storage_failure_keeps_original_unacked(delivery_db):
    storage = SimpleNamespace(upload=AsyncMock(side_effect=ConnectionError("storage down")))
    msg = message(raw=b"original content", decode_error="invalid_json")
    await runner(delivery_db, AsyncMock(), policy=DeliveryPolicy(quarantine_inline_bytes=2), storage=storage)._process(msg)
    msg._ack.assert_not_awaited()
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(WorkerQuarantine)) == 0


@pytest.mark.asyncio
async def test_large_quarantine_preserves_exact_bytes_in_storage(delivery_db):
    storage = SimpleNamespace(upload=AsyncMock())
    raw = b"\xffinvalid original"
    msg = message(raw=raw, decode_error="invalid_json")
    await runner(delivery_db, AsyncMock(), policy=DeliveryPolicy(quarantine_inline_bytes=2), storage=storage)._process(msg)
    storage.upload.assert_awaited_once()
    assert storage.upload.call_args.args[1] == raw
    async with delivery_db() as session:
        row = await session.scalar(select(WorkerQuarantine))
        assert row.payload_sha256 == hashlib.sha256(raw).hexdigest() and row.storage_key and row.raw_body is None


@pytest.mark.asyncio
async def test_relay_does_not_hold_database_transaction_while_publishing(delivery_db):
    async with delivery_db() as session, session.begin():
        await enqueue(session, "test-service", "test.output", {"id": 1}, key="one")

    async def publish(msg):
        # A separate writer can update the claimed row while confirm is pending.
        async with delivery_db() as session, session.begin():
            await session.execute(update(DomainOutbox).values(last_error="concurrent_write"))
    await asyncio.wait_for(relay_once(delivery_db, SimpleNamespace(publish=publish), "test-service"), timeout=3)
    async with delivery_db() as session:
        row = await session.scalar(select(DomainOutbox))
        assert row.delivered_at is not None


@pytest.mark.asyncio
async def test_stale_relay_confirmation_is_fenced(delivery_db):
    async with delivery_db() as session, session.begin():
        await enqueue(session, "test-service", "test.output", {"id": 1}, key="one")
    async def publish(msg):
        async with delivery_db() as session, session.begin():
            await session.execute(update(DomainOutbox).values(claim_token="new-owner"))
    await relay_once(delivery_db, SimpleNamespace(publish=publish), "test-service")
    async with delivery_db() as session:
        row = await session.scalar(select(DomainOutbox))
        assert row.delivered_at is None and row.claim_token == "new-owner"


def test_legacy_identity_preserves_distinct_observations_and_stable_redelivery():
    one = message(body={"url": "same", "metadata": {"collected_at": "2026-10-25"}})
    two = message(body={"url": "same", "metadata": {"collected_at": "2026-10-26"}})
    assert event_identity(one) != event_identity(two)
    assert event_identity(one) == event_identity(message(body=one.body, headers={"x-delivery-count": 100}))
    first = event_identity(message(body={"message_id": "MessageA", "event_id": "transport"}), ("message_id",))
    second = event_identity(message(body={"message_id": "messagea", "event_id": "transport"}), ("message_id",))
    assert first != second and len(first) == 64


@pytest.mark.parametrize("exception,expected", [
    (PermanentMessageError(), FailureKind.PERMANENT),
    (InfrastructureUnavailable(), FailureKind.INFRASTRUCTURE),
    (ReconciliationRequired(), FailureKind.UNCERTAIN),
    (DeferredMessage(1), FailureKind.DEFERRED),
])
def test_failure_policy(exception, expected):
    assert classify_failure(exception) == expected


@pytest.mark.asyncio
async def test_quarantine_replay_is_audited_and_does_not_reset_execution_count(delivery_db):
    from scaffold.messaging.quarantine import replay
    async def invalid(msg):
        raise PermanentMessageError("bad_input")
    await runner(delivery_db, invalid)._process(message())
    async with delivery_db() as session:
        record = await session.scalar(select(WorkerQuarantine))
        quarantine_id = record.id
    await replay(delivery_db, quarantine_id, source="test-service", actor="operator", reason="input-corrected")
    with pytest.raises(ValueError, match="already_replayed"):
        await replay(delivery_db, quarantine_id, source="test-service", actor="operator", reason="again")
    broker = InMemoryMessaging()
    await relay_once(delivery_db, broker, "test-service")
    fresh = await broker.fetch_one("test.input")
    async def valid(msg):
        await msg.delete(receipt={"provider_id": "receipt-1"})
    await runner(delivery_db, valid)._process(fresh)
    async with delivery_db() as session:
        state = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert state.attempts == 2 and state.failures == 0 and state.status == "completed"
        assert state.receipt == {"provider_id": "receipt-1"}
        record = await session.get(WorkerQuarantine, quarantine_id)
        assert record.replayed_by == "operator" and record.replay_metadata["reason"] == "input-corrected"


@pytest.mark.asyncio
async def test_uncertain_effect_cannot_replay_without_reconciliation(delivery_db):
    from scaffold.messaging.quarantine import replay
    async def uncertain(msg):
        raise ReconciliationRequired("send_unknown")
    await runner(delivery_db, uncertain)._process(message())
    async with delivery_db() as session:
        record = await session.scalar(select(WorkerQuarantine))
        identity = record.id
    with pytest.raises(ValueError, match="reconciliation_evidence_required"):
        await replay(delivery_db, identity, source="test-service", actor="operator", reason="retry")


@pytest.mark.asyncio
async def test_ready_retry_is_not_lost_when_consumer_clock_is_behind(delivery_db):
    async def failed(msg):
        raise RuntimeError()
    await runner(delivery_db, failed)._process(message())
    async with delivery_db() as session:
        row = await session.scalar(select(DomainOutbox))
        retry_message = message(body=row.payload, headers=row.headers)
    # The retry is broker-delivered even though the local clock still considers
    # next_attempt_at future; its generation is explicit and owns recovery.
    async def valid(msg):
        await msg.delete()
    await runner(delivery_db, valid)._process(retry_message)
    async with delivery_db() as session:
        state = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert state.status == "completed" and state.attempts == 2


@pytest.mark.asyncio
async def test_busy_duplicate_is_preserved_without_pausing_other_work(delivery_db):
    delivery = DurableDelivery(delivery_db, "test-consumer", source="test-service")
    original = message(raw=b'{ "event_id": "event-1", "id": 1 }')
    owner = await delivery.claim(original)
    assert owner is not None
    duplicate = message(raw=original.raw_body)
    worker = runner(delivery_db, AsyncMock())
    await worker._process(duplicate)
    duplicate._ack.assert_awaited_once()
    assert worker._pause_until == 0
    async with delivery_db() as session:
        pending = await session.scalar(select(DomainOutbox))
        assert pending.raw_body == original.raw_body
        assert pending.available_at > datetime.utcnow()
        state = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert state.attempts == 1 and state.claim_token == owner.token


@pytest.mark.asyncio
async def test_case_sensitive_legacy_intents_are_distinct_on_mysql(delivery_db):
    async def handler(msg):
        await msg.delete()
    worker = runner(delivery_db, handler, policy=DeliveryPolicy(identity_fields=("message_id",)))
    await worker._process(message(body={"message_id": "MessageA"}))
    await worker._process(message(body={"message_id": "messagea"}))
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(WorkerDelivery)) == 2


@pytest.mark.asyncio
async def test_explicit_event_ids_keep_case_accents_and_trailing_characters(delivery_db):
    async def handler(msg):
        async with delivery_transaction(delivery_db) as session:
            await session.execute(insert(effects).values(id=msg.body["id"]))
        await msg.delete()
    worker = runner(delivery_db, handler)
    identities = ("Event-A", "event-a", "Évent-A", "Event-A ")
    for index, identity in enumerate(identities, 1):
        await worker._process(message(body={"event_id": identity, "id": index}))
    async with delivery_db() as session:
        assert await session.scalar(select(func.count()).select_from(WorkerDelivery)) == 4
        assert await session.scalar(select(func.count()).select_from(DomainInbox)) == 4
        assert await session.scalar(select(func.count()).select_from(effects)) == 4


@pytest.mark.asyncio
async def test_external_heartbeat_failure_after_acceptance_never_resends(delivery_db):
    calls = 0
    async def handler(msg):
        nonlocal calls
        calls += 1  # provider already accepted the side effect
        await asyncio.Event().wait()  # receipt persistence has not finished
    worker = runner(delivery_db, handler, policy=DeliveryPolicy(external_effects=True, lease_seconds=0.06))
    worker._delivery.heartbeat = AsyncMock(side_effect=InfrastructureUnavailable("database_down"))
    await asyncio.wait_for(worker._process(message()), timeout=1)
    await runner(delivery_db, handler, policy=DeliveryPolicy(external_effects=True))._process(message())
    assert calls == 1
    async with delivery_db() as session:
        row = await session.get(WorkerDelivery, ("test-consumer", "event-1"))
        assert row.status == "uncertain"
        assert await session.scalar(select(func.count()).select_from(DomainOutbox)) == 0


@pytest.mark.asyncio
async def test_no_progress_alert_includes_preserved_work_with_no_active_task(delivery_db, caplog):
    async def handler(msg):
        raise InfrastructureUnavailable("database_down")
    worker = runner(delivery_db, handler)
    await worker._process(message())
    now = asyncio.get_running_loop().time()
    worker._delivery.counters.last_progress = now - 301
    with caplog.at_level("ERROR"):
        worker._report_progress(0, now)
    assert "worker_no_progress" in caplog.text and "in_flight=0 unresolved=1" in caplog.text


@pytest.mark.asyncio
async def test_continuous_consumer_does_not_keep_legacy_thirty_second_idle(delivery_db):
    stop = asyncio.Event()
    class Queue:
        calls = 0
        start_consumer = AsyncMock()
        stop_consumer = AsyncMock()
        async def read(self):
            self.calls += 1
            return message() if self.calls == 2 else None
    async def handler(msg):
        await msg.delete()
        stop.set()
    worker = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=AsyncMock(),
                              delivery=DurableDelivery(delivery_db, "continuous-test"),
                              continuous=True, idle_sleep_s=30)
    await asyncio.wait_for(worker.run(stop), timeout=0.8)


@pytest.mark.asyncio
async def test_progress_timer_runs_with_all_slots_occupied(delivery_db, caplog):
    stop, release = asyncio.Event(), asyncio.Event()
    class Queue:
        sent = False
        async def read(self):
            if not self.sent:
                self.sent = True
                return message()
            return None
    async def handler(msg):
        await release.wait()
        await msg.delete()
    delivery = DurableDelivery(delivery_db, "progress-timer")
    delivery.counters.last_progress = asyncio.get_running_loop().time() - 1
    worker = QueueWorkerRunner(queue=Queue(), handler=handler, reconnect=AsyncMock(), delivery=delivery,
                              progress_report_interval_s=0.01, no_progress_s=0.03)
    async def finish():
        await asyncio.sleep(0.08)
        stop.set()
        release.set()
    with caplog.at_level("ERROR"):
        await asyncio.wait_for(asyncio.gather(worker.run(stop), finish()), timeout=1)
    assert "worker_no_progress" in caplog.text and "in_flight=1" in caplog.text

async def test_provider_cooldown_persists_retry_and_pauses_consumer(delivery_db):
    async def handle(msg):
        raise DeferredMessage(60, 'provider_cooldown', pause_consumer=True)
    runtime=runner(delivery_db,handle)
    msg=message()
    before=asyncio.get_running_loop().time()
    await runtime._process_durable(msg)
    assert runtime._pause_until>=before+60
    async with delivery_db() as session:
        state=await session.get(WorkerDelivery,('test-consumer','event-1'))
        assert state.status=='retry' and state.failures==0
        assert await session.scalar(select(func.count()).select_from(DomainOutbox))==1
