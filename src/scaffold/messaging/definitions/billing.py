"""Billing, payment, and notification queue topology."""

from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)


def _dead_lettered_queue(name: str) -> tuple[list[ExchangeDefinition], list[QueueDefinition], list[BindingDefinition]]:
    dlx = f"{name}.dlx"
    dlq = f"{name}.dlq"
    return (
        [ExchangeDefinition(name=dlx, type="direct", durable=True)],
        [
            QueueDefinition(
                name=name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": dlx,
                    "x-dead-letter-routing-key": dlq,
                },
            ),
            QueueDefinition(name=dlq, durable=True),
        ],
        [BindingDefinition(source=dlx, destination=dlq, routing_key=dlq)],
    )


_QUEUE_NAMES = [
    # Payment webhook -> billing worker
    "payment_event.process",
    # Billing worker outputs (consumed by notification-router)
    "payment.confirmed",
    "payment.failed",
    "subscription.activated",
    "subscription.suspended",
    "subscription.cancelled",
    # Notification-router inputs (from other services)
    "conversation.reply.composed",
    "application.submitted",
    "application.failed",
    # Notification-router outputs (consumed by whatsapp/email/sns workers)
    "notification.send_whatsapp",
    "notification.send_email",
    "notification.publish_sns",
    # Resume
    "resume.generate",
    "resume.generated",
]

_exchanges: list[ExchangeDefinition] = []
_queues: list[QueueDefinition] = []
_bindings: list[BindingDefinition] = []

for _name in _QUEUE_NAMES:
    _ex, _qu, _bi = _dead_lettered_queue(_name)
    _exchanges.extend(_ex)
    _queues.extend(_qu)
    _bindings.extend(_bi)

billing_topology = MessagingTopology(
    exchanges=_exchanges,
    queues=_queues,
    bindings=_bindings,
)
