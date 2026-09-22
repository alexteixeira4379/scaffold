"""Opt-in native tool protocol. Existing completion/onboarding contracts stay unchanged."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolFunction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    arguments: str


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    parameters: dict[str, Any]

    def wire(self) -> dict[str, Any]:
        # Some providers validate $defs but omit them from the model's tool prompt.
        # Inline local references so nested argument contracts are actually visible.
        def expand(value, trail=()):
            if isinstance(value, list):
                return [expand(item, trail) for item in value]
            if not isinstance(value, dict):
                return value
            if "$ref" in value:
                ref = value["$ref"]
                if not ref.startswith("#/") or ref in trail:
                    raise ValueError("Tool schemas require nonrecursive local references")
                target = self.parameters
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
                return expand(
                    {**target, **{k: v for k, v in value.items() if k != "$ref"}}, (*trail, ref)
                )
            return {k: expand(v, trail) for k, v in value.items() if k != "$defs"}

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": expand(self.parameters),
            },
        }


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: AgentMessage
    model: str
    finish_reason: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    # Reasoning accounting only when the provider reports it: None is "not reported",
    # never zero. Raw reasoning text is never retained, only its length.
    reasoning_tokens: int | None = Field(default=None, ge=0)
    reasoning_chars: int | None = Field(default=None, ge=0)
    # Set by callers that replay a stored result instead of calling the provider.
    cached: bool = False
