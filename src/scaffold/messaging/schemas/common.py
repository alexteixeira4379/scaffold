from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scaffold.constants import EmploymentType, ExperienceLevel, RemoteType

_SHA256_HEX = r"^[0-9a-f]{64}$"
_SHA256_PREFIXED = r"^sha256:[0-9a-f]{64}$"


def _is_supported_hash(value: str) -> bool:
    import re

    return bool(re.fullmatch(_SHA256_HEX, value) or re.fullmatch(_SHA256_PREFIXED, value))


# --- Pre-registro job body -------------------------------------------------


class JobBodyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_code: str
    title: str
    canonical_url: str | None = None
    external_job_id: str | None = None
    company_name_snapshot: str | None = None
    company_domain_snapshot: str | None = None
    description: str | None = None
    location: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    remote_type: RemoteType | None = None
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    raw_payload: dict[str, object]


class CapturedJobBody(JobBodyBase):
    pass


class RoutedJobBody(JobBodyBase):
    canonical_url: str


class IngestedJobBody(RoutedJobBody):
    url_hash: str

    @field_validator("url_hash")
    @classmethod
    def validate_url_hash(cls, value: str) -> str:
        if not _is_supported_hash(value):
            raise ValueError("url_hash must be 64 lowercase hex chars or sha256:<64 lowercase hex chars>")
        return value


# --- Pre-registro metadata --------------------------------------------------


class MetadataBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_definition_id: int | None = None
    collection_run_id: int | None = None
    collected_at: datetime | None = None
    source_code: str
    ats_discovery_source_id: int | None = None
    ats_provider_id: int | None = None


class CapturedMetadata(MetadataBase):
    @model_validator(mode="after")
    def validate_source_identity(self) -> "CapturedMetadata":
        has_collection_identity = self.collection_definition_id is not None and self.collection_run_id is not None
        has_ats_identity = self.ats_discovery_source_id is not None
        if not (has_collection_identity or has_ats_identity):
            raise ValueError(
                "metadata must include collection_definition_id+collection_run_id or ats_discovery_source_id"
            )
        return self


class RoutingInfoBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routed_at: datetime
    reason: str


class LinkedinRoutingInfo(RoutingInfoBase):
    route: Literal["linkedin"] = "linkedin"


class CommonRoutingInfo(RoutingInfoBase):
    route: Literal["common"] = "common"


class LinkedinIngestionRequestMetadata(MetadataBase):
    routing: LinkedinRoutingInfo


class CommonIngestionRequestMetadata(MetadataBase):
    routing: CommonRoutingInfo


class IngestionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed"]
    ingested_at: datetime
    worker: Literal["linkedin-ingestion-worker", "common-ingestion-worker"]
    original_url: str | None = None
    final_url: str | None = None
    url_hash: str
    content_hash: str | None = None
    errors: list[object] = Field(default_factory=list)

    @field_validator("url_hash")
    @classmethod
    def validate_url_hash(cls, value: str) -> str:
        if not _is_supported_hash(value):
            raise ValueError("url_hash must be 64 lowercase hex chars or sha256:<64 lowercase hex chars>")
        return value

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, value: str | None) -> str | None:
        if value is not None and not _is_supported_hash(value):
            raise ValueError("content_hash must be 64 lowercase hex chars or sha256:<64 lowercase hex chars>")
        return value


class IngestedMetadata(MetadataBase):
    routing: dict[str, object] | None = None
    ingestion: IngestionInfo


# --- Pos-registro shared refs ----------------------------------------------


class JobRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str


class JobRefWithUrl(JobRef):
    canonical_url: str | None = None


class CandidateRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    target_profile_id: int


class EnrichmentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    provider: str
    model: str
    completed_at: datetime
    artifact_ids: list[int] = Field(default_factory=list)


class ClassificationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    classified_at: datetime
    taxonomy_ids: list[int] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class EligibilityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    routing_score: float = Field(ge=0, le=100)
    status: Literal["eligible"] = "eligible"
    created_at: datetime


class MatchInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    eligibility_id: int
    score: float = Field(ge=0, le=100)
    status: Literal["scored"] = "scored"
    matched_at: datetime


class JobCreatedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    canonical_url: str | None = None
    company_id: int | None = None
    ats_provider_id: int | None = None
    source_code: str
    created_at: datetime
