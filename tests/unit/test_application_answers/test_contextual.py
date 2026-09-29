import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from scaffold.application_answers.contracts import CandidateContext, Question, QuestionOption, AnswerType
from scaffold.application_answers.contextual import build_prompt, validate
from scaffold.application_answers.engine import AnswerEngine


@pytest.fixture
def context():
    return CandidateContext(42, cpf="52998224725", min_salary=8500, currency="BRL",
                            employment_preference="contract", resume_version_id=55,
                            resume_content="Developed Python APIs and led a distributed team since 2020.",
                            resume_local_path="/tmp/authorized.pdf")


async def test_engine_infers_after_deterministic_miss(monkeypatch, context):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context",
                        AsyncMock(return_value=context))
    ai = AsyncMock()
    ai.basic.return_value = MagicMock(as_json=lambda: {
        "pj": {"answer": "yes", "kind": "inferred", "basis": ["employment_preference"]},
        "role": {"answer": "backend", "kind": "derived", "basis": ["authorized_resume"]},
        "past": {"answer": "Valor não disponível no histórico informado.", "kind": "qualified", "basis": []},
    })
    engine = AnswerEngine(AsyncMock(), ai_client=ai, contextual=True)
    await engine.load(42)
    answers = await engine.answer_batch([
        Question("cpf", "CPF"),
        Question("pj", "Você tem interesse em trabalhar como PJ?", options=[QuestionOption("Sim", "yes")]),
        Question("role", "Atuação principal?", options=[QuestionOption("Backend", "backend")]),
        Question("past", "Última remuneração fixa e PLR/PPR?", is_required=True),
        Question("file", "Currículo", field_type="file_resume"),
    ])
    assert [a.value for a in answers] == [context.cpf, "yes", "backend",
                                         "Valor não disponível no histórico informado.", "/tmp/authorized.pdf"]
    assert answers[1].source == "ai_inferred"
    ai.basic.assert_awaited_once()
    sent = json.loads(ai.basic.await_args.args[0])
    assert {q["id"] for q in sent["questions"]} == {"pj", "role", "past"}
    assert context.cpf not in ai.basic.await_args.args[0]
    assert sent["candidate"]["authorized_resume"]["content"] == context.resume_content


@pytest.mark.parametrize("label", ["CPF", "Raça/cor", "Identidade de gênero", "CID", "Você possui deficiência?"])
async def test_sensitive_missing_never_reaches_model(monkeypatch, label):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context",
                        AsyncMock(return_value=CandidateContext(42)))
    ai = AsyncMock()
    engine = AnswerEngine(AsyncMock(), ai_client=ai, contextual=True)
    await engine.load(42)
    assert (await engine.answer(Question("q", label, is_required=True))).type == AnswerType.SKIP
    ai.basic.assert_not_awaited()


@pytest.mark.parametrize("record", [
    {"answer": "yes", "kind": "inferred", "basis": ["invented_key"]},
    {"answer": "yes", "kind": "inferred", "basis": []},
    {"answer": "not_an_option", "kind": "inferred", "basis": ["authorized_resume"]},
    {"answer": "yes", "kind": "bogus", "basis": ["authorized_resume"]},
    "yes", None,
])
def test_invalid_answers_do_not_choose_first_option(context, record):
    q = Question("q", "Question", options=[QuestionOption("Yes", "yes")])
    assert validate(q, record, context).type == AnswerType.SKIP


def test_constraints_and_complete_option_list(context):
    q = Question("q", "Experience", field_type="numeric", min_value=0, max_value=10)
    for value in ("11", "-1", "NaN", "Infinity", "five years"):
        assert validate(q, {"answer": value, "kind": "derived", "basis": ["authorized_resume"]}, context).type == AnswerType.SKIP
    assert validate(q, {"answer": "6", "kind": "derived", "basis": ["authorized_resume"]}, context).value == "6"
    q.max_length = 1
    assert validate(q, {"answer": "6.5", "kind": "derived", "basis": ["authorized_resume"]}, context).type == AnswerType.SKIP
    q.options = [QuestionOption(f"Band {i}", str(i)) for i in range(20)]
    payload = json.loads(build_prompt([q], context))
    assert len(payload["questions"][0]["options"]) == 20
    assert payload["questions"][0]["max_value"] == 10


async def test_consent_and_model_failure_have_no_arbitrary_fallback(monkeypatch, context):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context",
                        AsyncMock(return_value=context))
    ai = AsyncMock()
    ai.basic.side_effect = ValueError("malformed response")
    engine = AnswerEngine(AsyncMock(), ai_client=ai, contextual=True)
    await engine.load(42)
    consent = Question("consent", "I agree", field_type="consent", options=[QuestionOption("Yes", "yes")])
    assert (await engine.answer(consent)).type == AnswerType.SKIP
    ai.basic.assert_not_awaited()
    context.custom_answers["consent"] = "yes"
    assert (await engine.answer(consent)).value == "yes"
    answer = await engine.answer(Question("q", "Main technology?", options=[QuestionOption("Java", "java")]))
    assert answer.type == AnswerType.SKIP
    ai.basic.assert_awaited_once()
