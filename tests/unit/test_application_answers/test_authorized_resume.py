from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from scaffold.application_answers import candidate_context as loader
from scaffold.application_answers.contracts import CandidateContext, Question, QuestionOption
from scaffold.application_answers.prompts import build_batch_prompt


@pytest.mark.parametrize('owner', [42, 99, None])
async def test_explicit_resume_never_uses_latest(monkeypatch, owner):
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=object())
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    candidate = SimpleNamespace(full_name='Test', email='test@example.org', phone=None,
                                country=None, location=None, linkedin_url=None)
    monkeypatch.setattr(loader.candidate_repository, 'get', AsyncMock(return_value=candidate))
    monkeypatch.setattr(loader.candidate_preference_repository, 'get_by_candidate_id', AsyncMock(return_value=None))
    monkeypatch.setattr(loader, '_load_application_data', AsyncMock(return_value=None))
    resume = SimpleNamespace(id=55, candidate_id=owner, content='Python developer since 2015', storage_url=None)
    get = AsyncMock(return_value=resume if owner else None)
    latest = AsyncMock(side_effect=AssertionError('must not select latest'))
    monkeypatch.setattr(loader.resume_version_repository, 'get', get)
    monkeypatch.setattr(loader.resume_version_repository, 'list_by_candidate_id', latest)
    monkeypatch.setattr(loader.cover_letter_version_repository, 'list_by_candidate_id', AsyncMock(return_value=[]))
    if owner != 42:
        with pytest.raises(ValueError, match='authorized_resume_not_found'):
            await loader.load_candidate_context(factory, 42, resume_version_id=55)
    else:
        ctx = await loader.load_candidate_context(factory, 42, resume_version_id=55)
        assert ctx.resume_version_id == 55
        assert ctx.resume_content == resume.content
    latest.assert_not_awaited()
    assert get.await_args.args[1] == 55


def test_strict_prompt_contains_authorized_resume_and_all_options():
    ctx = CandidateContext(42, resume_version_id=55, resume_content='Python since 2015')
    q = Question('salary', 'Salary?', is_required=True,
                 options=[QuestionOption(f'Band {i}', str(i)) for i in range(20)])
    prompt = build_batch_prompt([q], ctx, strict=True)
    assert 'Python since 2015' in prompt
    assert 'Band 19' in prompt
    assert 'MUST provide' not in prompt
    assert 'empty string' in prompt
    assert 'authorized_resume' not in build_batch_prompt([q], ctx)
