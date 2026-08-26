from scaffold.messaging.definitions.billing import billing_topology
from scaffold.messaging.definitions.jobs import jobs_topology
from scaffold.messaging.definitions.linkedin import linkedin_topology
from scaffold.messaging.topology import MessagingTopology


def get_full_topology() -> MessagingTopology:
    base = MessagingTopology()
    return base.merge(jobs_topology).merge(linkedin_topology).merge(billing_topology)


__all__ = ["get_full_topology", "jobs_topology", "linkedin_topology", "billing_topology"]
