from scaffold.application_answers.application_policy import deterministic, validate
from scaffold.application_answers.contracts import AnswerType, CandidateContext, Question, QuestionOption


def context():
    return CandidateContext(42, application_context={"authorized_match": True,
        "job": {"location": "Slovakia - Kosice"}})


def question():
    return Question("fresh-native-id", "Are you authorized to work in the country in which you’re applying?",
                    is_required=True, options=[QuestionOption("Yes", "yes-id"), QuestionOption("No", "no-id")])


def test_unknown_work_permission_is_not_inferred_yes_from_application_intent():
    q, ctx = question(), context()
    result = deterministic(q, ctx)
    assert result.value == "no-id"
    assert result.source == "work_authorization_not_confirmed"
    assert ctx.work_authorization is None
    q.options.reverse()
    assert deterministic(q, ctx).value == "no-id"
    assert validate(q, {"answer": "yes-id", "kind": "intent", "basis": ["application_context"]}, ctx).type == AnswerType.SKIP


def test_explicit_permission_wins_over_unknown_default():
    ctx = context()
    ctx.work_authorization = "Yes"
    assert deterministic(question(), ctx).value == "yes-id"


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
