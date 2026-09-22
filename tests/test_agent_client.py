import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scaffold.ai import AIClient, InferenceTier, ResponseMode
from scaffold.ai.agent import AgentMessage, ToolDefinition
from scaffold.ai.contracts import AIProviderError
from scaffold.ai.groq import GroqLLM, strict_forced_schema
from scaffold.ai.memory import InMemoryLLM


async def test_native_calls_preserve_ids_and_usage_without_changing_completion():
    backend = GroqLLM(
        api_key="test",
        base_url="https://provider.invalid",
        models={InferenceTier.COMPLEX: "test-model"},
    )
    request = httpx.Request("POST", "https://provider.invalid/chat/completions")
    response = httpx.Response(
        200,
        request=request,
        json={
            "model": "actual-model",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "read", "arguments": "{}"},
                            }
                        ],
                    },
                }
            ],
        },
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        result = await AIClient(backend).agent(
            [AgentMessage(role="user", content="test")],
            [ToolDefinition(name="read", description="Read", parameters={"type": "object"})],
        )
    assert result.model == "actual-model"
    assert result.input_tokens == 100
    assert result.message.tool_calls[0].id == "call-1"
    assert post.call_args.kwargs["json"]["tool_choice"] == "auto"
    # Legacy onboarding backend remains usable without native tools.
    legacy = await AIClient(InMemoryLLM()).basic("hello", ResponseMode.TEXT)
    assert "hello" in legacy.text


async def test_provider_error_never_leaks_candidate_content():
    backend = GroqLLM(
        api_key="test",
        base_url="https://provider.invalid",
        models={InferenceTier.COMPLEX: "test-model"},
    )
    response = httpx.Response(400, text="private resume failed generation")
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        with pytest.raises(AIProviderError, match="^groq http 400$"):
            await AIClient(backend).agent([], [])


async def test_json_validation_code_is_preserved_without_failed_generation():
    backend = GroqLLM(
        api_key="test",
        base_url="https://provider.invalid",
        models={InferenceTier.COMPLEX: "test-model"},
    )
    response = httpx.Response(
        400,
        json={
            "error": {
                "code": "json_validate_failed",
                "message": "private resume",
                "failed_generation": "private draft",
            }
        },
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        with pytest.raises(AIProviderError, match=r"^groq http 400 \(json_validate_failed\)$"):
            await AIClient(backend).agent([], [])


async def test_native_tool_result_round_trip_keeps_matching_call_id():
    messages = [
        AgentMessage(
            role="assistant",
            tool_calls=[{"id": "x", "function": {"name": "read", "arguments": "{}"}}],
        ),
        AgentMessage(role="tool", tool_call_id="x", content=json.dumps({"status": "ok"})),
    ]
    decoded = [AgentMessage.model_validate_json(m.model_dump_json()) for m in messages]
    assert decoded[1].tool_call_id == decoded[0].tool_calls[0].id


def test_tool_contract_inlines_nested_refs_without_losing_title_field():
    schema = {
        "type": "object",
        "properties": {"draft": {"$ref": "#/$defs/Draft"}},
        "$defs": {
            "Draft": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            }
        },
    }
    wire = ToolDefinition(name="finish", description="Finish", parameters=schema).wire()
    nested = wire["function"]["parameters"]["properties"]["draft"]
    assert nested["properties"]["title"]["type"] == "string"
    assert "$ref" not in json.dumps(wire)
    assert "$defs" in schema  # Input contract is not mutated.


async def test_forced_gpt_oss_result_uses_json_transport_and_still_returns_tool_contract():
    backend = GroqLLM(
        api_key="test",
        base_url="https://provider.invalid",
        models={InferenceTier.COMPLEX: "openai/gpt-oss-120b"},
    )
    response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"issues":[]}', "reasoning": "private reasoning"},
                }
            ]
        },
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        result = await AIClient(backend).agent(
            [AgentMessage(role="user", content="Review")],
            [
                ToolDefinition(
                    name="review_result", description="Review", parameters={"type": "object"}
                )
            ],
            tool_choice={"type": "function", "function": {"name": "review_result"}},
        )
    body = post.call_args.kwargs["json"]
    assert body["response_format"] == {"type": "json_object"}
    assert "tools" not in body
    call = result.message.tool_calls[0]
    assert call.function.name == "review_result"
    assert json.loads(call.function.arguments) == {"issues": []}
    assert "private reasoning" not in result.model_dump_json()


async def test_gpt_oss_json_routing_preserves_read_tool_identity():
    backend = GroqLLM(
        api_key="test",
        base_url="https://provider.invalid",
        models={InferenceTier.COMPLEX: "openai/gpt-oss-120b"},
    )
    response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"calls":[{"name":"read","arguments":{"section":"summary"}}]}'
                    },
                }
            ]
        },
    )
    messages = [
        AgentMessage(
            role="assistant",
            tool_calls=[{"id": "previous-call", "function": {"name": "read", "arguments": "{}"}}],
        ),
        AgentMessage(role="tool", tool_call_id="previous-call", content='{"status":"ok"}'),
    ]
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)) as post:
        result = await AIClient(backend).agent(
            messages,
            [ToolDefinition(name="read", description="Read", parameters={"type": "object"})],
        )
    sent = post.call_args.kwargs["json"]["messages"]
    assert json.loads(sent[1]["content"])["tool_result_for"] == "previous-call"
    assert result.message.tool_calls[0].function.name == "read"
    assert json.loads(result.message.tool_calls[0].function.arguments) == {"section": "summary"}


async def test_json_routing_rejects_unlisted_tool_before_returning_it():
    backend = GroqLLM(
        api_key="test",
        base_url="https://provider.invalid",
        models={InferenceTier.COMPLEX: "openai/gpt-oss-120b"},
    )
    response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"calls":[{"name":"execute_sql","arguments":{}}]}'},
                }
            ]
        },
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        with pytest.raises(AIProviderError, match="invalid agent response"):
            await AIClient(backend).agent(
                [], [ToolDefinition(name="read", description="Read", parameters={"type": "object"})]
            )


def test_strict_forced_schema_preserves_constraints_and_does_not_close_domain_payloads():
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "issues": {"type": "array", "maxItems": 12, "items": {
            "type": "object", "additionalProperties": False, "properties": {
                "reason": {"type": "string", "default": "", "maxLength": 800},
            }, "required": []}},
        "question": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
    }, "required": ["issues"]}
    original = json.dumps(schema)
    strict = strict_forced_schema(schema)
    assert strict["required"] == ["issues", "question"]
    assert strict["properties"]["issues"]["items"]["required"] == ["reason"]
    assert strict["properties"]["issues"]["maxItems"] == 12
    assert strict["properties"]["question"]["anyOf"][-1] == {"type": "null"}
    assert "default" not in json.dumps(strict)
    assert json.dumps(schema) == original
    schema["properties"]["payload"] = {"type": "object", "additionalProperties": True}
    assert strict_forced_schema(schema) is None
    schema["properties"]["payload"] = {}
    assert strict_forced_schema(schema) is None


@pytest.mark.parametrize("enabled,closed,expected", [
    (True, True, "json_schema"), (False, True, "json_object"), (True, False, "json_object"),
])
async def test_strict_forced_transport_is_opt_in_and_preserves_tool_result(monkeypatch, enabled, closed, expected):
    monkeypatch.setenv("GROQ_AGENT_STRICT_FORCED", str(enabled).lower())
    backend = GroqLLM(api_key="test", base_url="https://provider.invalid",
                      models={InferenceTier.COMPLEX: "openai/gpt-oss-120b"})
    schema = {"type": "object", "additionalProperties": not closed,
              "properties": {"issues": {"type": "array", "items": {"type": "string"}}},
              "required": ["issues"]}
    result = httpx.Response(200, json={"choices": [{"finish_reason": "stop",
                           "message": {"content": '{"issues":[]}'}}]})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=result)) as post:
        output = await AIClient(backend).agent([], [ToolDefinition(
            name="review_result", description="Review", parameters=schema)],
            tool_choice={"type": "function", "function": {"name": "review_result"}})
    body = post.call_args.kwargs["json"]
    assert body["response_format"]["type"] == expected
    assert "tools" not in body
    assert output.message.tool_calls[0].function.name == "review_result"
    assert json.loads(output.message.tool_calls[0].function.arguments) == {"issues": []}
