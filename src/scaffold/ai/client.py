from __future__ import annotations

from collections.abc import Sequence

from scaffold.ai.contracts import ChatMessage, CompletionResult, InferenceTier, ResponseMode
from scaffold.ai.factory import create_llm_backend
from scaffold.ai.ports import LLMPort
from scaffold.config import Settings


class AIClient:
    def __init__(self, backend: LLMPort) -> None:
        self._backend = backend

    @classmethod
    def from_settings(cls, settings: Settings) -> AIClient:
        return cls(create_llm_backend(settings))

    async def basic(
        self,
        prompt: str,
        output: ResponseMode,
        *,
        system: str | None = None,
        messages: Sequence[ChatMessage] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        return await self._run(
            InferenceTier.BASIC,
            output,
            prompt,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def intermediate(
        self,
        prompt: str,
        output: ResponseMode,
        *,
        system: str | None = None,
        messages: Sequence[ChatMessage] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        return await self._run(
            InferenceTier.INTERMEDIATE,
            output,
            prompt,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def complex(
        self,
        prompt: str,
        output: ResponseMode,
        *,
        system: str | None = None,
        messages: Sequence[ChatMessage] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        return await self._run(
            InferenceTier.COMPLEX,
            output,
            prompt,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def thinking(
        self,
        prompt: str,
        output: ResponseMode,
        *,
        system: str | None = None,
        messages: Sequence[ChatMessage] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        return await self._run(
            InferenceTier.THINKING,
            output,
            prompt,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _run(
        self,
        tier: InferenceTier,
        output: ResponseMode,
        prompt: str,
        *,
        system: str | None,
        messages: Sequence[ChatMessage] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> CompletionResult:
        if messages is not None:
            thread = list(messages)
            if prompt.strip():
                thread.append(ChatMessage(role="user", content=prompt))
        else:
            thread = []
            if system is not None:
                thread.append(ChatMessage(role="system", content=system))
            thread.append(ChatMessage(role="user", content=prompt))
        return await self._backend.complete(
            tier,
            output,
            thread,
            temperature=temperature,
            max_tokens=max_tokens,
        )
