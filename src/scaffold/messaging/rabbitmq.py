import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast

from scaffold.messaging.contracts import OutboundMessage, QueueSubscription
from scaffold.messaging.delivery import read_count_from_amqp
from scaffold.messaging.ports import ConsumedEnvelope, FetchedMessage

if TYPE_CHECKING:
    from aio_pika import IncomingMessage


def _import_aio_pika() -> Any:
    try:
        import aio_pika
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RabbitMQ support requires the 'aio-pika' package to be installed."
        ) from exc
    return aio_pika


class RabbitMQMessaging:
    def __init__(self, url: str, *, heartbeat_s: int = 30, timeout_s: float = 15.0) -> None:
        self._url = url
        self._heartbeat_s = heartbeat_s
        self._timeout_s = timeout_s
        self._connection: Any = None
        self._channel: Any = None

    async def connect(self) -> None:
        aio_pika = _import_aio_pika()
        self._connection = await aio_pika.connect_robust(
            self._url,
            heartbeat=self._heartbeat_s,
            timeout=self._timeout_s,
        )
        self._channel = await self._connection.channel(publisher_confirms=False)

    async def close(self) -> None:
        if self._channel is not None:
            try:
                await self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None

    async def publish(self, message: OutboundMessage) -> None:
        aio_pika = _import_aio_pika()
        if self._channel is None:
            raise RuntimeError("not connected")
        body = json.dumps(message.body, ensure_ascii=False).encode("utf-8")
        hdrs: dict[str, str] = dict(message.headers)
        amqp_message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=message.correlation_id or None,
            headers=cast(Any, hdrs or None),
        )
        await self._channel.default_exchange.publish(amqp_message, routing_key=message.queue)

    async def fetch_one(self, queue_name: str, *, durable: bool = True) -> FetchedMessage | None:
        if self._channel is None:
            raise RuntimeError("not connected")
        queue = await self._channel.declare_queue(queue_name, durable=durable, passive=True)
        incoming = await queue.get(fail=False, no_ack=False)
        if incoming is None:
            return None

        async def ack() -> None:
            await incoming.ack()

        async def nack(requeue: bool = False) -> None:
            await incoming.nack(requeue=requeue)

        async def transfer(
            destination_queue: str,
            destination_body: dict[str, object],
            destination_correlation_id: str | None,
            headers: dict[str, str] | None,
        ) -> None:
            aio_pika = _import_aio_pika()
            channel = incoming.channel
            body = json.dumps(destination_body, ensure_ascii=False).encode("utf-8")
            hdrs: dict[str, str] = dict(headers or {})
            amqp_message = aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=destination_correlation_id or None,
                headers=cast(Any, hdrs or None),
            )
            async with channel.transaction():
                await channel.default_exchange.publish(amqp_message, routing_key=destination_queue)
                await incoming.ack()

        hdrs = incoming.headers
        read_count = read_count_from_amqp(bool(incoming.redelivered), hdrs)
        correlation_id = incoming.correlation_id
        try:
            parsed = json.loads(incoming.body.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            await incoming.nack(requeue=False)
            return None
        if not isinstance(parsed, dict):
            await incoming.nack(requeue=False)
            return None
        body: dict[str, object] = {str(k): v for k, v in parsed.items()}
        return FetchedMessage(body, read_count, correlation_id, queue_name, ack, nack, transfer)

    async def consume(
        self,
        subscription: QueueSubscription,
        handler: Callable[[ConsumedEnvelope], Awaitable[None]],
    ) -> None:
        if self._channel is None:
            raise RuntimeError("not connected")
        queue = await self._channel.declare_queue(
            subscription.queue_name,
            durable=subscription.durable,
            passive=True,
        )
        await self._channel.set_qos(prefetch_count=subscription.prefetch_count)
        async with queue.iterator() as queue_iter:
            async for incoming in queue_iter:
                await self._dispatch_incoming(incoming, handler)

    async def _dispatch_incoming(
        self,
        incoming: "IncomingMessage",
        handler: Callable[[ConsumedEnvelope], Awaitable[None]],
    ) -> None:
        acked = False
        nacked = False

        async def ack() -> None:
            nonlocal acked
            await incoming.ack()
            acked = True

        async def nack(requeue: bool = False) -> None:
            nonlocal nacked
            await incoming.nack(requeue=requeue)
            nacked = True

        routing_key = incoming.routing_key or ""
        correlation_id = incoming.correlation_id
        try:
            parsed = json.loads(incoming.body.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            await incoming.nack(requeue=False)
            return
        if not isinstance(parsed, dict):
            await incoming.nack(requeue=False)
            return
        body: dict[str, object] = {str(k): v for k, v in parsed.items()}
        env = ConsumedEnvelope(body, routing_key, correlation_id, ack, nack)
        try:
            await handler(env)
        except BaseException:
            if not acked and not nacked:
                await incoming.nack(requeue=True)
            raise
        if not acked and not nacked:
            await incoming.ack()
