"""One subscription per owner. Never share a queue between domains."""

from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)

DOMAIN_EXCHANGE = "jobito.domain"
SUBSCRIPTIONS = {
    "whatsapp.ingress": ("whatsapp.ingress.received",),
    "email.lifecycle": ("auth.contact.verified",),
    "candidate.lifecycle": ("subscription.#", "auth.contact.verified", "resume.builder.completed", "candidate.profile.completed"),
    "resume.lifecycle": (
        "billing.access.reconciled",
        "subscription.trial_started",
        "payment.confirmed",
        "candidate.profile.completed",
        "resume.builder.completed",
    ),
    "billing.workflow": ("payment.confirmed", "subscription.trial_started"),
    "conversation.lifecycle": ("payment.confirmed", "subscription.trial_started"),
    "matching.lifecycle": (
        "candidate.search.changed",
        "subscription.#",
        "resume.available",
        "linkedin.session.available",
        "linkedin.session.invalidated",
    ),
    "catalog-replay.lifecycle": ("candidate.search.activated", "candidate.catalog.replay.page"),
    "linkedin-application.lifecycle": ("linkedin.session.available",),
    "collection.lifecycle": ("candidate.search.changed",),
    "tracking.lifecycle": ("subscription.activated", "subscription.trial_started", "payment.confirmed", "registration.completed", "checkout.initiated", "resume.builder.completed", "identity.verified", "resume.imported", "offer.accepted", "onboarding.step_completed"),
    "tracking.meta": ("subscription.activated", "subscription.trial_started", "payment.confirmed", "registration.completed", "checkout.initiated", "resume.builder.completed", "identity.verified", "resume.imported", "offer.accepted", "onboarding.step_completed"),
    "tracking.ga4": ("subscription.activated", "subscription.trial_started", "payment.confirmed", "registration.completed", "checkout.initiated", "resume.builder.completed", "identity.verified", "resume.imported", "offer.accepted", "onboarding.step_completed"),
    "tracking.tiktok": ("subscription.activated", "subscription.trial_started", "payment.confirmed", "registration.completed", "checkout.initiated", "resume.builder.completed", "identity.verified", "resume.imported", "offer.accepted", "onboarding.step_completed"),
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
