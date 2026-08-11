from scaffold.messaging.events import JobEventName
from scaffold.messaging.schemas.envelope import JobEventEnvelope
from scaffold.messaging.schemas.pos_registro import (
    JobClassifiedPayload,
    JobCreatedPayload,
    JobEligiblePayload,
    JobEnrichedPayload,
    JobMatchedPayload,
)
from scaffold.messaging.schemas.pre_registro import (
    CapturedJobPayload,
    CommonIngestionRequestPayload,
    IngestedJobPayload,
    LinkedinIngestionRequestPayload,
)

JOB_EVENT_PAYLOADS: dict[JobEventName, type[JobEventEnvelope]] = {
    JobEventName.JOB_CAPTURED: CapturedJobPayload,
    JobEventName.JOB_INGESTION_LINKEDIN_REQUEST: LinkedinIngestionRequestPayload,
    JobEventName.JOB_INGESTION_COMMON_REQUEST: CommonIngestionRequestPayload,
    JobEventName.JOB_INGESTED: IngestedJobPayload,
    JobEventName.JOB_CREATED: JobCreatedPayload,
    JobEventName.JOB_ENRICHED: JobEnrichedPayload,
    JobEventName.JOB_CLASSIFIED: JobClassifiedPayload,
    JobEventName.JOB_ELIGIBLE: JobEligiblePayload,
    JobEventName.JOB_MATCHED: JobMatchedPayload,
}


def serialize_job_event(payload: JobEventEnvelope) -> dict[str, object]:
    return payload.model_dump(mode="json")


def deserialize_job_event(event_name: str, body: dict[str, object]) -> JobEventEnvelope:
    try:
        event = JobEventName(event_name)
    except ValueError as exc:
        raise ValueError(f"unknown job event name: {event_name!r}") from exc
    return JOB_EVENT_PAYLOADS[event].model_validate(body)
