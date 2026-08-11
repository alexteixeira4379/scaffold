from typing import Literal

from scaffold.messaging.events import JobEventName
from scaffold.messaging.schemas.common import (
    CandidateRef,
    ClassificationInfo,
    EligibilityInfo,
    EnrichmentInfo,
    JobCreatedBody,
    JobRef,
    JobRefWithUrl,
    MatchInfo,
)
from scaffold.messaging.schemas.envelope import JobEventEnvelope


class JobCreatedPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_CREATED]
    job: JobCreatedBody


class JobEnrichedPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_ENRICHED]
    job: JobRefWithUrl
    enrichment: EnrichmentInfo


class JobClassifiedPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_CLASSIFIED]
    job: JobRefWithUrl
    classification: ClassificationInfo


class JobEligiblePayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_ELIGIBLE]
    job: JobRef
    candidate: CandidateRef
    eligibility: EligibilityInfo


class JobMatchedPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_MATCHED]
    job: JobRef
    candidate: CandidateRef
    match: MatchInfo
