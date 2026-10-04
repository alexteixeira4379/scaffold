import json

import httpx
import pytest

from scaffold.ai.contracts import AIProviderError, ChatMessage, InferenceTier
from scaffold.ai.groq import GroqLLM, structured_error_metadata


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


async def test_structured_http_error_preserves_safe_diagnostic_without_private_body(monkeypatch):
    calls = []
    async def respond(request):
        calls.append(request)
        return httpx.Response(400, json={'error': {
            'failed_generation': 'PRIVATE_CANDIDATE ' * 200,
            'message': 'Failed to generate JSON. PRIVATE_CANDIDATE',
            'type': 'invalid_request_error', 'code': 'json_validate_failed',
            'param': 'response_format.private_candidate_field',
        }})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond)))
    backend = GroqLLM(api_key='PRIVATE_SECRET', base_url='https://test.invalid', models={})
    with pytest.raises(AIProviderError) as caught:
        await backend.complete_structured(model='openai/gpt-oss-20b',
            messages=[ChatMessage(role='user', content='PRIVATE_CANDIDATE')], schema={},
            max_tokens=100, strict=True)
    assert len(calls) == 1
    assert str(caught.value) == 'groq http 400'
    diagnostic = caught.value.provider_error
    assert diagnostic['code'] == 'json_validate_failed'
    assert diagnostic['message'] == 'json_generation_failed'
    assert diagnostic['param'] == 'response_format.<redacted>'
    assert diagnostic['failed_generation_chars'] > 500
    assert diagnostic['message_chars'] > 0
    assert diagnostic['generation_shape']['json_parsed'] is False
    assert len(diagnostic['response_hash']) == 64
    assert 'private' not in json.dumps(diagnostic).lower()
    assert caught.value.usage is None


@pytest.mark.parametrize('body', [
    b'PRIVATE_CANDIDATE non-json upstream response',
    b'[]', b'{"error":[]}',
    b'{"error":{"message":"PRIVATE_CANDIDATE","code":["PRIVATE_CANDIDATE"],'
    b'"type":"PRIVATE_CANDIDATE","param":"PRIVATE_CANDIDATE"}}',
])
def test_unknown_error_content_is_never_exposed(body):
    diagnostic = structured_error_metadata(httpx.Response(400, content=body))
    assert diagnostic['http_status'] == 400
    assert diagnostic['message'] == 'provider_message_redacted'
    assert 'PRIVATE_CANDIDATE' not in json.dumps(diagnostic)


def test_schema_path_and_technical_constraint_survive_without_untrusted_text():
    diagnostic = structured_error_metadata(httpx.Response(400, json={'error': {
        'message': 'Invalid JSON schema: maxItems not supported. PRIVATE_NAME CPF123',
        'param': 'response_format.json_schema.schema.properties.candidate_evidence_ids.maxItems',
        'type': 'invalid_request_error',
    }}))
    assert diagnostic['param'].endswith('candidate_evidence_ids.maxItems')
    assert diagnostic['message'] == 'invalid_json_schema'
    assert 'maxItems' in diagnostic['technical_terms']
    assert 'PRIVATE_NAME' not in json.dumps(diagnostic)
    assert 'CPF123' not in json.dumps(diagnostic)
