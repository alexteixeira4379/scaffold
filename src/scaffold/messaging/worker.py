from __future__ import annotations

import asyncio
import inspect
import logging
import json
import re
from collections.abc import Awaitable, Callable

from scaffold.messaging.ports import FetchedMessage
from scaffold.messaging.queue_client import QueueClient


def _default_trace_id(message: FetchedMessage) -> str:
    cid = getattr(message, "correlation_id", None)
    if isinstance(cid, str) and cid.strip():
        return cid.strip()
    return "<missing>"


class QueueWorkerRunner:
    def __init__(
        self,
        *,
        queue: QueueClient,
        handler: Callable[[FetchedMessage], Awaitable[None]],
        reconnect: Callable[[], Awaitable[None]],
        idle_sleep_s: float = 1.0,
        message_timeout_s: float = 0.0,
        logger: logging.Logger | None = None,
        trace_id: Callable[[FetchedMessage], str] = _default_trace_id,
        on_collected: Callable[[FetchedMessage], Awaitable[None] | None] | None = None,
        max_in_flight: int = 1,
        drain_timeout_s: float = 180.0,
        delivery=None,
        continuous: bool = False,
        max_in_flight_bytes: int = 128 * 1024 * 1024,
        progress_report_interval_s: float = 30.0,
        no_progress_s: float = 300.0,
    ) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be positive")
        if drain_timeout_s <= 0:
            raise ValueError("drain_timeout_s must be positive")
        if min(progress_report_interval_s, no_progress_s) <= 0:
            raise ValueError("progress intervals must be positive")
        self._queue = queue
        self._handler = handler
        self._reconnect = reconnect
        self._idle_sleep_s = min(0.1, max(0.05, idle_sleep_s)) if continuous else max(0.05, idle_sleep_s)
        self._message_timeout_s = max(0.0, message_timeout_s)
        self._logger = logger or logging.getLogger(__name__)
        self._trace_id = trace_id
        self._on_collected = on_collected
        self._max_in_flight = max_in_flight
        self._drain_timeout_s = drain_timeout_s
        self._reconnect_lock = asyncio.Lock()
        self._reconnect_pending: str | None = None
        self._delivery = delivery
        self._continuous = continuous
        self._pause_until = 0.0
        self._infrastructure_failures = 0
        self._last_report = 0.0
        self._progress_report_interval_s = progress_report_interval_s
        self._no_progress_s = no_progress_s
        self._last_delivery = 0.0
        self._unresolved_deliveries: dict[str, float] = {}
        if delivery and max_in_flight * delivery.policy.max_transport_bytes > max_in_flight_bytes:
            raise ValueError("max_in_flight exceeds the configured payload memory budget")

    async def run(self, stop_event: asyncio.Event) -> None:
        active: set[asyncio.Task[None]] = set()
        if self._continuous:
            await self._queue.start_consumer(prefetch_count=self._max_in_flight)
        try:
            await self._run_until_stopped(stop_event, active)
        finally:
            if active:
                done, pending = await asyncio.wait(active, timeout=self._drain_timeout_s)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    if not task.cancelled() and task.exception():
                        self._logger.error("message task failed during drain", exc_info=task.exception())
            if self._continuous:
                await self._queue.stop_consumer()

    async def _run_until_stopped(self, stop_event: asyncio.Event, active: set[asyncio.Task[None]]) -> None:
        while not stop_event.is_set():
            now = asyncio.get_running_loop().time()
            if self._delivery and now - self._last_report >= self._progress_report_interval_s:
                self._report_progress(len(active), now)
            remaining = self._pause_until - asyncio.get_running_loop().time()
            if remaining > 0:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=min(remaining, 1))
                except TimeoutError:
                    pass
                continue
            if self._reconnect_pending:
                if active:
                    stop_waiter = asyncio.create_task(stop_event.wait())
                    try:
                        await asyncio.wait({*active, stop_waiter}, timeout=self._progress_report_interval_s,
                                           return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        stop_waiter.cancel()
                    continue
                label, self._reconnect_pending = self._reconnect_pending, None
                await self._safe_reconnect(label)
                continue
            if len(active) >= self._max_in_flight:
                stop_waiter = asyncio.create_task(stop_event.wait())
                try:
                    await asyncio.wait({*active, stop_waiter}, timeout=self._progress_report_interval_s,
                                       return_when=asyncio.FIRST_COMPLETED)
                finally:
                    stop_waiter.cancel()
                continue
            try:
                message = await self._queue.read()
            except Exception as exc:
                self._logger.warning("message_read_failed error_class=%s", type(exc).__name__)
                self._reconnect_pending = "reconnect_after_read_failure"
                if self._delivery:
                    self._infrastructure_pause()
                else:
                    await asyncio.sleep(self._idle_sleep_s)
                continue

            if message is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._idle_sleep_s)
                except TimeoutError:
                    pass
                continue

            task = asyncio.create_task(self._process(message))
            active.add(task)
            def completed(task):
                active.discard(task)
                if not task.cancelled() and task.exception():
                    self._logger.error("delivery_task_failed error_class=%s", type(task.exception()).__name__)
            task.add_done_callback(completed)

    async def _process(self, message: FetchedMessage) -> None:
        if self._delivery is not None:
            await self._process_durable(message)
            return
        traced = self._trace_id(message)
        self._logger.info(
            "collected queue=%s correlation_id=%s read_count=%s",
            message.queue_name,
            traced,
            message.read_count,
        )
        try:
            if getattr(message, "decode_error", None):
                await message.release(requeue=False)
                return
            if self._on_collected is not None:
                maybe_awaitable = self._on_collected(message)
                if maybe_awaitable is not None and inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
            if self._message_timeout_s > 0:
                await asyncio.wait_for(self._handler(message), timeout=self._message_timeout_s)
            else:
                await self._handler(message)
        except TimeoutError:
            self._logger.exception(
                "message_processing_timeout; releasing for retry correlation_id=%s timeout_s=%s",
                traced,
                self._message_timeout_s,
            )
            await self._safe_release(message, traced, "reconnect_after_timeout_release_failure")
        except Exception:
            self._logger.exception("unhandled error processing message; releasing for retry")
            await self._safe_release(message, traced, "reconnect_after_release_failure")

    async def _safe_release(self, message: FetchedMessage, traced: str, reconnect_err: str) -> None:
        try:
            await message.release(requeue=True)
        except Exception:  # noqa: BLE001 - release errors must preserve the delivery for reconnect
            self._logger.warning("release_failed message may redeliver correlation_id=%s", traced)
            self._reconnect_pending = reconnect_err

    async def _safe_reconnect(self, label: str) -> None:
        async with self._reconnect_lock:
            try:
                await self._reconnect()
            except Exception as exc:
                self._logger.warning("queue_reconnect_failed error_class=%s", type(exc).__name__)
                self._reconnect_pending = label
                if self._delivery:
                    self._infrastructure_pause()
                else:
                    await asyncio.sleep(self._idle_sleep_s)

    def _infrastructure_pause(self):
        self._infrastructure_failures = min(self._infrastructure_failures + 1, 6)
        delay = min(60, self._delivery.policy.infrastructure_backoff * 2 ** (self._infrastructure_failures - 1))
        self._pause_until = max(self._pause_until, asyncio.get_running_loop().time() + delay)
        return delay

    def _report_progress(self, active_count: int, now: float):
        self._last_report = now
        self._logger.info("worker_metrics consumer=%s in_flight=%s unresolved=%s counters=%s",
                          self._delivery.consumer, active_count, len(self._unresolved_deliveries),
                          json.dumps(self._delivery.counters.values, sort_keys=True))
        # Preserved/requeued deliveries remain known pending work while the
        # circuit is open, even after their task released its worker slot.
        if (active_count or self._unresolved_deliveries) and now - self._delivery.counters.last_progress >= self._no_progress_s:
            self._logger.error("worker_no_progress consumer=%s in_flight=%s unresolved=%s",
                               self._delivery.consumer, active_count, len(self._unresolved_deliveries))

    async def _pause_delivery(self, message, reason: str) -> None:
        from scaffold.messaging.processing import event_identity
        identity = event_identity(message, self._delivery.policy.identity_fields)
        self._unresolved_deliveries.setdefault(identity, asyncio.get_running_loop().time())
        delay = self._infrastructure_pause()
        self._logger.warning("worker_paused consumer=%s reason=%s delay_s=%s",
                             self._delivery.consumer, reason, delay)
        if not getattr(message, "finalized", False):
            await self._safe_release(message, _default_trace_id(message), "preserve_delivery_failed")

    async def _process_durable(self, message) -> None:
        from scaffold.messaging.processing import (
            DeferredMessage, DuplicateEvent, FailureKind, InfrastructureUnavailable, ManagedMessage,
            PermanentMessageError, ReconciliationRequired, RetryableMessageError,
            classify_failure, current_delivery, encoded_body,
            event_identity,
        )
        context = None
        self._last_delivery = asyncio.get_running_loop().time()
        self._delivery.counters.increment("received")
        try:
            context = await self._delivery.claim(message)
            if context is None:
                await message.delete()
                self._unresolved_deliveries.pop(event_identity(message, self._delivery.policy.identity_fields), None)
                self._delivery.counters.increment("duplicate")
                return
            managed = ManagedMessage(message, context.failures + 1)
            failure = None
            token = current_delivery.set(context)
            try:
                if context.expired_external:
                    raise ReconciliationRequired("expired_external_execution")
                if context.failures >= self._delivery.policy.max_attempts:
                    raise PermanentMessageError("attempt_budget_exhausted")
                if getattr(message, "decode_error", None):
                    raise PermanentMessageError("invalid_json")
                if len(encoded_body(message)) > self._delivery.policy.max_message_bytes:
                    raise PermanentMessageError("message_byte_limit")

                async def invoke():
                    if self._on_collected:
                        result = self._on_collected(managed)
                        if inspect.isawaitable(result):
                            await result
                    await self._handler(managed)

                async def heartbeat():
                    while True:
                        await asyncio.sleep(self._delivery.policy.lease_seconds / 3)
                        await self._delivery.heartbeat(context)

                task = asyncio.create_task(invoke())
                lease = asyncio.create_task(heartbeat())
                try:
                    done, _ = await asyncio.wait(
                        {task, lease}, timeout=self._message_timeout_s or None,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        if self._delivery.policy.external_effects:
                            raise ReconciliationRequired("external_execution_timeout")
                        raise TimeoutError()
                    if lease in done:
                        try:
                            lease.result()
                        except Exception as exc:
                            if self._delivery.policy.external_effects:
                                raise ReconciliationRequired("external_heartbeat_failed") from exc
                            raise InfrastructureUnavailable("heartbeat_failed") from exc
                    await task
                finally:
                    for child in (task, lease):
                        if not child.done():
                            child.cancel()
                    await asyncio.gather(task, lease, return_exceptions=True)
                if not managed.finalized:
                    raise PermanentMessageError("handler_returned_without_outcome")
            except DuplicateEvent:
                managed.finalized = True
            except Exception as exc:
                failure = exc
                if self._delivery.policy.external_effects:
                    safe = isinstance(exc, (DeferredMessage, PermanentMessageError, RetryableMessageError,
                                            InfrastructureUnavailable))
                    if not safe and not isinstance(exc, ReconciliationRequired):
                        failure = ReconciliationRequired("external_execution_uncertain")
            finally:
                current_delivery.reset(token)
            outcome = await self._delivery.finish(context, message, failure=failure,
                                                  transfer=managed.transfer_intent, receipt=managed.receipt)
            if failure and classify_failure(failure) == FailureKind.INFRASTRUCTURE:
                await self._pause_delivery(message, type(failure).__name__)
                return
            # Only the transport ACK lives here; if it is ambiguous the durable
            # outcome will suppress effects on the next broker delivery.
            await message.delete()
            if isinstance(failure, DeferredMessage) and failure.pause_consumer:
                self._pause_until = max(self._pause_until, asyncio.get_running_loop().time() + failure.delay_seconds)
                self._logger.info("worker_deferred consumer=%s reason=%s delay_s=%s",
                                  self._delivery.consumer, str(failure), failure.delay_seconds)
            self._unresolved_deliveries.pop(context.event_id, None)
            self._infrastructure_failures = 0
            self._logger.debug("delivery_finished consumer=%s outcome=%s", self._delivery.consumer, outcome)
        except asyncio.CancelledError:
            # Connection close returns unacked deliveries. Lease expiry recovers
            # interrupted local work; external work requires reconciliation.
            raise
        except Exception as exc:
            from sqlalchemy.exc import DBAPIError
            reason = type(exc).__name__
            if isinstance(exc, DBAPIError):
                args = getattr(exc.orig, "args", ())
                if args and isinstance(args[0], int):
                    reason += ":" + str(args[0])
            elif isinstance(exc, InfrastructureUnavailable) and re.fullmatch(r"[a-z][a-z0-9_]{0,80}", str(exc)):
                reason += ":" + str(exc)
            await self._pause_delivery(message, reason)
