from enum import StrEnum


class JobEventName(StrEnum):
    JOB_CAPTURED = "job.captured"
    JOB_INGESTION_LINKEDIN_REQUEST = "job.ingestion.linkedin.request"
    JOB_INGESTION_COMMON_REQUEST = "job.ingestion.common.request"
    JOB_INGESTED = "job.ingested"
    JOB_CREATED = "job.created"
    JOB_ENRICHED = "job.enriched"
    JOB_CLASSIFIED = "job.classified"
    JOB_ELIGIBLE = "job.eligible"
    JOB_MATCHED = "job.matched"


def queue_name_for(event: JobEventName) -> str:
    return event.value


def dlq_name_for(event: JobEventName) -> str:
    return f"{event.value}.dlq"


def dlx_name_for(event: JobEventName) -> str:
    return f"{event.value}.dlx"


# Recommended idempotency key(s) per event, as ordered fallback chains
# (first candidate wins). Documentation/exposure only, not enforced at runtime.
# Source: jobito-architecture/Specs/scaffold-job-events-contracts-spec.md
JOB_EVENT_IDEMPOTENCY_KEYS: dict[JobEventName, tuple[str, ...]] = {
    JobEventName.JOB_CAPTURED: (
        "metadata.ats_provider_id+job.external_job_id",
        "job.canonical_url",
        "job.source_code+job.title+job.company_name_snapshot",
    ),
    JobEventName.JOB_INGESTION_LINKEDIN_REQUEST: ("correlation_id+job.canonical_url",),
    JobEventName.JOB_INGESTION_COMMON_REQUEST: ("correlation_id+job.canonical_url",),
    JobEventName.JOB_INGESTED: ("job.url_hash",),
    JobEventName.JOB_CREATED: ("job.id",),
    JobEventName.JOB_ENRICHED: ("job.id+enrichment.version",),
    JobEventName.JOB_CLASSIFIED: ("job.id+classification.version",),
    JobEventName.JOB_ELIGIBLE: ("eligibility.id",),
    JobEventName.JOB_MATCHED: ("match.id",),
}
