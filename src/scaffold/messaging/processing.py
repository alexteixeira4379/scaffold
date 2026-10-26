"""Durable application delivery policy. Broker redelivery is never a retry budget."""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.exc import DBAPIError, IntegrityError, TimeoutError as PoolTimeout

from scaffold.models.domain_delivery import DomainInbox, WorkerDelivery, WorkerQuarantine


class PermanentMessageError(Exception):
    pass


class RetryableMessageError(Exception):
    pass


class InfrastructureUnavailable(Exception):
    pass


class ReconciliationRequired(Exception):
    pass


class DeferredMessage(Exception):
    """Wait for a dependency without spending the application failure budget."""
    def __init__(self, delay_seconds: float, reason: str = "dependency_pending", *, pause_consumer: bool = False):
        if delay_seconds <= 0:
            raise ValueError("deferral delay must be positive")
        super().__init__(reason)
        self.delay_seconds = delay_seconds
        self.pause_consumer = pause_consumer


class DuplicateEvent(Exception):
    """The local transaction already committed this event."""


class FailureKind(StrEnum):
    PERMANENT = "permanent"
    RETRY = "retry"
    INFRASTRUCTURE = "infrastructure"
    UNCERTAIN = "uncertain"
    DEFERRED = "deferred"


def classify_failure(exc: Exception) -> FailureKind:
    if isinstance(exc, DeferredMessage):
        return FailureKind.DEFERRED
    if isinstance(exc, ReconciliationRequired):
        return FailureKind.UNCERTAIN
    if isinstance(exc, InfrastructureUnavailable):
        return FailureKind.INFRASTRUCTURE
    if isinstance(exc, PermanentMessageError):
        return FailureKind.PERMANENT
    if isinstance(exc, RetryableMessageError):
        return FailureKind.RETRY
    if isinstance(exc, DBAPIError):
        args = getattr(exc.orig, "args", ())
        code = args[0] if args else None
        if code in {1205, 1213}:  # lock timeout / deadlock
            return FailureKind.RETRY
        if exc.connection_invalidated or code in {1040, 1042, 1047, 1129, 1130, 2002, 2003, 2006, 2013}:
            return FailureKind.INFRASTRUCTURE
        if code in {1048, 1264, 1292, 1366, 1406, 1452, 3819}:
            return FailureKind.PERMANENT
        # A duplicate unique key can be a concurrent insert, not bad data.
        return FailureKind.RETRY
    if isinstance(exc, (ConnectionError, OSError, PoolTimeout)):
        return FailureKind.INFRASTRUCTURE
    if isinstance(exc, (ValueError, TypeError, UnicodeError)):
        return FailureKind.PERMANENT
    return FailureKind.RETRY


def encoded_body(message) -> bytes:
    raw = getattr(message, "raw_body", None)
    if isinstance(raw, bytes):
        return raw
    return json.dumps(message.body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def event_identity(message, identity_fields: tuple[str, ...] = ()) -> str:
    headers = getattr(message, "headers", {}) or {}
    explicit = None
    if isinstance(message.body, dict):
        for name in identity_fields:
            if message.body.get(name):
                # Legacy intent IDs can be case-sensitive even on a CI MySQL
                # database. A lowercase digest also fits existing inbox keys.
                return hashlib.sha256(f"intent:{name}:{message.body[name]}".encode()).hexdigest()
    explicit = explicit or headers.get("x-event-id")
    if not explicit and isinstance(message.body, dict):
        explicit = message.body.get("event_id")
    explicit = explicit or getattr(message, "message_id", None)
    if explicit:
        if headers.get("x-event-key") == "sha256" and len(str(explicit)) == 64:
            return str(explicit)
        return str(explicit) if len(str(explicit)) <= 64 else hashlib.sha256(str(explicit).encode()).hexdigest()
    # Include observation metadata and correlation, not only job URL. Transport
    # attempt headers are deliberately excluded, so identity survives retries.
    canonical = encoded_body(message)
    if not getattr(message, "decode_error", None):
        canonical = json.dumps(message.body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(message.queue_name.encode() + b"\0" +
                          str(message.correlation_id or "").encode() + b"\0" + canonical).hexdigest()


@dataclass(frozen=True)
class DeliveryPolicy:
    max_attempts: int = 5
    retry_delays: tuple[float, ...] = (10, 60, 300, 900)
    lease_seconds: float = 360
    infrastructure_backoff: float = 5
    max_message_bytes: int = 8 * 1024 * 1024
    max_transport_bytes: int = 16 * 1024 * 1024
    quarantine_inline_bytes: int = 16 * 1024 * 1024
    external_effects: bool = False
    identity_fields: tuple[str, ...] = ()

    def __post_init__(self):
        if self.max_attempts < 1 or not self.retry_delays or min(self.retry_delays) <= 0:
            raise ValueError("positive attempts and retry delays required")
        if min(self.lease_seconds, self.infrastructure_backoff, self.max_message_bytes, self.max_transport_bytes,
               self.quarantine_inline_bytes) <= 0:
            raise ValueError("positive delivery bounds required")
        if self.max_message_bytes > self.max_transport_bytes:
            raise ValueError("application message limit exceeds transport limit")

    def delay(self, attempt: int) -> float:
        base = self.retry_delays[min(max(0, attempt - 1), len(self.retry_delays) - 1)]
        return base * random.uniform(1, 1.2)


@dataclass
class DeliveryContext:
    consumer: str
    event_id: str
    attempt: int
    token: str
    sequence: int = 0
    expired_external: bool = False
    failures: int = 0


current_delivery: ContextVar[DeliveryContext | None] = ContextVar("worker_delivery", default=None)


@asynccontextmanager
async def delivery_transaction(factory, *, consumer=None, event_id=None):
    """Inbox and local effects share this transaction; duplicates execute no effects.

    Use once for the owning mutation, not for read-only preparation transactions.
    Outside a managed delivery it behaves as a regular transaction.
    """
    context = current_delivery.get()
    inbox_key = (context.consumer, context.event_id) if context else (
        (consumer, event_id) if consumer and event_id else None
    )
    if (consumer is None) != (event_id is None):
        raise ValueError("consumer and event_id must be supplied together")
    async with factory() as session, session.begin():
        if inbox_key:
            if session.bind.dialect.name == "mysql":
                await session.connection(execution_options={"isolation_level": "READ COMMITTED"})
            prior = await session.get(DomainInbox, inbox_key, with_for_update=True)
            if prior is not None:
                raise DuplicateEvent()
            if session.bind.dialect.name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert
                result = await session.execute(insert(DomainInbox).values(
                    consumer=inbox_key[0], event_id=inbox_key[1],
                ).on_conflict_do_nothing())
                if not result.rowcount:
                    raise DuplicateEvent()
            else:
                try:
                    async with session.begin_nested():
                        session.add(DomainInbox(consumer=inbox_key[0], event_id=inbox_key[1]))
                        await session.flush()
                except IntegrityError as exc:
                    raise DuplicateEvent() from exc
        yield session
        if context:
            # Fence the commit, not the whole handler: a slow/stalled owner must
            # not commit after another replica acquired an expired lease.
            owner = await session.get(WorkerDelivery, (context.consumer, context.event_id),
                                      with_for_update=True, populate_existing=True)
            if (owner is None or owner.claim_token != context.token or
                    owner.status != "processing" or owner.claimed_until <= datetime.utcnow()):
                raise InfrastructureUnavailable("delivery_lease_lost_before_commit")


async def enqueue_output(session, source: str, destination: str, payload: dict, *, key: str | None = None):
    """Enqueue in the owning transaction, with stable output identity on retry."""
    from scaffold.messaging.domain import enqueue
    context = current_delivery.get()
    if key is None:
        if context is None:
            raise ValueError("an output key is required outside a managed delivery")
        context.sequence += 1
        key = f"delivery:{context.event_id}:{context.sequence}:{destination}"
    key = hashlib.sha256(key.encode()).hexdigest()
    output = dict(payload)
    output["event_id"] = str(uuid5(NAMESPACE_URL, f"jobito:{source}:{key}"))
    return await enqueue(session, source, destination, output, key=key)


@dataclass
class ProcessingCounters:
    values: dict[str, int] = field(default_factory=dict)
    last_progress: float = field(default_factory=time.monotonic)

    def increment(self, outcome: str):
        self.values[outcome] = self.values.get(outcome, 0) + 1
        if outcome == "completed":
            self.last_progress = time.monotonic()


class DurableDelivery:
    def __init__(self, factory, consumer: str, *, policy: DeliveryPolicy | None = None,
                 storage=None, source: str | None = None):
        if not consumer or len(consumer) > 64:
            raise ValueError("consumer must contain 1..64 characters")
        self.factory = factory
        self.consumer = consumer
        self.source = source or consumer
        self.policy = policy or DeliveryPolicy()
        self.storage = storage
        self.counters = ProcessingCounters()

    async def claim(self, message):
        identity = event_identity(message, self.policy.identity_fields)
        now = datetime.utcnow()
        async with self.factory() as session, session.begin():
            if session.bind.dialect.name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert
                await session.execute(insert(WorkerDelivery).values(
                    consumer=self.consumer, event_id=identity, queue=message.queue_name,
                    status="pending", attempts=0, failures=0, retry_generation=0,
                ).on_conflict_do_nothing())
            elif session.bind.dialect.name == "mysql":
                from sqlalchemy.dialects.mysql import insert
                statement = insert(WorkerDelivery).values(
                    consumer=self.consumer, event_id=identity, queue=message.queue_name,
                    status="pending", attempts=0, failures=0, retry_generation=0,
                )
                # Insert/upsert before locking reads avoids gap-lock conversion
                # deadlocks when many new events arrive concurrently.
                await session.execute(statement.on_duplicate_key_update(
                    event_id=statement.inserted.event_id))
            row = await session.get(WorkerDelivery, (self.consumer, identity), with_for_update=True)
            if row is None:
                try:
                    async with session.begin_nested():
                        row = WorkerDelivery(consumer=self.consumer, event_id=identity,
                                             queue=message.queue_name, status="pending", attempts=0)
                        session.add(row)
                        await session.flush()
                except IntegrityError:
                    # The winner owns the event; never run a second handler.
                    raise InfrastructureUnavailable("concurrent_delivery_claim") from None
            if row.status in {"completed", "quarantined", "uncertain"}:
                return None
            if row.status == "retry" and row.next_attempt_at and row.next_attempt_at > now:
                generation = str((getattr(message, "headers", {}) or {}).get("x-retry-generation", ""))
                if generation != str(row.retry_generation):
                    return None  # the durable scheduled copy owns recovery
                # The relay released this generation already. A slower consumer
                # clock must not ACK and lose its sole scheduled recovery copy.
            if row.claimed_until and row.claimed_until > now:
                from scaffold.messaging.domain import enqueue
                headers = dict(getattr(message, "headers", {}) or {})
                headers.update({"x-event-id": identity, "x-event-key": "sha256"})
                if message.correlation_id:
                    headers["x-correlation-id"] = message.correlation_id
                await enqueue(session, self.source, message.queue_name, message.body,
                              key=f"busy:{self.consumer}:{identity}:{row.claim_token}",
                              available_at=row.claimed_until + timedelta(seconds=1), headers=headers,
                              raw_body=encoded_body(message))
                return None  # duplicate preserved durably; do not pause healthy work
            expired_external = row.status == "processing" and self.policy.external_effects
            if row.status == "processing" and not expired_external:
                row.failures += 1  # a crashed local attempt also spends budget
            token = str(uuid4())
            row.attempts += 1
            row.status, row.claim_token = "processing", token
            row.claimed_until = now + timedelta(seconds=self.policy.lease_seconds)
            row.updated_at = now
            return DeliveryContext(self.consumer, identity, row.attempts, token,
                                   expired_external=expired_external, failures=row.failures)

    async def heartbeat(self, context):
        from sqlalchemy import update
        async with self.factory() as session, session.begin():
            result = await session.execute(update(WorkerDelivery).where(
                WorkerDelivery.consumer == self.consumer,
                WorkerDelivery.event_id == context.event_id,
                WorkerDelivery.claim_token == context.token,
                WorkerDelivery.status == "processing",
            ).values(claimed_until=datetime.utcnow() + timedelta(seconds=self.policy.lease_seconds)))
            if not result.rowcount:
                raise InfrastructureUnavailable("delivery_lease_lost")

    async def finish(self, context, message, *, failure=None, transfer=None, receipt=None):
        kind = classify_failure(failure) if failure else None
        reason = type(failure).__name__ if failure else None
        if isinstance(failure, (DeferredMessage, PermanentMessageError, RetryableMessageError,
                                InfrastructureUnavailable, ReconciliationRequired)):
            code = str(failure)
            if re.fullmatch(r"[a-z][a-z0-9_]{0,80}", code):
                reason += ":" + code
        if isinstance(failure, DBAPIError):
            args = getattr(failure.orig, "args", ())
            if args and isinstance(args[0], int):
                reason += ":" + str(args[0])
        # Never persist exception strings: SQLAlchemy exceptions contain SQL and
        # bound values. Codes/classes are sufficient to group failures safely.
        raw = encoded_body(message)
        storage_key = None
        quarantine = kind in {FailureKind.PERMANENT, FailureKind.UNCERTAIN} or (
            kind == FailureKind.RETRY and context.failures + 1 >= self.policy.max_attempts
        )
        if quarantine and len(raw) > self.policy.quarantine_inline_bytes:
            storage_key = f"worker-quarantine/{self.consumer}/{hashlib.sha256(raw).hexdigest()}"
            if self.storage is not None:
                await self.storage.upload(storage_key, raw, content_type="application/octet-stream")
            else:
                bucket = os.getenv("WORKER_QUARANTINE_BUCKET", "").strip()
                if not bucket:
                    raise InfrastructureUnavailable("large_quarantine_requires_storage")
                from scaffold.config import get_settings
                from scaffold.storage import StorageClient
                storage = StorageClient.from_settings(get_settings(), bucket)
                await storage.connect()
                try:
                    await storage.upload(storage_key, raw, content_type="application/octet-stream")
                finally:
                    await storage.close()
        async with self.factory() as session, session.begin():
            row = await session.get(WorkerDelivery, (self.consumer, context.event_id), with_for_update=True)
            if row is None or row.claim_token != context.token:
                raise InfrastructureUnavailable("delivery_lease_lost")
            row.updated_at = datetime.utcnow()
            row.last_error = reason
            row.claim_token, row.claimed_until = None, None
            if kind == FailureKind.INFRASTRUCTURE:
                row.status = "pending"
            elif quarantine:
                if kind == FailureKind.RETRY:
                    row.failures += 1
                row.status = "uncertain" if kind == FailureKind.UNCERTAIN else "quarantined"
                session.add(WorkerQuarantine(
                    id=str(uuid4()), consumer=self.consumer, event_id=context.event_id,
                    queue=message.queue_name, correlation_id=message.correlation_id,
                    reason=reason, attempts=context.attempt, payload_sha256=hashlib.sha256(raw).hexdigest(),
                    raw_body=None if storage_key else raw, storage_key=storage_key,
                    headers=dict(getattr(message, "headers", {}) or {}),
                ))
            elif kind in {FailureKind.RETRY, FailureKind.DEFERRED}:
                from scaffold.messaging.domain import enqueue
                row.status = "retry"
                if kind == FailureKind.RETRY:
                    row.failures += 1
                row.retry_generation += 1
                delay = failure.delay_seconds if kind == FailureKind.DEFERRED else self.policy.delay(row.failures)
                row.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay)
                # Preserve exact bytes and metadata even if JSON parsing failed.
                payload = message.body
                headers = dict(getattr(message, "headers", {}) or {})
                headers.update({"x-event-id": context.event_id, "x-event-key": "sha256",
                                "x-application-attempt": str(context.attempt + 1),
                                "x-retry-generation": str(row.retry_generation)})
                if message.correlation_id:
                    headers["x-correlation-id"] = message.correlation_id
                await enqueue(session, self.source, message.queue_name, payload,
                              key=f"retry:{self.consumer}:{context.event_id}:{row.retry_generation}",
                              available_at=row.next_attempt_at, headers=headers, raw_body=raw)
            else:
                row.status = "completed"
                row.receipt = receipt
                if transfer:
                    from scaffold.messaging.domain import enqueue
                    destination, payload, correlation_id, headers = transfer
                    transfer_payload = dict(payload)
                    headers = dict(headers or {})
                    if correlation_id:
                        headers.setdefault("x-correlation-id", correlation_id)
                    await enqueue(session, self.source, destination, transfer_payload,
                                  key=f"transfer:{self.consumer}:{context.event_id}", headers=headers)
            outcome = row.status
        self.counters.increment(outcome)
        return outcome


class ManagedMessage:
    """Compatibility adapter: handlers declare intent; runtime owns broker ACK."""
    def __init__(self, message, attempt):
        self._message = message
        self.read_count = attempt
        self.finalized = False
        self.transfer_intent = None
        self.receipt = None

    def __getattr__(self, name):
        return getattr(self._message, name)

    async def delete(self, *, receipt=None):
        if self.finalized:
            raise PermanentMessageError("double_finalization")
        self.finalized = True
        self.receipt = receipt

    async def release(self, requeue=True):
        if self.finalized:
            raise PermanentMessageError("double_finalization")
        if requeue:
            raise RetryableMessageError("handler_requested_retry")
        raise PermanentMessageError("handler_rejected_message")

    async def transfer(self, queue_name, body, *, correlation_id=None, headers=None):
        if self.finalized:
            raise PermanentMessageError("double_finalization")
        self.transfer_intent = (queue_name, body, correlation_id, headers)
        self.finalized = True
