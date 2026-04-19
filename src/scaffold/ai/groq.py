import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from scaffold.ai.contracts import (
    AIProviderError,
    ChatMessage,
    CompletionResult,
    InferenceTier,
    ResponseMode,
)
from scaffold.ai.formatters import parse_json_content, prepare_messages


class GroqLLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        models: Mapping[InferenceTier, str],
        timeout_s: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._models = dict(models)
        self._timeout_s = timeout_s

    async def complete(
        self,
        tier: InferenceTier,
        output: ResponseMode,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        model = self._models.get(tier)
        if not model:
            raise AIProviderError(f"no model configured for tier {tier.value}")
        msgs = prepare_messages(output, messages)
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in msgs],
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if output == ResponseMode.JSON:
            body["response_format"] = {"type": "json_object"}
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise AIProviderError(f"groq http {resp.status_code}: {resp.text[:2000]}")
        payload = resp.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AIProviderError(f"unexpected groq payload: {payload!r}") from e
        if not isinstance(content, str):
            raise AIProviderError("groq message content is not a string")
        if output == ResponseMode.TEXT:
            return CompletionResult(output=output, text=content, data=None)
        try:
            data = parse_json_content(content)
        except (json.JSONDecodeError, ValueError) as e:
            raise AIProviderError(f"invalid json from model: {content[:500]}") from e
        return CompletionResult(output=output, text=content.strip(), data=data)
