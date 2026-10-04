import json

import httpx
import pytest

from scaffold.ai.contracts import AIProviderError, ChatMessage, InferenceTier
from scaffold.ai.groq import GroqLLM


@pytest.mark.parametrize('strict', [False, True])
async def test_structured_strict_flag_sent_only_when_explicit(monkeypatch, strict):
    requests = []
    async def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'model': 'openai/gpt-oss-20b',
            'choices': [{'message': {'content': '{"score":80}'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 23, 'completion_tokens': 7},
        })
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond)))
    backend = GroqLLM(api_key='test', base_url='https://test.invalid',
                      models={InferenceTier.INTERMEDIATE: 'openai/gpt-oss-20b'})
    schema = {'type': 'object', 'properties': {'score': {'type': 'integer', 'enum': [80]}},
              'required': ['score'], 'additionalProperties': False}
    result = await backend.complete_structured(model='openai/gpt-oss-20b',
        messages=[ChatMessage(role='user', content='test')], schema=schema,
        max_tokens=100, strict=strict)
    assert len(requests) == 1
    wire = requests[0]['response_format']
    assert wire['type'] == 'json_schema' and wire['json_schema']['schema'] == schema
    assert wire['json_schema'].get('strict') is (True if strict else None)
    assert result.input_tokens == 23 and result.output_tokens == 7 and result.finish_reason == 'stop'


async def test_strict_rejects_json_object_without_network():
    backend = GroqLLM(api_key='test', base_url='https://test.invalid', models={})
    with pytest.raises(AIProviderError, match='requires json_schema'):
        await backend.complete_structured(model='openai/gpt-oss-20b', messages=[], schema={},
                                          max_tokens=100, strict=True, schema_transport='json_object')
