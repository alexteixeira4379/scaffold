from collections.abc import Awaitable, Callable
from typing import Protocol

from scaffold.messaging.contracts import OutboundMessage, QueueSubscription


class FetchedMessage:
    __slots__ = (
        "body",
        "read_count",
        "correlation_id",
        "_queue_name",
        "_finalized",
        "_ack",
        "_nack",
    )

    def __init__(
        self,
        body: dict[str, object],
        read_count: int,
        correlation_id: str | None,
        queue_name: str,
        ack: Callable[[], Awaitable[None]],
        nack: Callable[[bool], Awaitable[None]],
    ) -> None:
        self.body = body
        self.read_count = read_count
        self.correlation_id = correlation_id
        self._queue_name = queue_name
        self._finalized = False
        self._ack = ack
        self._nack = nack

    @property
    def queue_name(self) -> str:
        return self._queue_name

    async def delete(self) -> None:
        if self._finalized:
            raise RuntimeError("already finalized")
        await self._ack()
        self._finalized = True

    async def release(self, requeue: bool = True) -> None:
        if self._finalized:
            raise RuntimeError("already finalized")
        await self._nack(requeue)
        self._finalized = True


class ConsumedEnvelope:
    __slots__ = ("body", "correlation_id", "routing_key", "_ack", "_nack")

    def __init__(
        self,
        body: dict[str, object],
        routing_key: str,
        correlation_id: str | None,
        ack: Callable[[], Awaitable[None]],
        nack: Callable[[bool], Awaitable[None]],
    ) -> None:
        self.body = body
        self.routing_key = routing_key
        self.correlation_id = correlation_id
        self._ack = ack
        self._nack = nack

    async def ack(self) -> None:
        await self._ack()

    async def nack(self, requeue: bool = False) -> None:
        await self._nack(requeue)


class MessagingPort(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def publish(self, message: OutboundMessage) -> None: ...

    async def consume(
        self,
        subscription: QueueSubscription,
        handler: Callable[[ConsumedEnvelope], Awaitable[None]],
    ) -> None: ...

    async def fetch_one(self, queue_name: str, *, durable: bool = True) -> FetchedMessage | None: ...
