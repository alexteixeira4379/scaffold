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


async def test_latest_resume_content_matches_downloaded_file(monkeypatch):
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=object())
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    candidate = SimpleNamespace(full_name='Test', email='test@example.org', phone=None,
                                country=None, location=None, linkedin_url=None)
    resume = SimpleNamespace(id=55, content='Python engineer', storage_url='resume/55.pdf')
    monkeypatch.setattr(loader.candidate_repository, 'get', AsyncMock(return_value=candidate))
    monkeypatch.setattr(loader.candidate_preference_repository, 'get_by_candidate_id', AsyncMock(return_value=None))
    monkeypatch.setattr(loader, '_load_application_data', AsyncMock(return_value=None))
    monkeypatch.setattr(loader.resume_version_repository, 'list_by_candidate_id', AsyncMock(return_value=[resume]))
    monkeypatch.setattr(loader.cover_letter_version_repository, 'list_by_candidate_id', AsyncMock(return_value=[]))
    download = AsyncMock(return_value='/tmp/resume55.pdf')
    monkeypatch.setattr(loader, '_download_file', download)
    storage = object()
    ctx = await loader.load_candidate_context(factory, 42, storage_client=storage)
    assert (ctx.resume_version_id, ctx.resume_content, ctx.resume_local_path) == (55, 'Python engineer', '/tmp/resume55.pdf')
    download.assert_awaited_once_with(storage, 'resume/55.pdf', 'resume_42')


def test_strict_prompt_contains_authorized_resume_and_all_options():
    ctx = CandidateContext(42, resume_version_id=55, resume_content='Python since 2015')
    q = Question('salary', 'Salary?', is_required=True,
                 options=[QuestionOption(f'Band {i}', str(i)) for i in range(20)])
    prompt = build_batch_prompt([q], ctx, strict=True)
    assert 'Python since 2015' in prompt
    assert 'Band 19' in prompt
    assert 'MUST provide' not in prompt
    assert 'empty answer' in prompt
    assert 'authorized_resume' not in build_batch_prompt([q], ctx)


def test_strict_ai_rejects_unfounded_remote_experience():
    from scaffold.application_answers.ai_responder import AIResponder
    from scaffold.application_answers.contracts import AnswerType
    responder = AIResponder(AsyncMock(), strict=True)
    ctx = CandidateContext(42, resume_version_id=55, resume_content='Senior Python developer')
    q = Question('remote', 'Você já trabalhou em ambiente remoto?', options=[QuestionOption('Sim', 'yes')])
    for record in [{'answer': 'yes', 'evidence': 'Worked remotely'},
                   {'answer': 'yes', 'evidence': 'Senior Python developer'},
                   {'answer': 'yes', 'evidence': ''}]:
        assert responder._grounded_answer(q, record, ctx).type == AnswerType.SKIP
    ctx.resume_content = 'Worked remotely since 2020'
    assert responder._grounded_answer(q, {'answer': 'yes', 'evidence': ctx.resume_content}, ctx).value == 'yes'


def test_strict_ai_uses_verbatim_structured_resume_skill():
    from scaffold.application_answers.ai_responder import AIResponder
    ctx = CandidateContext(42, resume_version_id=55, resume_content='{"skills": ["Python"]}')
    answer = AIResponder(AsyncMock(), strict=True)._grounded_answer(
        Question('tech', 'Main technology?'), {'answer': 'Python', 'evidence': 'Python'}, ctx)
    assert answer.value == 'Python'
    assert answer.source == 'ai'
