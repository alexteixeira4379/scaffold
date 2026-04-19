from collections.abc import Sequence
from typing import Protocol

from scaffold.ai.contracts import ChatMessage, CompletionResult, InferenceTier, ResponseMode


class LLMPort(Protocol):
    async def complete(
        self,
        tier: InferenceTier,
        output: ResponseMode,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult: ...
