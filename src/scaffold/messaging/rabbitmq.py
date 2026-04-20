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
    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: Any = None
        self._channel: Any = None

    async def connect(self) -> None:
        aio_pika = _import_aio_pika()
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def publish(self, message: OutboundMessage) -> None:
        aio_pika = _import_aio_pika()
        if self._channel is None:
            raise RuntimeError("not connected")
        body = json.dumps(message.body).encode()
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
        queue = await self._channel.declare_queue(queue_name, durable=durable)
        incoming = await queue.get(fail=False, no_ack=False)
        if incoming is None:
            return None

        async def ack() -> None:
            await incoming.ack()

        async def nack(requeue: bool = False) -> None:
            await incoming.nack(requeue=requeue)

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
        return FetchedMessage(body, read_count, correlation_id, queue_name, ack, nack)

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
