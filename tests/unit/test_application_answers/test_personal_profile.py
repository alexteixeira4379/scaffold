import pytest
from types import SimpleNamespace
from scaffold.candidate_profile import normalize_cpf, effective_work_modes, application_preparation
from scaffold.application_answers.contracts import (
    CandidateContext,
    Question,
    QuestionOption,
    AnswerType,
)
from scaffold.application_answers.matcher import CommonMatcher


@pytest.mark.parametrize("value", ["11111111111", "12345678900", "123", "52998224725x"])
def test_invalid_cpf(value):
    with pytest.raises(ValueError):
        normalize_cpf(value)


def test_cpf_normalization_and_missing():
    assert normalize_cpf("529.982.247-25") == "52998224725"
    assert normalize_cpf("") is None


@pytest.mark.parametrize("strict", [True, False])
def test_personal_data_never_falls_back_to_guess(strict):
    matcher = CommonMatcher(CandidateContext(candidate_id=1), strict=strict)
    for label in [
        "CPF",
        "Raça/cor",
        "Orientação sexual",
        "Identidade de gênero",
        "Você possui deficiência?",
        "CID",
        "Sexo",
    ]:
        answer = matcher.match(
            Question("q", label, is_required=True, options=[QuestionOption("Não", "no")])
        )
        assert answer.type == AnswerType.SKIP
        assert answer.value == ""


@pytest.mark.parametrize("strict", [True, False])
def test_decline_requires_matching_option(strict):
    matcher = CommonMatcher(
        CandidateContext(candidate_id=1, race_color="prefer_not_to_answer"), strict=strict
    )
    answer = matcher.match(
        Question("q", "Raça/cor", options=[QuestionOption("Prefiro não responder", "decline")])
    )
    assert answer.value == "decline"
    answer = matcher.match(Question("q", "Raça/cor", options=[QuestionOption("Branca", "white")]))
    assert answer.type == AnswerType.SKIP


def test_cpf_and_declarations_from_explicit_facts():
    matcher = CommonMatcher(
        CandidateContext(candidate_id=1, cpf="52998224725", gender="Mulher cis", race_color="Parda")
    )
    assert matcher.match(Question("q", "CPF")).value == "52998224725"
    assert matcher.match(Question("q", "Identidade de gênero")).value == "Mulher cis"
    assert matcher.match(Question("q", "Sexo")).type == AnswerType.SKIP
    assert (
        matcher.match(Question("q", "Raça/cor", options=[QuestionOption("Parda", "parda")])).value
        == "parda"
    )


def test_work_modes_legacy_and_multiple():
    assert effective_work_modes("hybrid", None) == ["hybrid"]
    assert effective_work_modes("remote", []) == ["remote", "hybrid", "onsite"]
    assert effective_work_modes("unknown", ["remote", "hybrid"]) == ["remote", "hybrid"]


def test_generic_review_does_not_complete_application_setup():
    prefs = SimpleNamespace(reviewed_at="2026-01-01", salary_reviewed_at=None)
    data = SimpleNamespace(cpf="52998224725")
    status = application_preparation(prefs, data)
    assert not status["complete"]
    assert status["pending_fields"] == ["min_salary"]
    prefs.salary_reviewed_at = "2026-01-01"
    assert application_preparation(prefs, data)["complete"]


def test_contract_convention_and_all_default():
    for stored, expected in [("full_time", "CLT"), ("contract", "PJ"), ("unknown", "Todas")]:
        matcher = CommonMatcher(CandidateContext(candidate_id=1, employment_preference=stored))
        assert matcher.match(Question("q", "Tipo de contratação")).value == expected
        assert matcher.match(Question("q", "Você trabalhou como PJ?")).type == AnswerType.SKIP


@pytest.mark.parametrize("strict", [True, False])
def test_missing_salary_and_wrong_currency_never_invented(strict):
    ctx = CandidateContext(candidate_id=1)
    matcher = CommonMatcher(ctx, strict=strict)
    assert (
        matcher.match(Question("q", "Pretensão salarial", is_required=True)).type == AnswerType.SKIP
    )
    ctx.min_salary, ctx.currency = 8500.75, "BRL"
    assert matcher.match(Question("q", "Pretensão salarial")).value == "8500.75"
    assert matcher.match(Question("q", "Salary expectations USD")).type == AnswerType.SKIP
    assert matcher.match(Question("q", "Annual salary expectations")).type == AnswerType.SKIP
    assert matcher.match(Question("q", "Current salary")).type == AnswerType.SKIP


@pytest.mark.asyncio
async def test_unanswered_personal_fact_does_not_reach_ai_single_or_batch():
    from unittest.mock import AsyncMock
    from scaffold.application_answers.engine import AnswerEngine

    engine = AnswerEngine(AsyncMock())
    engine._context = CandidateContext(candidate_id=1)
    engine._matcher = CommonMatcher(engine._context)
    engine._ai_responder = AsyncMock()
    questions = [
        Question("cpf", "CPF", is_required=True),
        Question("race", "Raça/cor", is_required=True),
    ]
    assert (await engine.answer(questions[0])).type == AnswerType.SKIP
    assert all(answer.type == AnswerType.SKIP for answer in await engine.answer_batch(questions))
    engine._ai_responder.answer.assert_not_called()
    engine._ai_responder.answer_batch.assert_not_called()
