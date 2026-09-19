from scaffold.messaging.definitions import get_full_topology


def test_execution_and_resume_notification_queues_are_provisioned():
    topology = get_full_topology()
    queues = {queue.name: queue for queue in topology.queues}
    assert len(queues) == len(topology.queues)
    for name in (
        "application.linkedin.submit", "application.ats.submit",
        "notification.application.submitted", "notification.application.failed",
        "resume.available",
    ):
        assert queues[name].durable
        assert queues[name].arguments["x-dead-letter-routing-key"] == f"{name}.dlq"
        assert f"{name}.dlq" in queues
    assert queues["tracking.event"].arguments == {}
    assert queues["tracking.event.dlq"].durable
