import asyncio
import copy
import json
import os

import httpx
import pytest

from scaffold.ai import AIClient, InferenceTier
from scaffold.ai.agent import AgentMessage, ToolDefinition
from scaffold.ai.contracts import AIProviderError
from scaffold.ai.groq import GroqLLM


def client():
    return AIClient(GroqLLM(api_key="test", base_url="https://provider.invalid",
                           models={InferenceTier.COMPLEX: "openai/gpt-oss-120b"}))


MESSAGES = [AgentMessage(role="user", content="Check the supplied text")]
TOOLS = [ToolDefinition(name="review_result", description="Review", parameters={"type": "object"})]
CHOICE = {"type": "function", "function": {"name": "review_result"}}


async def test_concurrent_override_matches_default_payload_except_model_and_never_mutates_shared_state(monkeypatch):
    monkeypatch.delenv("GROQ_AGENT_TOOL_TRANSPORT", raising=False)
    monkeypatch.delenv("GROQ_AGENT_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("GROQ_AGENT_STRICT_FORCED", raising=False)
    ai = client()
    environment = dict(os.environ)
    configured = copy.deepcopy(ai._backend._models)
    sent = []

    async def post(self, url, **kwargs):
        body = copy.deepcopy(kwargs["json"])
        sent.append(body)
        await asyncio.sleep(0)
        return httpx.Response(200, json={"model": body["model"], "choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps({"ok": True})}}
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    ordinary, review = await asyncio.gather(
        ai.agent(MESSAGES, TOOLS, tool_choice=CHOICE),
        ai.agent(MESSAGES, TOOLS, tool_choice=CHOICE, model="qwen/qwen3.8-27b",
                 tool_transport="json", reasoning_effort="medium"),
    )
    assert ordinary.model == "openai/gpt-oss-120b"
    assert review.model == "qwen/qwen3.8-27b"
    assert [{k: v for k, v in b.items() if k != "model"} for b in sent][0] == {
        k: v for k, v in sent[1].items() if k != "model"
    }
    assert sent[0]["reasoning_effort"] == "medium"
    assert sent[0]["response_format"] == {"type": "json_object"}
    assert ai._backend._models == configured
    assert dict(os.environ) == environment


async def test_configured_model_error_has_no_default_model_fallback(monkeypatch):
    sent = []

    async def post(self, url, **kwargs):
        sent.append(kwargs["json"]["model"])
        return httpx.Response(400, json={"error": {"code": "model_not_found"}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(AIProviderError, match="model_not_found"):
        await client().agent(MESSAGES, TOOLS, model="qwen/qwen3.8-27b",
                             tool_transport="json", reasoning_effort="medium")
    assert sent == ["qwen/qwen3.8-27b"]


def test_effective_profile_retains_default_env_and_distinguishes_explicit_options(monkeypatch):
    monkeypatch.setenv("GROQ_AGENT_TOOL_TRANSPORT", "native")
    monkeypatch.setenv("GROQ_AGENT_REASONING_EFFORT", "high")
    ai = client()
    assert ai.agent_profile()["tool_transport"] == "native"
    assert ai.agent_profile()["reasoning_effort"] is None
    override = ai.agent_profile(model="qwen/qwen3.8-27b", tool_transport="json", reasoning_effort="medium")
    assert override == {"provider": "groq", "model": "qwen/qwen3.8-27b", "tool_transport": "json",
                        "reasoning_effort": "medium", "strict_forced": False}
    assert ai.agent_profile(tool_choice="none")["reasoning_effort"] is None
    with pytest.raises(AIProviderError, match="transport"):
        ai.agent_profile(tool_transport="unsupported")
