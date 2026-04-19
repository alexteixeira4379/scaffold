from __future__ import annotations

from scaffold.config import Settings
from scaffold.messaging.contracts import OutboundMessage
from scaffold.messaging.factory import create_messaging_client
from scaffold.messaging.ports import FetchedMessage, MessagingPort


class QueueClient:
    def __init__(self, broker: MessagingPort, queue_name: str, *, durable: bool = True) -> None:
        self._broker = broker
        self._queue_name = queue_name
        self._durable = durable

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        queue_name: str,
        *,
        durable: bool = True,
    ) -> QueueClient:
        return cls(create_messaging_client(settings), queue_name, durable=durable)

    async def connect(self) -> None:
        await self._broker.connect()

    async def close(self) -> None:
        await self._broker.close()

    async def publish(
        self,
        body: dict[str, object],
        *,
        correlation_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        await self._broker.publish(
            OutboundMessage(
                queue=self._queue_name,
                body=body,
                correlation_id=correlation_id,
                headers=dict(headers or {}),
            ),
        )

    async def read(self) -> FetchedMessage | None:
        msg = await self._broker.fetch_one(self._queue_name, durable=self._durable)
        if msg is not None and msg.queue_name != self._queue_name:
            raise RuntimeError("queue mismatch")
        return msg

    async def delete(self, message: FetchedMessage) -> None:
        if message.queue_name != self._queue_name:
            raise ValueError("message does not belong to this queue")
        await message.delete()
