from scaffold.messaging.definitions.billing import billing_topology
from scaffold.messaging.definitions.jobs import jobs_topology
from scaffold.messaging.definitions.linkedin import linkedin_topology
from scaffold.messaging.topology import MessagingTopology, QueueDefinition
from scaffold.messaging.definitions.domain import domain_topology


def get_full_topology() -> MessagingTopology:
    # The legacy candidate PUT still publishes this event. Provision it centrally
    # so mandatory publisher confirmations do not reject profile updates.
    base = MessagingTopology(queues=[QueueDefinition(name="candidate.updated")])
    return (
        base.merge(jobs_topology)
        .merge(linkedin_topology)
        .merge(billing_topology)
        .merge(domain_topology())
    )


__all__ = ["get_full_topology", "jobs_topology", "linkedin_topology", "billing_topology"]
