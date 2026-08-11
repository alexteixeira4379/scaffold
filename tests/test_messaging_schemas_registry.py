import copy

import pytest

from scaffold.messaging.events import JobEventName
from scaffold.messaging.schemas import JobCreatedPayload
from scaffold.messaging.schemas.registry import (
    JOB_EVENT_PAYLOADS,
    deserialize_job_event,
    serialize_job_event,
)

CREATED_EXAMPLE = {
    "event_id": "11111111-1111-1111-1111-111111111111",
    "event_name": "job.created",
    "schema_version": "1.0",
    "occurred_at": "2026-08-10T12:00:00Z",
    "correlation_id": "22222222-2222-2222-2222-222222222222",
    "job": {
        "id": 123,
        "title": "Software Engineer",
        "canonical_url": "https://example.com/job/1",
        "company_id": 10,
        "ats_provider_id": None,
        "source_code": "linkedin",
        "created_at": "2026-08-10T12:00:00Z",
    },
}


def test_registry_maps_all_nine_events() -> None:
    assert set(JOB_EVENT_PAYLOADS) == set(JobEventName)


def test_serialize_job_event_returns_json_safe_dict() -> None:
    payload = JobCreatedPayload.model_validate(CREATED_EXAMPLE)
    body = serialize_job_event(payload)

    assert isinstance(body["event_id"], str)
    assert isinstance(body["correlation_id"], str)
    assert isinstance(body["occurred_at"], str)


def test_deserialize_job_event_dispatches_correct_model() -> None:
    result = deserialize_job_event("job.created", CREATED_EXAMPLE)
    assert isinstance(result, JobCreatedPayload)


def test_serialize_then_deserialize_round_trips() -> None:
    payload = JobCreatedPayload.model_validate(CREATED_EXAMPLE)
    body = serialize_job_event(payload)
    restored = deserialize_job_event("job.created", body)
    assert restored.model_dump() == payload.model_dump()


def test_deserialize_job_event_raises_on_unknown_event_name() -> None:
    with pytest.raises(ValueError):
        deserialize_job_event("job.bogus", {})


def test_deserialize_job_event_raises_on_invalid_shape() -> None:
    with pytest.raises(Exception):
        deserialize_job_event("job.captured", {})


def test_deserialize_job_event_raises_on_incomplete_created_payload() -> None:
    broken = copy.deepcopy(CREATED_EXAMPLE)
    del broken["job"]["id"]
    with pytest.raises(Exception):
        deserialize_job_event("job.created", broken)
