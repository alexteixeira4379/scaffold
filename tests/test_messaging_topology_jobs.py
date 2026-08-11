from scaffold.messaging.definitions import get_full_topology
from scaffold.messaging.definitions.jobs import jobs_topology
from scaffold.messaging.events import JobEventName, dlq_name_for, dlx_name_for, queue_name_for

_LEGACY_NAMES = {
    "job.ingestion",
    "job.ingestion.dlq",
    "job.ingestion.dlx",
    "job.new",
    "job.new.dlq",
    "job.new.dlx",
}


def _queue_names(topology) -> set[str]:
    return {queue.name for queue in topology.queues}


def _exchange_names(topology) -> set[str]:
    return {exchange.name for exchange in topology.exchanges}


def test_all_nine_job_events_have_queue_and_dlq() -> None:
    queue_names = _queue_names(jobs_topology)
    for event in JobEventName:
        assert queue_name_for(event) in queue_names
        assert dlq_name_for(event) in queue_names


def test_every_job_queue_has_dead_letter_arguments() -> None:
    queues_by_name = {queue.name: queue for queue in jobs_topology.queues}
    for event in JobEventName:
        queue = queues_by_name[queue_name_for(event)]
        assert queue.arguments["x-dead-letter-exchange"] == dlx_name_for(event)
        assert queue.arguments["x-dead-letter-routing-key"] == dlq_name_for(event)


def test_every_job_event_has_dlx_exchange() -> None:
    exchanges_by_name = {exchange.name: exchange for exchange in jobs_topology.exchanges}
    for event in JobEventName:
        exchange = exchanges_by_name[dlx_name_for(event)]
        assert exchange.type == "direct"
        assert exchange.durable is True


def test_every_dlx_binds_to_its_dlq() -> None:
    bindings = {
        (binding.source, binding.destination, binding.routing_key)
        for binding in jobs_topology.bindings
    }
    for event in JobEventName:
        dlx, dlq = dlx_name_for(event), dlq_name_for(event)
        assert (dlx, dlq, dlq) in bindings


def test_job_created_lane_names_unchanged() -> None:
    queue_names = _queue_names(jobs_topology)
    exchange_names = _exchange_names(jobs_topology)
    assert "job.created" in queue_names
    assert "job.created.dlq" in queue_names
    assert "job.created.dlx" in exchange_names


def test_legacy_job_ingestion_and_job_new_absent() -> None:
    queue_names = _queue_names(jobs_topology)
    exchange_names = _exchange_names(jobs_topology)
    binding_names = {
        name
        for binding in jobs_topology.bindings
        for name in (binding.source, binding.destination, binding.routing_key)
    }
    assert not (_LEGACY_NAMES & queue_names)
    assert not (_LEGACY_NAMES & exchange_names)
    assert not (_LEGACY_NAMES & binding_names)


def test_get_full_topology_includes_all_job_events_and_excludes_legacy() -> None:
    topology = get_full_topology()
    queue_names = _queue_names(topology)
    for event in JobEventName:
        assert queue_name_for(event) in queue_names
        assert dlq_name_for(event) in queue_names
    assert not (_LEGACY_NAMES & queue_names)
    assert not (_LEGACY_NAMES & _exchange_names(topology))


def test_jobs_topology_has_exactly_nine_main_queues() -> None:
    main_queues = [
        queue.name for queue in jobs_topology.queues if not queue.name.endswith(".dlq")
    ]
    assert len(main_queues) == 9
