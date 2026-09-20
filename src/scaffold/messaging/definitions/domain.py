"""One subscription per owner. Never share a queue between domains."""

from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)

DOMAIN_EXCHANGE = "jobito.domain"
SUBSCRIPTIONS = {
    "candidate.lifecycle": ("subscription.#", "auth.contact.verified"),
    "resume.lifecycle": (
        "billing.access.reconciled",
        "payment.confirmed",
        "candidate.profile.completed",
        "resume.builder.completed",
    ),
    "billing.workflow": ("payment.confirmed",),
    "conversation.lifecycle": ("payment.confirmed",),
    "matching.lifecycle": (
        "candidate.search.changed",
        "subscription.#",
        "resume.available",
        "linkedin.session.available",
        "linkedin.session.invalidated",
    ),
    "eligibility.lifecycle": ("candidate.search.changed", "candidate.catalog.page"),
    "linkedin-application.lifecycle": ("linkedin.session.available",),
    "collection.lifecycle": ("candidate.search.changed",),
    "tracking.lifecycle": ("subscription.activated",),
    "tracking.meta": ("subscription.activated",),
    "tracking.ga4": ("subscription.activated",),
    "tracking.tiktok": ("subscription.activated",),
    "notification.lifecycle": (
        "opportunity.available",
        "subscription.activated",
        "subscription.suspended",
        "subscription.cancelled",
        "payment.confirmed",
        "payment.failed",
    ),
}


def domain_topology():
    exchanges = [ExchangeDefinition(name=DOMAIN_EXCHANGE, type="topic", durable=True)]
    queues, bindings = [], []
    for queue, patterns in SUBSCRIPTIONS.items():
        queues.extend(
            [
                QueueDefinition(
                    name=queue,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": queue + ".dlq",
                    },
                ),
                QueueDefinition(name=queue + ".dlq", durable=True),
                QueueDefinition(
                    name=queue + ".retry",
                    durable=True,
                    arguments={
                        "x-message-ttl": 10000,
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": queue,
                    },
                ),
            ]
        )
        bindings.extend(
            BindingDefinition(source=DOMAIN_EXCHANGE, destination=queue, routing_key=pattern)
            for pattern in patterns
        )
    return MessagingTopology(exchanges=exchanges, queues=queues, bindings=bindings)
