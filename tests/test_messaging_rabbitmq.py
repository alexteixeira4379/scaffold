from __future__ import annotations

import types
from types import SimpleNamespace

import pytest

from scaffold.config import MessagingBackend, Settings
from scaffold.messaging.factory import create_messaging_client
from scaffold.messaging.rabbitmq import RabbitMQMessaging


class FakeChannel:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    async def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()

    async def channel(self, **kwargs) -> FakeChannel:
        self.channel_instance.kwargs = kwargs
        return self.channel_instance

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_rabbitmq_connect_uses_heartbeat_and_timeout(monkeypatch) -> None:
    calls = []

    async def connect_robust(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeConnection()

    monkeypatch.setitem(
        __import__("sys").modules,
        "aio_pika",
        types.SimpleNamespace(connect_robust=connect_robust),
    )

    broker = RabbitMQMessaging(
        "amqp://guest:guest@localhost:5672/",
        heartbeat_s=45,
        timeout_s=7.5,
    )

    await broker.connect()
    await broker.close()

    assert calls == [
        {
            "url": "amqp://guest:guest@localhost:5672/",
            "heartbeat": 45,
            "timeout": 7.5,
        }
    ]
    assert broker._channel is None
    assert broker._connection is None


@pytest.mark.asyncio
async def test_rabbitmq_connect_disables_publisher_confirms(monkeypatch) -> None:
    connection = FakeConnection()

    async def connect_robust(url: str, **kwargs):
        return connection

    monkeypatch.setitem(
        __import__("sys").modules,
        "aio_pika",
        types.SimpleNamespace(connect_robust=connect_robust),
    )

    broker = RabbitMQMessaging("amqp://guest:guest@localhost:5672/")

    await broker.connect()

    assert connection.channel_instance.kwargs == {"publisher_confirms": False}


def test_factory_passes_rabbitmq_connection_tuning() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "messaging_backend": MessagingBackend.RABBITMQ,
            "rabbitmq_url": "amqp://guest:guest@localhost:5672/",
            "rabbitmq_heartbeat_s": 20,
            "rabbitmq_timeout_s": 9.0,
        }
    )

    broker = create_messaging_client(settings)

    assert isinstance(broker, RabbitMQMessaging)
    assert broker._heartbeat_s == 20
    assert broker._timeout_s == 9.0


@pytest.mark.asyncio
async def test_rabbitmq_close_suppresses_already_closed_errors() -> None:
    class ClosedChannel:
        async def close(self) -> None:
            raise RuntimeError("channel already closed")

    class ClosedConnection:
        async def close(self) -> None:
            raise RuntimeError("connection already closed")

    broker = RabbitMQMessaging("amqp://guest:guest@localhost:5672/")
    broker._channel = ClosedChannel()
    broker._connection = ClosedConnection()

    await broker.close()

    assert broker._channel is None
    assert broker._connection is None


@pytest.mark.asyncio
async def test_rabbitmq_fetch_one_transfer_uses_channel_tx_methods() -> None:
    calls: list[tuple[str, object]] = []

    class IncomingChannel:
        is_closed = False

        async def tx_select(self) -> None:
            calls.append(("tx_select", None))

        async def basic_publish(self, body: bytes, **kwargs) -> None:
            calls.append(("basic_publish", {"body": body, **kwargs}))

        async def tx_commit(self) -> None:
            calls.append(("tx_commit", None))

        async def tx_rollback(self) -> None:
            calls.append(("tx_rollback", None))

        async def basic_ack(self, *, delivery_tag, multiple=False) -> None:
            calls.append(("basic_ack", {"delivery_tag": delivery_tag, "multiple": multiple}))

    class IncomingMessage:
        def __init__(self) -> None:
            self.channel = IncomingChannel()
            self.headers = {}
            self.redelivered = False
            self.correlation_id = "c1"
            self.body = b'{"id":"a1"}'
            self.delivery_tag = 11

        async def ack(self) -> None:
            await self.channel.basic_ack(delivery_tag=self.delivery_tag, multiple=False)

        async def nack(self, requeue: bool = False) -> None:
            raise AssertionError("nack should not be called")

    class Queue:
        async def get(self, fail=False, no_ack=False):
            return IncomingMessage()

    async def declare_queue(queue_name: str, durable: bool = True, passive: bool = True):
        return Queue()

    broker = RabbitMQMessaging("amqp://guest:guest@localhost:5672/")
    broker._channel = SimpleNamespace(declare_queue=declare_queue)

    message = await broker.fetch_one("job.ingestion")

    assert message is not None
    await message.transfer("job.ingestion.dlq", {"id": "a1", "status": "failed"}, correlation_id="c1")

    assert [name for name, _ in calls] == ["tx_select", "basic_publish", "basic_ack", "tx_commit"]
