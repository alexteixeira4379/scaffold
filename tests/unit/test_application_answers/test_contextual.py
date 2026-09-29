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


@pytest.mark.parametrize("value", ["riCZvuAj6iB8", "Senior"])
async def test_inhire_seniority_label_or_value(monkeypatch, value):
    context = CandidateContext(42, resume_version_id=55,
                              resume_content="Sr. Full Stack Engenier; Engenheiro de software - Senior")
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context",
                        AsyncMock(return_value=context))
    question_id = "typeform:kO0GZG3B:SjTvgqqZm2VN"
    ai = AsyncMock()
    ai.basic.return_value = MagicMock(as_json=lambda: {
        question_id: {"answer": value, "kind": "derived", "basis": ["authorized_resume"]}
    })
    engine = AnswerEngine(AsyncMock(), ai_client=ai, contextual=True)
    await engine.load(42, resume_version_id=55)
    answer, = await engine.answer_batch([Question(question_id, "Qual a sua senioridade na área de tecnologia?",
        is_required=True, options=[QuestionOption("Junior", "nJPZRJAf4uS4"),
                                  QuestionOption("Pleno", "5L3T0Ekkt0w6"),
                                  QuestionOption("Senior", "riCZvuAj6iB8"),
                                  QuestionOption("Especialista", "QuLPsTy1Pwhy")])])
    assert answer.value == "riCZvuAj6iB8"
    assert answer.type == AnswerType.OPTION
    assert answer.rejection_reason is None
    assert "Sr. Full Stack Engenier" in ai.basic.await_args.args[0]
    ai.basic.assert_awaited_once()


def test_duplicate_labels_do_not_guess(context):
    q = Question("q", "Level?", options=[QuestionOption("Senior", "one"), QuestionOption("Senior", "two")])
    record = {"answer": "Senior", "kind": "derived", "basis": ["authorized_resume"]}
    assert validate(q, record, context).rejection_reason == "ambiguous_option_label"


@pytest.mark.parametrize("record,reason", [
    (None, "missing_record"),
    ("Senior", "invalid_record"),
    ({"answer": "Senior", "kind": [], "basis": []}, "invalid_kind"),
    ({"answer": "Senior", "kind": "direct", "basis": ["authorized_resume.missing"]}, "invalid_basis_reference"),
    ({"answer": "", "kind": "unresolved", "basis": []}, "model_unresolved"),
])
def test_diagnostic_reasons(context, record, reason):
    assert validate(Question("q", "Question"), record, context).rejection_reason == reason


async def test_one_bad_record_does_not_discard_good_answers(monkeypatch, context):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context", AsyncMock(return_value=context))
    ai = AsyncMock()
    ai.basic.return_value = MagicMock(as_json=lambda: {
        "bad": {"answer": "Senior", "kind": [], "basis": []},
        "good": {"answer": "Python", "kind": "derived", "basis": ["authorized_resume"]},
    })
    engine = AnswerEngine(AsyncMock(), ai_client=ai, contextual=True)
    await engine.load(42)
    bad, good = await engine.answer_batch([Question("bad", "Level?"), Question("good", "Technology?")])
    assert bad.rejection_reason == "invalid_kind"
    assert good.value == "Python"


@pytest.mark.parametrize("mode,reason", [("call", "ai_call_failed"),
    ("json", "invalid_json_response"), ("shape", "invalid_batch_shape")])
async def test_batch_failure_reasons_without_raw_data(monkeypatch, context, mode, reason, caplog):
    monkeypatch.setattr("scaffold.application_answers.engine.load_candidate_context", AsyncMock(return_value=context))
    ai = AsyncMock()
    if mode == "call":
        ai.basic.side_effect = RuntimeError("PRIVATE_RESPONSE_BODY")
    elif mode == "json":
        ai.basic.return_value = MagicMock()
        ai.basic.return_value.as_json.side_effect = ValueError("PRIVATE_RESPONSE_BODY")
    else:
        ai.basic.return_value = MagicMock(as_json=lambda: [])
    engine = AnswerEngine(AsyncMock(), ai_client=ai, contextual=True)
    await engine.load(42)
    answer, = await engine.answer_batch([Question("q", "Seniority?")])
    assert answer.rejection_reason == reason
    assert "PRIVATE_RESPONSE_BODY" not in caplog.text
    ai.basic.assert_awaited_once()


@pytest.mark.parametrize("reference", ["authorized_resume.content", "candidate.authorized_resume.content",
                                      "$.candidate.authorized_resume.content", " authorized_resume "])
def test_existing_nested_basis_is_normalized(context, reference):
    answer = validate(Question("q", "Technology?"),
                      {"answer": "Python", "kind": "derived", "basis": [reference]}, context)
    assert answer.value == "Python"
    assert answer.basis == ["authorized_resume"]


@pytest.mark.parametrize("reference", ["authorized_resume.missing", "candidate.missing", "email",
                                      "authorized_resume.content.missing", 12, {}, None])
def test_basis_must_resolve_to_nonempty_value(context, reference):
    answer = validate(Question("q", "Technology?"),
                      {"answer": "Python", "kind": "derived", "basis": [reference]}, context)
    assert answer.rejection_reason == "invalid_basis_reference"


def test_basis_list_index_and_false_are_real_values(context):
    from scaffold.application_answers.contextual import resolve_basis
    assert resolve_basis("candidate.skills[0]", {"skills": ["Python"]}) == "skills"
    assert resolve_basis("skills[1]", {"skills": ["Python"]}) is None
    assert resolve_basis("flag", {"flag": False}) == "flag"
    assert resolve_basis("years", {"years": 0}) == "years"


def test_production_candidate_prefix_and_structured_resume(context):
    context.resume_content = json.dumps({"experiences": [{"role": "Engineer"}]})
    for reference in ("candidate.min_salary", "candidate.authorized_resume.content.experiences",
                      "candidate.authorized_resume.content.experiences[0].role"):
        answer = validate(Question("q", "Question"),
                          {"answer": "Answer", "kind": "derived", "basis": [reference]}, context)
        assert answer.type == AnswerType.TEXT
    assert isinstance(json.loads(build_prompt([], context))["candidate"]["authorized_resume"]["content"], dict)


def test_missing_sensitive_fact_uses_only_offered_non_disclosure():
    from scaffold.application_answers.personal_facts import match_personal_fact
    ctx = CandidateContext(42)
    q = Question('q', 'Você é uma Pessoa com Deficiência?', options=[
        QuestionOption('Sim', 'yes'), QuestionOption('Não', 'no'),
        QuestionOption('Prefiro não responder', 'decline')])
    assert match_personal_fact(q, ctx, contextual=True).value == 'decline'
    ctx.disability_status = 'no'
    assert match_personal_fact(q, ctx, contextual=True).value == 'no'
    ctx.disability_status = None
    q.options = q.options[:2]
    assert match_personal_fact(q, ctx, contextual=True).type == AnswerType.SKIP


def test_unique_resume_section_aliases(context):
    from scaffold.application_answers.contextual import resolve_basis
    data = {"authorized_resume": {"content": {"languages": ["English"], "experiences": ["Engineer"]}}}
    assert resolve_basis("languages", data) == "authorized_resume"
    assert resolve_basis("experiences", data) == "authorized_resume"
    assert resolve_basis("candidate.languages", data) == "authorized_resume"
    assert resolve_basis("skills", data) is None
    data["other"] = {"languages": ["Portuguese"]}
    assert resolve_basis("languages", data) is None
