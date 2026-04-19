from pydantic import BaseModel, ConfigDict, Field


class OutboundMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue: str
    body: dict[str, object]
    correlation_id: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class QueueSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_name: str
    durable: bool = True
    prefetch_count: int = 10
