from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_name: str
    schema_version: Literal["1.0"]
    occurred_at: datetime
    correlation_id: UUID
