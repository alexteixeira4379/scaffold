from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)

linkedin_topology = MessagingTopology(
    exchanges=[
        ExchangeDefinition(name="linkedin.login.jobs.dlx", type="direct", durable=True),
        ExchangeDefinition(name="messages.whatsapp.dlx", type="direct", durable=True),
    ],
    queues=[
        QueueDefinition(
            name="linkedin.login.jobs",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "linkedin.login.jobs.dlx",
                "x-dead-letter-routing-key": "linkedin.login.jobs.dlq",
            },
        ),
        QueueDefinition(name="linkedin.login.jobs.dlq", durable=True),
        QueueDefinition(
            name="messages.whatsapp",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "messages.whatsapp.dlx",
                "x-dead-letter-routing-key": "messages.whatsapp.dlq",
            },
        ),
        QueueDefinition(name="messages.whatsapp.dlq", durable=True),
    ],
    bindings=[
        BindingDefinition(
            source="linkedin.login.jobs.dlx",
            destination="linkedin.login.jobs.dlq",
            routing_key="linkedin.login.jobs.dlq",
        ),
        BindingDefinition(
            source="messages.whatsapp.dlx",
            destination="messages.whatsapp.dlq",
            routing_key="messages.whatsapp.dlq",
        ),
    ],
)
