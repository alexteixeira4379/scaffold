from scaffold.config import MessagingBackend, Settings
from scaffold.messaging.memory import InMemoryMessaging
from scaffold.messaging.ports import MessagingPort


def create_messaging_client(settings: Settings) -> MessagingPort:
    backend = settings.messaging_backend
    if backend == MessagingBackend.MEMORY:
        return InMemoryMessaging()
    if backend == MessagingBackend.RABBITMQ:
        from scaffold.messaging.rabbitmq import RabbitMQMessaging

        url = settings.rabbitmq_url
        if not url:
            raise ValueError("rabbitmq_url is required when messaging_backend is rabbitmq")
        return RabbitMQMessaging(
            url,
            heartbeat_s=settings.rabbitmq_heartbeat_s,
            timeout_s=settings.rabbitmq_timeout_s,
        )
    raise ValueError(f"unsupported messaging_backend: {backend!r}")
