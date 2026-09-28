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
