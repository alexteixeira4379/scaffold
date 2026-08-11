import copy

import pytest
from pydantic import ValidationError

from scaffold.messaging.schemas import (
    JobClassifiedPayload,
    JobCreatedPayload,
    JobEligiblePayload,
    JobEnrichedPayload,
    JobMatchedPayload,
)

_ENVELOPE_FIELDS = ["event_id", "event_name", "schema_version", "occurred_at", "correlation_id"]

_ENVELOPE = {
    "event_id": "11111111-1111-1111-1111-111111111111",
    "schema_version": "1.0",
    "occurred_at": "2026-08-10T12:00:00Z",
    "correlation_id": "22222222-2222-2222-2222-222222222222",
}

CREATED_EXAMPLE = {
    **_ENVELOPE,
    "event_name": "job.created",
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

ENRICHED_EXAMPLE = {
    **_ENVELOPE,
    "event_name": "job.enriched",
    "job": {"id": 123, "title": "Software Engineer", "canonical_url": "https://example.com/job/1"},
    "enrichment": {
        "version": "v1",
        "provider": "openai",
        "model": "gpt-5",
        "completed_at": "2026-08-10T12:30:00Z",
        "artifact_ids": [1, 2],
    },
}

CLASSIFIED_EXAMPLE = {
    **_ENVELOPE,
    "event_name": "job.classified",
    "job": {"id": 123, "title": "Software Engineer", "canonical_url": "https://example.com/job/1"},
    "classification": {
        "version": "v1",
        "classified_at": "2026-08-10T12:45:00Z",
        "taxonomy_ids": [1, 2],
        "confidence": 0.9,
    },
}

ELIGIBLE_EXAMPLE = {
    **_ENVELOPE,
    "event_name": "job.eligible",
    "job": {"id": 123, "title": "Software Engineer"},
    "candidate": {"id": 5, "target_profile_id": 7},
    "eligibility": {
        "id": 99,
        "routing_score": 80,
        "status": "eligible",
        "created_at": "2026-08-10T13:00:00Z",
    },
}

MATCHED_EXAMPLE = {
    **_ENVELOPE,
    "event_name": "job.matched",
    "job": {"id": 123, "title": "Software Engineer"},
    "candidate": {"id": 5, "target_profile_id": 7},
    "match": {
        "id": 501,
        "eligibility_id": 99,
        "score": 88,
        "status": "scored",
        "matched_at": "2026-08-10T13:15:00Z",
    },
}

_ALL = [
    (JobCreatedPayload, CREATED_EXAMPLE),
    (JobEnrichedPayload, ENRICHED_EXAMPLE),
    (JobClassifiedPayload, CLASSIFIED_EXAMPLE),
    (JobEligiblePayload, ELIGIBLE_EXAMPLE),
    (JobMatchedPayload, MATCHED_EXAMPLE),
]


@pytest.mark.parametrize(("model_cls", "example"), _ALL)
def test_accepts_valid_payload(model_cls, example) -> None:
    payload = model_cls.model_validate(example)
    assert str(payload.event_name) == example["event_name"]


@pytest.mark.parametrize(("model_cls", "example"), _ALL)
@pytest.mark.parametrize("field", _ENVELOPE_FIELDS)
def test_rejects_missing_envelope_field(model_cls, example, field) -> None:
    broken = copy.deepcopy(example)
    del broken[field]
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


@pytest.mark.parametrize(("model_cls", "example"), _ALL)
def test_event_name_is_fixed(model_cls, example) -> None:
    other = "job.captured" if example["event_name"] != "job.captured" else "job.created"
    broken = {**copy.deepcopy(example), "event_name": other}
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


@pytest.mark.parametrize(("model_cls", "example"), _ALL)
def test_schema_version_rejects_unknown_value(model_cls, example) -> None:
    broken = {**copy.deepcopy(example), "schema_version": "2.0"}
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


@pytest.mark.parametrize(("model_cls", "example"), _ALL)
def test_rejects_extra_raw_payload_key_at_top_level(model_cls, example) -> None:
    broken = {**copy.deepcopy(example), "raw_payload": {"foo": "bar"}}
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


@pytest.mark.parametrize(("model_cls", "example"), _ALL)
def test_rejects_extra_raw_payload_key_nested_in_job(model_cls, example) -> None:
    broken = copy.deepcopy(example)
    broken["job"]["raw_payload"] = {"foo": "bar"}
    with pytest.raises(ValidationError):
        model_cls.model_validate(broken)


def test_job_created_requires_id_title_source_code_created_at() -> None:
    for field in ("id", "title", "source_code", "created_at"):
        broken = copy.deepcopy(CREATED_EXAMPLE)
        del broken["job"][field]
        with pytest.raises(ValidationError):
            JobCreatedPayload.model_validate(broken)


def test_job_enriched_requires_version_and_completed_at() -> None:
    for field in ("version", "completed_at"):
        broken = copy.deepcopy(ENRICHED_EXAMPLE)
        del broken["enrichment"][field]
        with pytest.raises(ValidationError):
            JobEnrichedPayload.model_validate(broken)


def test_job_classified_requires_version_and_classified_at() -> None:
    for field in ("version", "classified_at"):
        broken = copy.deepcopy(CLASSIFIED_EXAMPLE)
        del broken["classification"][field]
        with pytest.raises(ValidationError):
            JobClassifiedPayload.model_validate(broken)


def test_job_eligible_requires_candidate_and_eligibility_fields() -> None:
    broken = copy.deepcopy(ELIGIBLE_EXAMPLE)
    del broken["candidate"]["target_profile_id"]
    with pytest.raises(ValidationError):
        JobEligiblePayload.model_validate(broken)

    broken = copy.deepcopy(ELIGIBLE_EXAMPLE)
    del broken["eligibility"]["id"]
    with pytest.raises(ValidationError):
        JobEligiblePayload.model_validate(broken)


def test_job_matched_requires_match_and_eligibility_id_and_score() -> None:
    for field in ("id", "eligibility_id", "score"):
        broken = copy.deepcopy(MATCHED_EXAMPLE)
        del broken["match"][field]
        with pytest.raises(ValidationError):
            JobMatchedPayload.model_validate(broken)


@pytest.mark.parametrize("score", [0, 100])
def test_job_eligible_routing_score_bounds_accepted(score) -> None:
    example = copy.deepcopy(ELIGIBLE_EXAMPLE)
    example["eligibility"]["routing_score"] = score
    JobEligiblePayload.model_validate(example)


@pytest.mark.parametrize("score", [-1, 101])
def test_job_eligible_routing_score_bounds_rejected(score) -> None:
    example = copy.deepcopy(ELIGIBLE_EXAMPLE)
    example["eligibility"]["routing_score"] = score
    with pytest.raises(ValidationError):
        JobEligiblePayload.model_validate(example)


@pytest.mark.parametrize("score", [0, 100])
def test_job_matched_score_bounds_accepted(score) -> None:
    example = copy.deepcopy(MATCHED_EXAMPLE)
    example["match"]["score"] = score
    JobMatchedPayload.model_validate(example)


@pytest.mark.parametrize("score", [-1, 101])
def test_job_matched_score_bounds_rejected(score) -> None:
    example = copy.deepcopy(MATCHED_EXAMPLE)
    example["match"]["score"] = score
    with pytest.raises(ValidationError):
        JobMatchedPayload.model_validate(example)
