"""Dedicated email work lanes; inbound mail never subscribes to notifications."""

from scaffold.messaging.topology import MessagingTopology, QueueDefinition

EMAIL_INBOUND_QUEUE = "email.inbound"
EMAIL_FORWARDING_QUEUE = "email.forwarding"


def email_topology() -> MessagingTopology:
    queues = []
    for name in (EMAIL_INBOUND_QUEUE, EMAIL_FORWARDING_QUEUE):
        queues.extend(
            [
                QueueDefinition(
                    name=name,
                    arguments={
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": name + ".dlq",
                    },
                ),
                QueueDefinition(name=name + ".dlq"),
                QueueDefinition(
                    name=name + ".retry",
                    arguments={
                        "x-message-ttl": 10000,
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": name,
                    },
                ),
            ]
        )
    return MessagingTopology(queues=queues)
