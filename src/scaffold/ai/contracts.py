from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class InferenceTier(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    COMPLEX = "complex"
    THINKING = "thinking"


class ResponseMode(StrEnum):
    TEXT = "text"
    JSON = "json"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class CompletionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: ResponseMode
    text: str
    data: dict[str, Any] | None = None

    def as_text(self) -> str:
        if self.output != ResponseMode.TEXT:
            raise ValueError("completion is not text mode")
        return self.text

    def as_json(self) -> dict[str, Any]:
        if self.output != ResponseMode.JSON:
            raise ValueError("completion is not json mode")
        if self.data is None:
            raise ValueError("json payload missing")
        return self.data


class AIProviderError(RuntimeError):
    pass
