from scaffold.messaging.events import (
    JOB_EVENT_IDEMPOTENCY_KEYS,
    JobEventName,
    dlq_name_for,
    dlx_name_for,
    queue_name_for,
)

_EXPECTED_EVENT_VALUES = {
    "job.captured",
    "job.ingestion.linkedin.request",
    "job.ingestion.common.request",
    "job.ingested",
    "job.created",
    "job.enriched",
    "job.classified",
    "job.eligible",
    "job.matched",
}


def test_job_event_name_has_nine_members() -> None:
    assert len(JobEventName) == 9
    assert {event.value for event in JobEventName} == _EXPECTED_EVENT_VALUES


def test_queue_name_for_matches_event_value() -> None:
    for event in JobEventName:
        assert queue_name_for(event) == event.value


def test_dlq_name_for_appends_suffix() -> None:
    for event in JobEventName:
        assert dlq_name_for(event) == f"{event.value}.dlq"


def test_dlx_name_for_appends_suffix() -> None:
    for event in JobEventName:
        assert dlx_name_for(event) == f"{event.value}.dlx"


def test_job_created_queue_name_preserved() -> None:
    assert queue_name_for(JobEventName.JOB_CREATED) == "job.created"
    assert dlq_name_for(JobEventName.JOB_CREATED) == "job.created.dlq"
    assert dlx_name_for(JobEventName.JOB_CREATED) == "job.created.dlx"


def test_idempotency_keys_defined_for_all_events() -> None:
    assert set(JOB_EVENT_IDEMPOTENCY_KEYS) == set(JobEventName)
    for keys in JOB_EVENT_IDEMPOTENCY_KEYS.values():
        assert isinstance(keys, tuple)
        assert len(keys) > 0
