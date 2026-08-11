from functools import reduce

from scaffold.messaging.events import JobEventName, dlq_name_for, dlx_name_for, queue_name_for
from scaffold.messaging.topology import (
    BindingDefinition,
    ExchangeDefinition,
    MessagingTopology,
    QueueDefinition,
)


def _dead_lettered_lane(event: JobEventName) -> MessagingTopology:
    queue, dlq, dlx = queue_name_for(event), dlq_name_for(event), dlx_name_for(event)
    return MessagingTopology(
        exchanges=[ExchangeDefinition(name=dlx, type="direct", durable=True)],
        queues=[
            QueueDefinition(
                name=queue,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": dlx,
                    "x-dead-letter-routing-key": dlq,
                },
            ),
            QueueDefinition(name=dlq, durable=True),
        ],
        bindings=[BindingDefinition(source=dlx, destination=dlq, routing_key=dlq)],
    )


jobs_topology = reduce(
    lambda topology, event: topology.merge(_dead_lettered_lane(event)),
    JobEventName,
    MessagingTopology(),
)
