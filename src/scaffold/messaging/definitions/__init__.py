from scaffold.messaging.definitions.jobs import jobs_topology
from scaffold.messaging.topology import MessagingTopology


def get_full_topology() -> MessagingTopology:
    base = MessagingTopology()
    return base.merge(jobs_topology)


__all__ = ["get_full_topology", "jobs_topology"]
