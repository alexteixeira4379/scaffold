from typing import Literal

from scaffold.messaging.events import JobEventName
from scaffold.messaging.schemas.common import (
    CapturedJobBody,
    CapturedMetadata,
    CommonIngestionRequestMetadata,
    IngestedJobBody,
    IngestedMetadata,
    LinkedinIngestionRequestMetadata,
    RoutedJobBody,
)
from scaffold.messaging.schemas.envelope import JobEventEnvelope


class CapturedJobPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_CAPTURED]
    metadata: CapturedMetadata
    job: CapturedJobBody


class LinkedinIngestionRequestPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_INGESTION_LINKEDIN_REQUEST]
    metadata: LinkedinIngestionRequestMetadata
    job: RoutedJobBody


class CommonIngestionRequestPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_INGESTION_COMMON_REQUEST]
    metadata: CommonIngestionRequestMetadata
    job: RoutedJobBody


class IngestedJobPayload(JobEventEnvelope):
    event_name: Literal[JobEventName.JOB_INGESTED]
    metadata: IngestedMetadata
    job: IngestedJobBody
