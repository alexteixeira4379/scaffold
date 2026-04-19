import pytest

from scaffold.config import MessagingBackend, Settings
from scaffold.messaging.memory import InMemoryMessaging
from scaffold.messaging.queue_client import QueueClient


@pytest.mark.asyncio
async def test_queue_client_publish_read_delete() -> None:
    broker = InMemoryMessaging()
    q = QueueClient(broker, "tasks.x")
    await q.connect()
    await q.publish({"k": 1})
    msg = await q.read()
    assert msg is not None
    assert msg.body == {"k": 1}
    assert msg.read_count == 1
    assert msg.queue_name == "tasks.x"
    await q.delete(msg)
    assert await q.read() is None
    await q.close()


@pytest.mark.asyncio
async def test_queue_client_read_count_after_release() -> None:
    broker = InMemoryMessaging()
    q = QueueClient(broker, "tasks.y")
    await q.connect()
    await q.publish({"n": 2})
    first = await q.read()
    assert first is not None
    assert first.read_count == 1
    await first.release(requeue=True)
    second = await q.read()
    assert second is not None
    assert second.read_count == 2
    await q.delete(second)
    await q.close()


@pytest.mark.asyncio
async def test_fetched_double_delete() -> None:
    broker = InMemoryMessaging()
    q = QueueClient(broker, "tasks.z")
    await q.connect()
    await q.publish({})
    msg = await q.read()
    assert msg is not None
    await q.delete(msg)
    with pytest.raises(RuntimeError):
        await msg.delete()
    await q.close()


@pytest.mark.asyncio
async def test_queue_client_from_settings_memory() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "messaging_backend": MessagingBackend.MEMORY,
        },
    )
    q = QueueClient.from_settings(settings, "q.from_settings")
    await q.connect()
    await q.publish({"a": True})
    m = await q.read()
    assert m is not None and m.body == {"a": True}
    await q.delete(m)
    await q.close()
