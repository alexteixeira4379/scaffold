import copy

import pytest
from pydantic import ValidationError

from scaffold.constants import EmploymentType, ExperienceLevel, RemoteType
from scaffold.messaging.schemas import (
    CapturedJobPayload,
    CommonIngestionRequestPayload,
    IngestedJobPayload,
    LinkedinIngestionRequestPayload,
)

_ENVELOPE_FIELDS = ["event_id", "event_name", "schema_version", "occurred_at", "correlation_id"]

_BASE_JOB = {
    "source_code": "linkedin",
    "title": "Software Engineer",
    "canonical_url": "https://example.com/job/1",
    "external_job_id": "abc123",
    "company_name_snapshot": "Acme",
    "company_domain_snapshot": "acme.com",
    "description": "A great job",
    "location": "Remote",
    "country": "US",
    "state": "CA",
    "city": "SF",
    "remote_type": "remote",
    "employment_type": "full_time",
    "experience_level": "senior",
    "salary_min": 100000,
    "salary_max": 150000,
    "currency": "USD",
    "posted_at": "2026-08-01T00:00:00Z",
    "raw_payload": {"foo": "bar"},
}

CAPTURED_EXAMPLE = {
    "event_id": "11111111-1111-1111-1111-111111111111",
    "event_name": "job.captured",
    "schema_version": "1.0",
    "occurred_at": "2026-08-10T12:00:00Z",
    "correlation_id": "22222222-2222-2222-2222-222222222222",
    "metadata": {
        "collection_definition_id": 1,
        "collection_run_id": 2,
        "collected_at": "2026-08-10T11:00:00Z",
        "source_code": "linkedin",
        "ats_discovery_source_id": None,
        "ats_provider_id": None,
    },
    "job": _BASE_JOB,
}

LINKEDIN_REQUEST_EXAMPLE = {
    "event_id": "11111111-1111-1111-1111-111111111111",
    "event_name": "job.ingestion.linkedin.request",
    "schema_version": "1.0",
    "occurred_at": "2026-08-10T12:00:00Z",
    "correlation_id": "22222222-2222-2222-2222-222222222222",
    "metadata": {
        "collection_definition_id": 1,
        "collection_run_id": 2,
        "collected_at": "2026-08-10T11:00:00Z",
        "source_code": "linkedin",
        "ats_discovery_source_id": None,
        "ats_provider_id": None,
        "routing": {
            "routed_at": "2026-08-10T11:30:00Z",
            "route": "linkedin",
            "reason": "linkedin source",
        },
    },
    "job": _BASE_JOB,
}

COMMON_REQUEST_EXAMPLE = {
    **LINKEDIN_REQUEST_EXAMPLE,
    "event_name": "job.ingestion.common.request",
    "metadata": {
        **LINKEDIN_REQUEST_EXAMPLE["metadata"],
        "routing": {
            "routed_at": "2026-08-10T11:30:00Z",
            "route": "common",
            "reason": "non-linkedin source",
        },
    },
}

INGESTED_EXAMPLE = {
    "event_id": "11111111-1111-1111-1111-111111111111",
    "event_name": "job.ingested",
    "schema_version": "1.0",
    "occurred_at": "2026-08-10T12:00:00Z",
    "correlation_id": "22222222-2222-2222-2222-222222222222",
    "metadata": {
        "collection_definition_id": 1,
        "collection_run_id": 2,
        "collected_at": "2026-08-10T11:00:00Z",
        "source_code": "linkedin",
        "ats_discovery_source_id": None,
        "ats_provider_id": None,
        "routing": None,
        "ingestion": {
            "status": "completed",
            "ingested_at": "2026-08-10T11:45:00Z",
            "worker": "linkedin-ingestion-worker",
            "original_url": "https://example.com/job/1",
            "final_url": "https://example.com/job/1",
            "url_hash": "a" * 64,
            "content_hash": None,
            "errors": [],
        },
    },
    "job": {**_BASE_JOB, "url_hash": "a" * 64},
}


@pytest.mark.parametrize(
    ("model_cls", "example"),
    [
        (CapturedJobPayload, CAPTURED_EXAMPLE),
        (LinkedinIngestionRequestPayload, LINKEDIN_REQUEST_EXAMPLE),
        (CommonIngestionRequestPayload, COMMON_REQUEST_EXAMPLE),
        (IngestedJobPayload, INGESTED_EXAMPLE),
    ],
)
def test_accepts_valid_payload(model_cls, example) -> None:
    payload = model_cls.model_validate(example)
    assert str(payload.event_name) == example["event_name"]


@pytest.mark.parametrize(
    ("model_cls", "example"),
    [
        (CapturedJobPayload, CAPTURED_EXAMPLE),
        (LinkedinIngestionRequestPayload, LINKEDIN_REQUEST_EXAMPLE),
        (CommonIngestionRequestPayload, COMMON_REQUEST_EXAMPLE),
        (IngestedJobPayload, INGESTED_EXAMPLE),
    ],
)
@pytest.mark.parametrize("field", _ENVELOPE_FIELDS)
def test_rejects_missing_envelope_field(model_cls, example, field) -> None:
    broken = copy.deepcopy(example)
    del broken[field]
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


@pytest.mark.parametrize(
    ("model_cls", "example", "other_event_name"),
    [
        (CapturedJobPayload, CAPTURED_EXAMPLE, "job.created"),
        (LinkedinIngestionRequestPayload, LINKEDIN_REQUEST_EXAMPLE, "job.captured"),
        (CommonIngestionRequestPayload, COMMON_REQUEST_EXAMPLE, "job.captured"),
        (IngestedJobPayload, INGESTED_EXAMPLE, "job.captured"),
    ],
)
def test_event_name_is_fixed(model_cls, example, other_event_name) -> None:
    broken = {**copy.deepcopy(example), "event_name": other_event_name}
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


@pytest.mark.parametrize(
    ("model_cls", "example"),
    [
        (CapturedJobPayload, CAPTURED_EXAMPLE),
        (LinkedinIngestionRequestPayload, LINKEDIN_REQUEST_EXAMPLE),
        (CommonIngestionRequestPayload, COMMON_REQUEST_EXAMPLE),
        (IngestedJobPayload, INGESTED_EXAMPLE),
    ],
)
def test_schema_version_rejects_unknown_value(model_cls, example) -> None:
    broken = {**copy.deepcopy(example), "schema_version": "2.0"}
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


def test_job_captured_requires_raw_payload() -> None:
    broken = copy.deepcopy(CAPTURED_EXAMPLE)
    del broken["job"]["raw_payload"]
    with pytest.raises(ValidationError):
        CapturedJobPayload.model_validate(broken)


def test_job_captured_allows_null_canonical_url() -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["canonical_url"] = None
    payload = CapturedJobPayload.model_validate(example)
    assert payload.job.canonical_url is None


def test_job_captured_accepts_ats_source_identity_without_collection_fields() -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["metadata"]["collection_definition_id"] = None
    example["metadata"]["collection_run_id"] = None
    example["metadata"]["collected_at"] = None
    example["metadata"]["ats_discovery_source_id"] = 123
    payload = CapturedJobPayload.model_validate(example)
    assert payload.metadata.ats_discovery_source_id == 123


def test_job_captured_requires_collection_or_ats_source_identity() -> None:
    broken = copy.deepcopy(CAPTURED_EXAMPLE)
    broken["metadata"]["collection_definition_id"] = None
    broken["metadata"]["collection_run_id"] = None
    broken["metadata"]["ats_discovery_source_id"] = None
    with pytest.raises(ValidationError):
        CapturedJobPayload.model_validate(broken)


def test_linkedin_request_requires_non_null_canonical_url() -> None:
    broken = copy.deepcopy(LINKEDIN_REQUEST_EXAMPLE)
    broken["job"]["canonical_url"] = None
    with pytest.raises(ValidationError):
        LinkedinIngestionRequestPayload.model_validate(broken)


def test_linkedin_request_routing_route_is_fixed_to_linkedin() -> None:
    broken = copy.deepcopy(LINKEDIN_REQUEST_EXAMPLE)
    broken["metadata"]["routing"]["route"] = "common"
    with pytest.raises(ValidationError):
        LinkedinIngestionRequestPayload.model_validate(broken)


def test_common_request_routing_route_is_fixed_to_common() -> None:
    broken = copy.deepcopy(COMMON_REQUEST_EXAMPLE)
    broken["metadata"]["routing"]["route"] = "linkedin"
    with pytest.raises(ValidationError):
        CommonIngestionRequestPayload.model_validate(broken)


@pytest.mark.parametrize(
    "model_cls,example",
    [
        (LinkedinIngestionRequestPayload, LINKEDIN_REQUEST_EXAMPLE),
        (CommonIngestionRequestPayload, COMMON_REQUEST_EXAMPLE),
    ],
)
def test_ingestion_request_metadata_ints_are_nullable(model_cls, example) -> None:
    loosened = copy.deepcopy(example)
    loosened["metadata"]["collection_definition_id"] = None
    loosened["metadata"]["collection_run_id"] = None
    loosened["metadata"]["collected_at"] = None
    payload = model_cls.model_validate(loosened)
    assert payload.metadata.collection_definition_id is None


def test_job_ingested_requires_url_hash() -> None:
    broken = copy.deepcopy(INGESTED_EXAMPLE)
    del broken["job"]["url_hash"]
    with pytest.raises(ValidationError):
        IngestedJobPayload.model_validate(broken)


@pytest.mark.parametrize("hash_value", ["a" * 64, f"sha256:{'a' * 64}"])
def test_job_ingested_accepts_supported_hash_formats(hash_value) -> None:
    example = copy.deepcopy(INGESTED_EXAMPLE)
    example["metadata"]["ingestion"]["url_hash"] = hash_value
    example["metadata"]["ingestion"]["content_hash"] = hash_value
    example["job"]["url_hash"] = hash_value
    payload = IngestedJobPayload.model_validate(example)
    assert payload.job.url_hash == hash_value


@pytest.mark.parametrize("hash_value", ["not-a-hash", "A" * 64, f"sha256:{'A' * 64}"])
def test_job_ingested_rejects_invalid_hash_formats(hash_value) -> None:
    example = copy.deepcopy(INGESTED_EXAMPLE)
    example["metadata"]["ingestion"]["url_hash"] = hash_value
    example["job"]["url_hash"] = hash_value
    with pytest.raises(ValidationError):
        IngestedJobPayload.model_validate(example)


def test_job_ingested_requires_ingestion_status_completed() -> None:
    broken = copy.deepcopy(INGESTED_EXAMPLE)
    broken["metadata"]["ingestion"]["status"] = "failed"
    with pytest.raises(ValidationError):
        IngestedJobPayload.model_validate(broken)


@pytest.mark.parametrize("member", list(RemoteType))
def test_remote_type_field_accepts_all_members(member) -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["remote_type"] = member.value
    payload = CapturedJobPayload.model_validate(example)
    assert payload.job.remote_type == member


def test_remote_type_field_rejects_invalid_value() -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["remote_type"] = "not-a-real-value"
    with pytest.raises(ValidationError):
        CapturedJobPayload.model_validate(example)


@pytest.mark.parametrize("member", list(EmploymentType))
def test_employment_type_field_accepts_all_members(member) -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["employment_type"] = member.value
    payload = CapturedJobPayload.model_validate(example)
    assert payload.job.employment_type == member


def test_employment_type_field_rejects_invalid_value() -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["employment_type"] = "not-a-real-value"
    with pytest.raises(ValidationError):
        CapturedJobPayload.model_validate(example)


@pytest.mark.parametrize("member", list(ExperienceLevel))
def test_experience_level_field_accepts_all_members(member) -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["experience_level"] = member.value
    payload = CapturedJobPayload.model_validate(example)
    assert payload.job.experience_level == member


def test_experience_level_field_rejects_invalid_value() -> None:
    example = copy.deepcopy(CAPTURED_EXAMPLE)
    example["job"]["experience_level"] = "not-a-real-value"
    with pytest.raises(ValidationError):
        CapturedJobPayload.model_validate(example)
