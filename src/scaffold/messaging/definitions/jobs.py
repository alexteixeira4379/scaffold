from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)

jobs_topology = MessagingTopology(
    exchanges=[
        ExchangeDefinition(name="job.ingestion.dlx", type="direct", durable=True),
        ExchangeDefinition(name="job.new.dlx", type="direct", durable=True),
        ExchangeDefinition(name="job.created.dlx", type="direct", durable=True),
    ],
    queues=[
        QueueDefinition(
            name="job.ingestion",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "job.ingestion.dlx",
                "x-dead-letter-routing-key": "job.ingestion.dlq",
            },
        ),
        QueueDefinition(name="job.ingestion.dlq", durable=True),
        QueueDefinition(
            name="job.new",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "job.new.dlx",
                "x-dead-letter-routing-key": "job.new.dlq",
            },
        ),
        QueueDefinition(name="job.new.dlq", durable=True),
        QueueDefinition(
            name="job.created",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "job.created.dlx",
                "x-dead-letter-routing-key": "job.created.dlq",
            },
        ),
        QueueDefinition(name="job.created.dlq", durable=True),
    ],
    bindings=[
        BindingDefinition(
            source="job.ingestion.dlx",
            destination="job.ingestion.dlq",
            routing_key="job.ingestion.dlq",
        ),
        BindingDefinition(
            source="job.new.dlx",
            destination="job.new.dlq",
            routing_key="job.new.dlq",
        ),
        BindingDefinition(
            source="job.created.dlx",
            destination="job.created.dlq",
            routing_key="job.created.dlq",
        ),
    ],
)
