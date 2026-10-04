"""Independent ATS opt-in contract checks; no provider calls or database writes."""
import json
from unittest.mock import AsyncMock

import pytest

from scaffold.application_answers import application_policy as policy
from scaffold.application_answers.contextual import validate as legacy_validate
from scaffold.application_answers.contracts import AnswerType, CandidateContext, Question, QuestionOption
from scaffold.application_answers.engine import AnswerEngine


@pytest.fixture
def application_context():
    return {
        "authorized_match": True,
        "job": {"title": "Engenheiro de Dados", "company": "Example", "description": "Python e pipelines de dados.",
                "location": "São Paulo", "remote_type": "hybrid"},
        "target": {"title": "Engenharia de Dados"},
    }


@pytest.fixture
def context(application_context):
    return CandidateContext(42, resume_version_id=55,
                            resume_content="Python e SQL em pipelines desde 2020.",
                            application_context=application_context)


def record(value, kind="inferred", basis=None):
    return {"answer": value, "kind": kind, "basis": basis if basis is not None else ["application_context"]}


def test_opt_in_kinds_do_not_change_legacy_validation(context):
    q = Question("opinion", "Tem interesse nesta oportunidade?")
    for kind in ("intent", "estimated"):
        assert legacy_validate(q, record("Sim", kind), context).type == AnswerType.SKIP


async def test_application_policy_requires_authorized_match_context(monkeypatch):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context",
                        AsyncMock(return_value=CandidateContext(42)))
    engine = AnswerEngine(AsyncMock(), ai_client=AsyncMock(), application_policy=True)
    with pytest.raises(ValueError):
        await engine.load(42, application_context={"authorized_match": False})


def test_authorized_intention_is_not_an_existing_candidate_fact(context):
    question = Question("intent", "Tem interesse em participar desta oportunidade?",
                        options=[QuestionOption("Não", "no"), QuestionOption("Sim", "yes")])
    answer = policy.validate(question, record("yes", "intent"), context)
    assert answer.value == "yes"
    assert answer.source == "ai_intent"
    assert context.custom_answers == {}
    assert context.availability is None


def test_all_real_options_and_constraints_are_available(context):
    question = Question("many", "Selecione tecnologias", multiple_choice=True, step_value=0.5,
                        min_value=0, max_value=20, max_length=80,
                        options=[QuestionOption(f"Tecnologia {i}", f"tech-{i}") for i in range(30)])
    payload = json.loads(policy.build_prompt([question], context))
    field = next(q for q in payload["questions"] if q["id"] == "many")
    assert len(field["options"]) == 30
    assert field["multiple_choice"] is True
    assert field["step_value"] == 0.5
    assert field["min_value"] == 0 and field["max_value"] == 20
    assert field["max_length"] == 80


@pytest.mark.parametrize("value", ['["python","unknown"]', '["python","python"]', '"python"', '[1]', '[]'])
def test_multiple_options_never_guess_or_select_first(context, value):
    question = Question("skills", "Selecione linguagens", is_required=True, multiple_choice=True,
                        options=[QuestionOption("Java", "java"), QuestionOption("Python", "python")])
    answer = policy.validate(question, record(value, "derived", ["authorized_resume"]), context)
    assert answer.type == AnswerType.SKIP


def test_multiple_options_retain_exact_values(context):
    question = Question("skills", "Selecione linguagens", multiple_choice=True,
                        options=[QuestionOption("Java", "java"), QuestionOption("Python", "python"), QuestionOption("SQL", "sql")])
    answer = policy.validate(question, record('["python","sql"]', "derived", ["authorized_resume"]), context)
    assert set(json.loads(answer.value)) == {"python", "sql"}
    assert "java" not in answer.value


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "100001", "17050"])
def test_numeric_estimates_obey_actual_step_and_limits(context, value):
    question = Question("expectation", "Pretensão salarial para esta oportunidade", field_type="number",
                        min_value=1000, max_value=100000, step_value=100)
    assert policy.validate(question, record(value, "estimated"), context).type == AnswerType.SKIP


def test_valid_estimate_is_traced_and_does_not_update_salary(context):
    question = Question("expectation", "Pretensão salarial para esta oportunidade", field_type="number",
                        min_value=1000, max_value=100000, step_value=100)
    answer = policy.validate(question, record("17000", "estimated"), context)
    assert answer.value == "17000" and answer.source == "ai_estimated"
    assert context.min_salary is None


def test_missing_identifier_is_never_generated(context):
    question = Question("identity", "CPF", is_required=True)
    assert policy.validate(question, record("12345678901", "estimated"), context).type == AnswerType.SKIP


def test_unknown_optional_identity_can_stay_empty_without_generic_fabrication(context):
    question = Question("identity", "CPF", is_required=False)
    answer = policy.fallback(question, context)
    assert answer.type == AnswerType.SKIP or answer.value == ""


def test_explicit_answer_wins_even_when_application_intent_differs(context):
    question = Question("future-random-id", "Você aceita a modalidade híbrida?",
                        options=[QuestionOption("Sim", "Y"), QuestionOption("Não", "N")])
    context.custom_answers[question.id] = "N"
    answer = policy.deterministic(question, context)
    assert answer.value == "N" and answer.source == "explicit_application_answer"


def test_radio_reordering_and_native_values_do_not_change_semantic_choice(context):
    options = [QuestionOption("Não", "negative-native-91"), QuestionOption("Sim", "positive-native-37")]
    question = Question("random-id", "Você tem interesse nesta oportunidade?", options=options)
    record_by_label = record("Sim", "intent")
    first = policy.validate(question, record_by_label, context)
    question.options = list(reversed(options))
    second = policy.validate(question, record_by_label, context)
    assert first.value == second.value == "positive-native-37"


@pytest.mark.parametrize("kind", [[], {}, None, 17])
def test_malformed_kind_is_rejected_without_throwing(context, kind):
    assert policy.validate(Question("q", "Motivação?"), record("Resposta", kind), context).type == AnswerType.SKIP


def test_professional_estimate_for_unseen_prr_field_is_allowed(context):
    question = Question("company-question-unknown-4829", "Qual expectativa anual de PRR para esta oportunidade?",
                        field_type="number", min_value=0, max_value=100000, step_value=100)
    answer = policy.validate(question, record("12000", "estimated"), context)
    assert answer.value == "12000" and answer.source == "ai_estimated"


def test_unknown_historical_numeric_compensation_uses_authorized_estimate(context):
    question = Question("historic-unseen", "Qual foi sua última remuneração recebida?",
                        field_type="number", is_required=True, min_value=1000, max_value=50000, step_value=100)
    assert policy.deterministic(question, context) is None
    answer = policy.validate(question, record("15000", "estimated"), context)
    assert answer.value == "15000" and answer.source == "ai_estimated"
    assert context.min_salary is None and context.custom_answers == {}


def test_ats_prompt_does_not_invent_salary_period_or_explicit_work_preference(context):
    facts = json.loads(policy.build_prompt([], context))["candidate"]
    assert "salary_period" not in facts
    assert "accepted_work_modes" not in facts
    assert "work_mode_search_filter" in facts


async def test_repair_only_revisits_invalid_question_and_keeps_valid_answer(monkeypatch, context):
    from unittest.mock import MagicMock
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context", AsyncMock(return_value=context))
    ai = AsyncMock()
    ai.basic.side_effect = [
        MagicMock(as_json=lambda: {
            "motivation": record("Quero contribuir com soluções de dados.", "inferred", ["authorized_resume"]),
            "prr-new": record("NaN", "estimated"),
        }),
        MagicMock(as_json=lambda: {"prr-new": record("12000", "estimated")}),
    ]
    engine = AnswerEngine(AsyncMock(), ai_client=ai, application_policy=True)
    await engine.load(42, application_context=context.application_context)
    result = await engine.answer_batch([
        Question("motivation", "O que motiva sua candidatura?", is_required=True),
        Question("prr-new", "Qual expectativa anual de PRR?", is_required=True,
                 field_type="number", min_value=0, max_value=50000, step_value=100),
    ])
    assert [answer.value for answer in result] == ["Quero contribuir com soluções de dados.", "12000"]
    assert ai.basic.await_count == 2
    repair = json.loads(ai.basic.await_args_list[1].args[0])
    assert [q["id"] for q in repair["questions"]] == ["prr-new"]
    assert repair["validation_feedback"]


async def test_repair_budget_remains_bounded_across_dynamic_steps(monkeypatch, context, caplog):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context", AsyncMock(return_value=context))
    ai = AsyncMock()
    ai.basic.side_effect = RuntimeError("PRIVATE_PROVIDER_BODY")
    engine = AnswerEngine(AsyncMock(), ai_client=ai, application_policy=True)
    await engine.load(42, application_context=context.application_context)
    for index in range(6):
        answer = await engine.answer(Question(f"future-{index}", "Como pretende contribuir?", is_required=True))
        assert answer.value and answer.source == "authorized_qualified_fallback"
    assert ai.basic.await_count <= 4
    assert "PRIVATE_PROVIDER_BODY" not in caplog.text


def test_estimated_numeric_fallback_respects_grid_below_non_aligned_maximum(context):
    context.min_salary = 20000
    question = Question("historic-numeric", "Última remuneração", field_type="number", is_required=True,
                        min_value=1000, max_value=17550, step_value=100)
    answer = policy.fallback(question, context)
    assert answer.type != AnswerType.SKIP
    assert 1000 <= float(answer.value) <= 17550
    assert (float(answer.value) - 1000) % 100 == 0
    assert answer.source == "authorized_estimated_fallback"
    assert context.min_salary == 20000
