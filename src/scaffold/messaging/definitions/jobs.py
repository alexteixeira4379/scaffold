from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)

jobs_topology = MessagingTopology(
    exchanges=[
        ExchangeDefinition(name="jobs.dlx", type="direct", durable=True),
    ],
    queues=[
        QueueDefinition(
            name="jobs.new",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "jobs.dlx",
                "x-dead-letter-routing-key": "jobs.new.dlq",
            },
        ),
        QueueDefinition(name="jobs.new.dlq", durable=True),
    ],
    bindings=[
        BindingDefinition(
            source="jobs.dlx",
            destination="jobs.new.dlq",
            routing_key="jobs.new.dlq",
        ),
    ],
)
