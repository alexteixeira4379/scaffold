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

    def agent_profile(self, *, model=None, tool_transport=None, reasoning_effort=None, tool_choice="auto"):
        """Resolve the actual agent configuration without changing the shared client."""
        profile = getattr(self._backend, "agent_profile", None)
        if profile is None:
            return {"provider": type(self._backend).__name__, "model": model,
                    "tool_transport": tool_transport, "reasoning_effort": reasoning_effort}
        return profile(model=model, tool_transport=tool_transport,
                       reasoning_effort=reasoning_effort, tool_choice=tool_choice)

    async def agent(self, messages, tools, *, max_tokens=6000, temperature=0.1, tool_choice="auto",
                    model=None, tool_transport=None, reasoning_effort=None):
        """Only the post-activation agent opts into native tools."""
        from scaffold.ai.contracts import AIProviderError

        complete = getattr(self._backend, "complete_agent", None)
        if complete is None:
            raise AIProviderError("native tools are not supported by the configured backend")
        return await complete(
            InferenceTier.COMPLEX,
            messages,
            tools,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            **{key: value for key, value in {"model": model, "tool_transport": tool_transport,
                                            "reasoning_effort": reasoning_effort}.items() if value is not None},
        )

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
