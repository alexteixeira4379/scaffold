"""Transactional outbox, independent inboxes and background domain consumers."""

import asyncio
import hashlib
import json
import logging
import random
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from scaffold.config import get_settings
from scaffold.db.session import get_session_factory
from scaffold.models.domain_delivery import DomainOutbox, WorkerDelivery, WorkerQuarantine
from scaffold.messaging.contracts import OutboundMessage
from scaffold.messaging.factory import create_messaging_client
from scaffold.messaging.queue_client import QueueClient
from scaffold.messaging.definitions.domain import DOMAIN_EXCHANGE

logger = logging.getLogger(__name__)


async def enqueue(session, source, destination, payload, *, key, exchange="", available_at=None, headers=None, raw_body=None):
    if not isinstance(payload, dict):
        raise ValueError("outbox_payload_must_be_object")
    # Existing DATETIME(0) deployments round fractional seconds. Floor an
    # immediate publication so it cannot accidentally become future work.
    available_at = available_at or datetime.utcnow().replace(microsecond=0)
    headers = dict(headers or {})
    if payload and not payload.get("event_id"):
        headers.setdefault("x-event-id", str(uuid5(NAMESPACE_URL, f"jobito-outbox:{source}:{key}")))
    existing = await session.scalar(
        select(DomainOutbox).where(DomainOutbox.source == source, DomainOutbox.dedupe_key == key)
    )
    if existing is not None:
        return existing
    if session.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
        await session.execute(insert(DomainOutbox).values(
            source=source, destination=destination, exchange=exchange, dedupe_key=key,
            payload=payload, available_at=available_at or datetime.utcnow(), headers=headers, raw_body=raw_body,
        ).on_conflict_do_nothing(index_elements=["source", "dedupe_key"]))
        return await session.scalar(select(DomainOutbox).where(
            DomainOutbox.source == source, DomainOutbox.dedupe_key == key))
    row = DomainOutbox(
        source=source,
        destination=destination,
        exchange=exchange,
        dedupe_key=key,
        payload=payload,
        headers=headers,
        raw_body=raw_body,
        available_at=available_at or datetime.utcnow(),
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        # Concurrent insertion is protected by the unique source/key constraint.
        # A locking read sees the committed winner even under REPEATABLE READ.
        row = await session.scalar(select(DomainOutbox).where(
            DomainOutbox.source == source, DomainOutbox.dedupe_key == key
        ).with_for_update())
        if row is None:
            raise
    return row


async def _quarantine_invalid_outbox(session, row, reason, *, replay_control=None):
    """Isolate a bad historical row atomically; its original data is never deleted.

    Bodies up to 16 MiB are copied verbatim. Larger historical records keep a
    SQL reference ``domain-outbox:<id>`` to their intact original row, not an S3
    key. Operators export that SQL payload and provide an audited replacement.
    Publisher controls use their own consumer namespace, never the receiver's.
    """
    now = datetime.utcnow()
    identity = replay_control or f"outbox:{row.id}"
    raw = row.raw_body
    if raw is None:
        raw = json.dumps(row.payload, ensure_ascii=False, separators=(",", ":")).encode()
    headers = dict(row.headers) if isinstance(row.headers, dict) else {
        "x-original-outbox-headers": json.dumps(row.headers, ensure_ascii=False, default=str)
    }
    headers["x-original-exchange"] = row.exchange
    control = await session.get(WorkerDelivery, ("outbox-publisher", identity), with_for_update=True)
    if control is None:
        control = WorkerDelivery(
            consumer="outbox-publisher", event_id=identity, queue=row.destination,
            status="quarantined", attempts=0, failures=0,
            retry_generation=0, created_at=now, updated_at=now,
        )
        session.add(control)
    control.status, control.last_error = "quarantined", reason
    control.attempts += 1
    control.failures += 1
    control.claim_token = control.claimed_until = control.next_attempt_at = None
    control.updated_at = now
    correlation = (headers.get("x-correlation-id") or
                   (row.payload.get("correlation_id") if isinstance(row.payload, dict) else None))
    if not isinstance(correlation, str) or len(correlation) > 255:
        correlation = None
    session.add(WorkerQuarantine(
        id=str(uuid4()), consumer="outbox-publisher", event_id=identity,
        queue=row.destination,
        correlation_id=correlation,
        reason=reason, attempts=control.attempts,
        payload_sha256=hashlib.sha256(raw).hexdigest(),
        raw_body=raw if len(raw) <= 16 * 1024 * 1024 else None,
        storage_key=f"domain-outbox:{row.id}" if len(raw) > 16 * 1024 * 1024 else None,
        headers=headers, created_at=now,
    ))
    row.quarantined_at = now
    row.attempts += 1
    row.last_error = reason
    row.claim_token = row.claimed_until = None


async def _publisher_replay_control(session, row):
    headers = row.headers if isinstance(row.headers, dict) else {}
    identity = headers.get("x-quarantine-replay")
    if (not isinstance(identity, str) or not identity or len(identity) > 36 or
            row.dedupe_key != f"quarantine-replay:{identity}"):
        return None
    record = await session.get(WorkerQuarantine, identity)
    if (record is None or record.consumer != "outbox-publisher" or
            record.replayed_at is None or record.queue != row.destination or
            (record.replay_metadata or {}).get("source") != row.source):
        return None
    return record.event_id


def _outbound_row(row):
    if not isinstance(row.payload, dict):
        raise ValueError("outbox_payload_must_be_object")
    if row.headers is not None and not isinstance(row.headers, dict):
        raise ValueError("outbox_headers_must_be_object")
    # Broker-originated integer delivery headers are normal. The publication
    # contract uses string headers, so normalize values instead of rejecting an
    # otherwise valid scheduled retry. Original metadata remains in the SQL row.
    headers = {key: value if isinstance(value, str) else json.dumps(value, default=str)
               for key, value in (row.headers or {}).items()}
    return OutboundMessage(
        queue=row.destination, exchange=row.exchange, body=row.payload,
        correlation_id=headers.get("x-correlation-id") or row.payload.get("correlation_id"),
        headers=headers, raw_body=row.raw_body,
    )


async def emit(session, source, event_name, candidate_id, data, *, key, aggregate=None):
    row = await enqueue(session, source, event_name, {}, key=key, exchange=DOMAIN_EXCHANGE)
    if row.payload:
        return row
    row.payload = {
        "event_id": str(uuid4()),
        "event_name": event_name,
        "event_type": event_name,
        "schema_version": "1.0",
        "source_service": source,
        "candidate_id": candidate_id,
        "aggregate": aggregate or f"candidate:{candidate_id}",
        "aggregate_version": row.id,
        "occurred_at": datetime.now(UTC).isoformat(),
        "correlation_id": key,
        "data": data,
    }
    return row


async def relay_once(factory, broker, source, *, batch_size=16, concurrency=4, publish_timeout=15):
    """Claim in a short transaction; never await the broker while holding locks.

    A lease token fences stale completion writes. A crash after confirm still
    admits redelivery, so consumer inboxes remain required.
    """
    if min(batch_size, concurrency, publish_timeout) <= 0:
        raise ValueError("positive outbox limits required")
    token = str(uuid4())
    now = datetime.utcnow()
    lease_seconds = publish_timeout * ((batch_size + concurrency - 1) // concurrency + 1) + 30
    async with factory() as session, session.begin():
        rows = list(await session.scalars(
            select(DomainOutbox)
            .where(
                DomainOutbox.source == source,
                DomainOutbox.delivered_at.is_(None),
                DomainOutbox.quarantined_at.is_(None),
                DomainOutbox.available_at <= datetime.utcnow(),
                or_(DomainOutbox.claimed_until.is_(None), DomainOutbox.claimed_until <= now),
            )
            .order_by(DomainOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        ))
        pending = []
        quarantined = 0
        for row in rows:
            replay_control = await _publisher_replay_control(session, row)
            try:
                message = _outbound_row(row)
            except (ValueError, TypeError):
                # Construction errors are permanent data failures; one malformed
                # historical payload must never roll back all healthy claims.
                await _quarantine_invalid_outbox(session, row, "outbox_invalid_envelope",
                                                 replay_control=replay_control)
                quarantined += 1
                continue
            row.claim_token = token
            row.claimed_until = now + timedelta(seconds=lease_seconds)
            if replay_control:
                control = await session.get(WorkerDelivery, ("outbox-publisher", replay_control),
                                            with_for_update=True)
                if control is not None and control.status == "retry":
                    control.attempts += 1
                    control.claim_token = token
                    control.claimed_until = row.claimed_until
                    control.updated_at = now
            pending.append((row.id, row.attempts, message, replay_control))
    if not pending:
        return bool(quarantined)
    semaphore = asyncio.Semaphore(concurrency)
    failures = Counter()

    async def publish(item):
        row_id, attempts, message, replay_control = item
        async with semaphore:
            try:
                await asyncio.wait_for(broker.publish(message), timeout=publish_timeout)
            except Exception as exc:
                values = dict(
                    attempts=attempts + 1, last_error=type(exc).__name__,
                    available_at=datetime.utcnow() + timedelta(seconds=min(300, 2 ** min(attempts + 1, 8)) * random.uniform(1, 1.2)),
                )
                failures[type(exc).__name__] += 1
            else:
                values = dict(delivered_at=datetime.utcnow(), last_error=None)
            async with factory() as session, session.begin():
                updated = await session.execute(update(DomainOutbox).where(
                    DomainOutbox.id == row_id, DomainOutbox.claim_token == token,
                    DomainOutbox.delivered_at.is_(None),
                ).values(**values, claim_token=None, claimed_until=None))
                if updated.rowcount and replay_control:
                    control_values = dict(claim_token=None, claimed_until=None,
                                          last_error=values.get("last_error"), updated_at=datetime.utcnow())
                    if "delivered_at" in values:
                        control_values.update(status="completed", next_attempt_at=None,
                                              receipt={"outbox_id": row_id})
                    else:
                        control_values["next_attempt_at"] = values["available_at"]
                    await session.execute(update(WorkerDelivery).where(
                        WorkerDelivery.consumer == "outbox-publisher",
                        WorkerDelivery.event_id == replay_control,
                        WorkerDelivery.status == "retry",
                        WorkerDelivery.claim_token == token,
                    ).values(**control_values))

    await asyncio.gather(*(publish(item) for item in pending))
    if failures:
        logger.warning("outbox_batch_pending source=%s failures=%s", source, dict(failures))
    return True


async def consume_once(factory, queue, consumer, handler):
    message = await queue.read()
    if message is None:
        return False
    from scaffold.messaging.processing import DurableDelivery
    from scaffold.messaging.worker import QueueWorkerRunner
    runtime = QueueWorkerRunner(queue=queue, handler=_domain_handler(factory, handler),
                                reconnect=queue.reconnect, delivery=DurableDelivery(factory, consumer))
    await runtime._process(message)
    return True


def _domain_handler(factory, handler, *, transactional=True):
    from scaffold.messaging.processing import PermanentMessageError, delivery_transaction

    async def invoke(message):
        if not message.body.get("event_id") or not message.body.get("event_name"):
            raise PermanentMessageError("invalid_domain_contract")
        if transactional:
            async with delivery_transaction(factory) as session:
                await handler(session, message.body)
            await message.delete()
        else:
            receipt = await handler(None, message.body)
            await message.delete(receipt=receipt if isinstance(receipt, dict) else None)
    return invoke


@asynccontextmanager
async def domain_runtime(source, subscriptions=None, *, factory=None, policies=None, transactional=None):
    """Run a service's relay and subscriptions; no distributed business coordinator."""
    factory = factory or get_session_factory()
    broker = create_messaging_client(get_settings())
    queues = {name: QueueClient.from_settings(get_settings(), name) for name in (subscriptions or {})}

    from scaffold.messaging.processing import DurableDelivery
    from scaffold.messaging.worker import QueueWorkerRunner
    stop = asyncio.Event()

    async def relay():
        while not stop.is_set():
            try:
                worked = await relay_once(factory, broker, source)
                if not worked:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("domain_relay_failed source=%s", source)
                await asyncio.sleep(5)
    try:
        await broker.connect()
        for queue in queues.values():
            await queue.connect()
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(relay(), name=f"outbox:{source}")
            for name, handler in (subscriptions or {}).items():
                queue = queues[name]
                runner = QueueWorkerRunner(
                    queue=queue, handler=_domain_handler(factory, handler, transactional=(transactional or {}).get(name, True)), reconnect=queue.reconnect,
                    delivery=DurableDelivery(factory, name, source=source, policy=(policies or {}).get(name)),
                    continuous=True, message_timeout_s=300, idle_sleep_s=0.1,
                )
                tasks.create_task(runner.run(stop), name=f"domain:{name}")
            try:
                yield
            finally:
                # TaskGroup propagates background failures to the owning service
                # instead of silently leaving its domain consumer dead.
                stop.set()
    finally:
        stop.set()
        await broker.close()
        for queue in queues.values():
            await queue.close()
