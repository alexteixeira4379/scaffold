from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)

jcrawler_topology = MessagingTopology(
    exchanges=[
        ExchangeDefinition(name="jcrawler.jobs.dlx", type="direct", durable=True),
    ],
    queues=[
        QueueDefinition(
            name="jcrawler.jobs.new",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "jcrawler.jobs.dlx",
                "x-dead-letter-routing-key": "jcrawler.jobs.new.dlq",
            },
        ),
        QueueDefinition(name="jcrawler.jobs.new.dlq", durable=True),
    ],
    bindings=[
        BindingDefinition(
            source="jcrawler.jobs.dlx",
            destination="jcrawler.jobs.new.dlq",
            routing_key="jcrawler.jobs.new.dlq",
        ),
    ],
)
