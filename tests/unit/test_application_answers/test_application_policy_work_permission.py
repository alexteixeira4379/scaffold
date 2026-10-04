from scaffold.application_answers.application_policy import deterministic, validate
from scaffold.application_answers.contracts import AnswerType, CandidateContext, Question, QuestionOption


def context():
    return CandidateContext(42, application_context={"authorized_match": True,
        "job": {"location": "Slovakia - Kosice"}})


def question():
    return Question("fresh-native-id", "Are you authorized to work in the country in which you’re applying?",
                    is_required=True, options=[QuestionOption("Yes", "yes-id"), QuestionOption("No", "no-id")])


def test_unknown_work_permission_does_not_infer_either_factual_yes_or_no():
    q, ctx = question(), context()
    result = deterministic(q, ctx)
    assert result.type == AnswerType.SKIP
    assert result.rejection_reason == "protected_fact_unavailable"
    assert ctx.work_authorization is None
    q.options.reverse()
    assert deterministic(q, ctx).type == AnswerType.SKIP
    assert validate(q, {"answer": "yes-id", "kind": "intent", "basis": ["application_context"]}, ctx).type == AnswerType.SKIP


def test_explicit_permission_wins_over_unknown_default():
    ctx = context()
    ctx.work_authorization = "Yes"
    assert deterministic(question(), ctx).value == "yes-id"
    ctx.work_authorization = "No"
    assert deterministic(question(), ctx).value == "no-id"


def test_true_nonconfirmation_option_can_resolve_unknown_permission():
    q = question()
    q.options.append(QuestionOption("Not confirmed", "unconfirmed-id"))
    result = deterministic(q, context())
    assert result.value == "unconfirmed-id"
    assert result.source == "non_disclosure"


def test_unknown_option_precedes_nonaffirmation_and_optional_is_not_defaulted():
    q = question()
    q.options.append(QuestionOption("Unknown", "unknown-id"))
    assert deterministic(q, context()).value == "unknown-id"
    q.options.pop()
    q.is_required = False
    assert deterministic(q, context()).type == AnswerType.SKIP


def test_compound_permission_or_sponsorship_is_not_silently_negated():
    q = question()
    q.question = "Are you authorized to work and do you require sponsorship?"
    assert deterministic(q, context()).type == AnswerType.SKIP
