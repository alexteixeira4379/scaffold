from scaffold.config import MessagingBackend, Settings
from scaffold.messaging.memory import InMemoryMessaging
from scaffold.messaging.ports import MessagingPort
from scaffold.messaging.rabbitmq import RabbitMQMessaging


def create_messaging_client(settings: Settings) -> MessagingPort:
    backend = settings.messaging_backend
    if backend == MessagingBackend.MEMORY:
        return InMemoryMessaging()
    if backend == MessagingBackend.RABBITMQ:
        url = settings.rabbitmq_url
        if not url:
            raise ValueError("rabbitmq_url is required when messaging_backend is rabbitmq")
        return RabbitMQMessaging(url)
    raise ValueError(f"unsupported messaging_backend: {backend!r}")
