import json
from collections.abc import Sequence

from scaffold.ai.contracts import (
    ChatMessage,
    CompletionResult,
    InferenceTier,
    ResponseMode,
)
from scaffold.ai.formatters import parse_json_content


class InMemoryLLM:
    async def complete(
        self,
        tier: InferenceTier,
        output: ResponseMode,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        del temperature, max_tokens
        last_user = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user = m.content
                break
        if output == ResponseMode.TEXT:
            text = f"[memory:{tier.value}] {last_user}".strip()
            return CompletionResult(output=output, text=text, data=None)
        payload = {"ok": True, "tier": tier.value, "echo": last_user}
        text = json.dumps(payload)
        data = parse_json_content(text)
        return CompletionResult(output=output, text=text, data=data)
