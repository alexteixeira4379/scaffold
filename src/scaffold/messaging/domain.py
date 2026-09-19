"""Transactional outbox, independent inboxes and background domain consumers."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, UTC
from uuid import uuid4

from sqlalchemy import select
from scaffold.config import get_settings
from scaffold.db.session import get_session_factory
from scaffold.models.domain_delivery import DomainOutbox, DomainInbox
from scaffold.messaging.contracts import OutboundMessage
from scaffold.messaging.factory import create_messaging_client
from scaffold.messaging.queue_client import QueueClient
from scaffold.messaging.definitions.domain import DOMAIN_EXCHANGE

logger = logging.getLogger(__name__)


async def enqueue(session, source, destination, payload, *, key, exchange="", available_at=None):
    existing = await session.scalar(
        select(DomainOutbox).where(DomainOutbox.source == source, DomainOutbox.dedupe_key == key)
    )
    if existing is not None:
        return existing
    row = DomainOutbox(
        source=source,
        destination=destination,
        exchange=exchange,
        dedupe_key=key,
        payload=payload,
        available_at=available_at or datetime.utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


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


async def relay_once(factory, broker, source):
    async with factory() as session, session.begin():
        row = await session.scalar(
            select(DomainOutbox)
            .where(
                DomainOutbox.source == source,
                DomainOutbox.delivered_at.is_(None),
                DomainOutbox.available_at <= datetime.utcnow(),
            )
            .order_by(DomainOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return False
        try:
            await broker.publish(
                OutboundMessage(
                    queue=row.destination,
                    exchange=row.exchange,
                    body=row.payload,
                    correlation_id=row.payload.get("correlation_id"),
                )
            )
        except Exception as exc:
            row.attempts += 1
            row.last_error = str(exc)[:2000]
            row.available_at = datetime.utcnow() + timedelta(
                seconds=min(300, 2 ** min(row.attempts, 8))
            )
            logger.exception("domain_outbox_pending source=%s id=%s", source, row.id)
        else:
            row.delivered_at = datetime.utcnow()
            row.last_error = None
    return True


async def consume_once(factory, queue, consumer, handler):
    message = await queue.read()
    if message is None:
        return False
    body = message.body
    event_id = body.get("event_id")
    if not event_id or not body.get("event_name"):
        await message.release(requeue=False)
        return True
    try:
        async with factory() as session, session.begin():
            # Inbox lookup must not establish a stale REPEATABLE READ snapshot
            # before the owning handler takes its aggregate lock.
            if session.bind.dialect.name == "mysql":
                await session.connection(execution_options={"isolation_level": "READ COMMITTED"})
            if await session.get(DomainInbox, (consumer, event_id)) is None:
                # Insert first: concurrent redelivery cannot run two effects.
                session.add(DomainInbox(consumer=consumer, event_id=event_id))
                await session.flush()
                await handler(session, body)
        await message.delete()
    except Exception:
        logger.exception("domain_consumer_failed consumer=%s event=%s", consumer, event_id)
        if message.read_count >= 8:
            await message.release(requeue=False)
        else:
            await message.transfer(
                queue.queue_name + ".retry",
                body,
                correlation_id=message.correlation_id,
                headers={"x-delivery-count": str(message.read_count + 1)},
            )
    return True


@asynccontextmanager
async def domain_runtime(source, subscriptions=None, *, factory=None):
    """Run a service's relay and subscriptions; no distributed business coordinator."""
    factory = factory or get_session_factory()
    broker = create_messaging_client(get_settings())
    await broker.connect()
    queues = {name: QueueClient(broker, name) for name in (subscriptions or {})}

    async def loop():
        while True:
            try:
                worked = await relay_once(factory, broker, source)
                for name, handler in (subscriptions or {}).items():
                    worked = await consume_once(factory, queues[name], name, handler) or worked
                if not worked:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("domain_runtime_failed source=%s", source)
                await asyncio.sleep(5)
                try:
                    await broker.close()
                    await broker.connect()
                except Exception:
                    logger.exception("domain_reconnect_pending source=%s", source)

    task = asyncio.create_task(loop(), name=f"domain:{source}")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await broker.close()
