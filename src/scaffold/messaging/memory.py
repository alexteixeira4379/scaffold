import asyncio
import json
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from scaffold.messaging.contracts import OutboundMessage, QueueSubscription
from scaffold.messaging.ports import ConsumedEnvelope, FetchedMessage


class InMemoryMessaging:
    def __init__(self) -> None:
        self._queues: dict[str, deque[bytes]] = defaultdict(deque)
        self._waiters: dict[str, list[asyncio.Queue[bytes | None]]] = defaultdict(list)
        self._pending: dict[str, dict[str, bytes]] = defaultdict(dict)
        self._closed = False

    async def connect(self) -> None:
        if self._closed:
            raise RuntimeError("closed")

    async def close(self) -> None:
        self._closed = True
        for key in list(self._waiters.keys()):
            for q in list(self._waiters[key]):
                await q.put(None)
        self._waiters.clear()
        self._pending.clear()
        self._queues.clear()

    async def publish(self, message: OutboundMessage) -> None:
        if self._closed:
            raise RuntimeError("closed")
        raw = json.dumps(
            {
                "body": message.body,
                "correlation_id": message.correlation_id,
                "headers": message.headers,
                "delivery_attempts": 0,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        key = message.queue
        if self._waiters[key]:
            w = self._waiters[key].pop(0)
            await w.put(raw)
        else:
            self._queues[key].append(raw)

    async def consume(
        self,
        subscription: QueueSubscription,
        handler: Callable[[ConsumedEnvelope], Awaitable[None]],
    ) -> None:
        if self._closed:
            raise RuntimeError("closed")
        name = subscription.queue_name
        while not self._closed:
            item = await self._next_delivery(name)
            if item is None:
                break
            data = json.loads(item.decode())
            body_obj = data["body"]
            if not isinstance(body_obj, dict):
                raise TypeError("body")
            body: dict[str, object] = {str(k): v for k, v in body_obj.items()}
            correlation_id = data.get("correlation_id")
            if correlation_id is not None and not isinstance(correlation_id, str):
                correlation_id = str(correlation_id)
            acked = False
            nacked = False

            async def ack() -> None:
                nonlocal acked
                acked = True

            async def nack(requeue: bool = False) -> None:
                nonlocal nacked
                nacked = True
                if requeue:
                    if self._waiters[name]:
                        w = self._waiters[name].pop(0)
                        await w.put(item)
                    else:
                        self._queues[name].appendleft(item)

            env = ConsumedEnvelope(body, name, correlation_id, ack, nack)
            try:
                await handler(env)
            except BaseException:
                if not acked and not nacked:
                    await nack(True)
                raise
            if not acked and not nacked:
                await ack()

    async def fetch_one(self, queue_name: str, *, durable: bool = True) -> FetchedMessage | None:
        del durable
        if self._closed:
            raise RuntimeError("closed")
        if not self._queues[queue_name]:
            return None
        raw = self._queues[queue_name].popleft()
        data = json.loads(raw.decode())
        body_obj = data.get("body")
        if not isinstance(body_obj, dict):
            raise TypeError("body")
        body: dict[str, object] = {str(k): v for k, v in body_obj.items()}
        correlation_id = data.get("correlation_id")
        if correlation_id is not None and not isinstance(correlation_id, str):
            correlation_id = str(correlation_id)
        attempts = data.get("delivery_attempts", 0)
        if not isinstance(attempts, int):
            attempts = 0
        attempts += 1
        data["delivery_attempts"] = attempts
        new_raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        token = uuid.uuid4().hex
        self._pending[queue_name][token] = new_raw

        async def ack() -> None:
            self._pending[queue_name].pop(token, None)

        async def nack(requeue: bool = False) -> None:
            self._pending[queue_name].pop(token, None)
            if requeue:
                self._queues[queue_name].appendleft(new_raw)

        async def transfer(
            destination_queue: str,
            destination_body: dict[str, object],
            destination_correlation_id: str | None,
            headers: dict[str, str] | None,
        ) -> None:
            if self._closed:
                raise RuntimeError("closed")
            outbound = OutboundMessage(
                queue=destination_queue,
                body=destination_body,
                correlation_id=destination_correlation_id,
                headers=dict(headers or {}),
            )
            await self.publish(outbound)
            self._pending[queue_name].pop(token, None)

        return FetchedMessage(body, attempts, correlation_id, queue_name, ack, nack, transfer)

    async def _next_delivery(self, name: str) -> bytes | None:
        if self._closed:
            return None
        if self._queues[name]:
            return self._queues[name].popleft()
        q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)
        self._waiters[name].append(q)
        try:
            v = await q.get()
            if v is None:
                return None
            return v
        finally:
            try:
                self._waiters[name].remove(q)
            except ValueError:
                pass
