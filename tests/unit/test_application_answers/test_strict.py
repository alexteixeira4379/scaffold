from unittest.mock import AsyncMock
from scaffold.application_answers.contracts import (
    CandidateContext,
    Question,
    QuestionOption,
    AnswerType,
)
from scaffold.application_answers.matcher import CommonMatcher
from scaffold.application_answers.ai_responder import AIResponder
from scaffold.application_answers.engine import AnswerEngine


def test_strict_matcher_does_not_pick_first_option():
    ctx = CandidateContext(1, country="Brazil")
    q = Question(
        "country",
        "Country",
        is_required=True,
        options=[QuestionOption("France", "fr"), QuestionOption("USA", "us")],
    )
    assert CommonMatcher(ctx, strict=True).match(q) is None
    assert CommonMatcher(ctx).match(q).value == "fr"  # Existing consumers retain behavior.


def test_strict_ai_unmatched_option_is_unresolved():
    q = Question(
        "x",
        "Choose",
        is_required=True,
        options=[QuestionOption("Yes", "yes"), QuestionOption("No", "no")],
    )
    answer = AIResponder(AsyncMock(), strict=True)._post_process(q, "missing information")
    assert answer.type == AnswerType.SKIP
    assert answer.value == ""


def test_strict_required_default_is_unresolved():
    answer = AnswerEngine(AsyncMock(), strict=True)._default_answer(
        Question("x", "Unknown", is_required=True)
    )
    assert answer.type == AnswerType.SKIP
    assert answer.value == ""


def test_strict_no_substring_option_match():
    ctx = CandidateContext(1, custom_answers={"x": "No"})
    q = Question(
        "x",
        "Declaration",
        options=[QuestionOption("Not applicable", "na"), QuestionOption("No", "no")],
    )
    assert CommonMatcher(ctx, strict=True).match(q).value == "no"


def test_strict_does_not_reuse_personal_fact_for_a_different_question():
    context = CandidateContext(
        1,
        full_name="Candidate Example",
        years_of_experience=12,
        min_salary=10000,
        custom_answers={"name": "Candidate Example"},
    )
    matcher = CommonMatcher(context, strict=True)
    for label in [
        "Nome da liderança direta",
        "Nome de preferência",
        "Years of experience with Rust",
        "Previous salary",
        "Manager email",
    ]:
        assert matcher.match(Question("other", label)) is None
    assert matcher.match(Question("name", "Full name")).value == "Candidate Example"
    assert matcher.match(Question("other", "Full name")).value == "Candidate Example"


def test_strict_residence_does_not_use_job_search_target():
    context = CandidateContext(1, target_country="Brazil", target_location="São Paulo")
    matcher = CommonMatcher(context, strict=True)
    assert matcher.match(Question("country", "Country")) is None
    assert matcher.match(Question("location", "Current location")) is None


def test_required_markers_do_not_change_fact_identity():
    matcher = CommonMatcher(
        CandidateContext(1, full_name="Candidate Example", email="fixture@example.test"),
        strict=True,
    )
    assert matcher.match(Question("name", "Full name ✱")).value == "Candidate Example"
    assert matcher.match(Question("email", "Email *")).value == "fixture@example.test"


def test_strict_phone_preserves_explicit_international_prefix():
    context = CandidateContext(1, phone="+55 11 99999-9999")
    question = Question("phone", "Phone")
    assert CommonMatcher(context, strict=True).match(question).value == "+55 11 99999-9999"
    assert CommonMatcher(context).match(question).value == "5511999999999"
