"""Versioned durable tasks. Received text is untrusted data, never instructions."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class InboundData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webhook_event_id: int = Field(gt=0)
    provider_email_id: str | None = None


class ForwardData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delivery_id: int = Field(gt=0)


class EmailInboundRequested(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=64)
    event_name: Literal["email.inbound.requested"] = "email.inbound.requested"
    schema_version: Literal["1.0"] = "1.0"
    candidate_id: int | None = None
    data: InboundData


class EmailForwardRequested(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=64)
    event_name: Literal["email.forward.requested"] = "email.forward.requested"
    schema_version: Literal["1.0"] = "1.0"
    candidate_id: int = Field(gt=0)
    data: ForwardData
