"""Tests for AIResponder post-processing logic."""

import pytest

from scaffold.application_answers.ai_responder import (
    AIResponder,
    _extract_salary,
    _is_numeric,
    _is_salary,
)
from scaffold.application_answers.contracts import (
    AnswerType,
    Question,
    QuestionOption,
)


class TestExtractSalary:
    def test_plain_number(self):
        assert _extract_salary("120000") == "120000"

    def test_with_dollar_sign(self):
        assert _extract_salary("$120,000") == "120000"

    def test_k_notation_lower(self):
        assert _extract_salary("90k") == "90000"

    def test_k_notation_upper(self):
        assert _extract_salary("90K") == "90000"

    def test_with_text(self):
        assert _extract_salary("I expect around $120,000 per year") == "120000"

    def test_short_number_via_k(self):
        assert _extract_salary("The salary should be 150k") == "150000"

    def test_fallback_to_any_digits(self):
        assert _extract_salary("about 85") == "85"

    def test_no_numbers(self):
        assert _extract_salary("not sure") == "not sure"


class TestIsNumeric:
    def test_how_many(self):
        assert _is_numeric("how many years of experience do you have?")

    def test_number_of(self):
        assert _is_numeric("number of projects you managed")

    def test_scale(self):
        assert _is_numeric("on a scale of 1-10, rate your skill")

    def test_not_numeric(self):
        assert not _is_numeric("what is your name?")


class TestIsSalary:
    def test_salary(self):
        assert _is_salary("what is your expected salary?")

    def test_compensation(self):
        assert _is_salary("desired compensation")

    def test_not_salary(self):
        assert not _is_salary("what is your favorite color?")


class TestPostProcess:
    """Test AIResponder._post_process via a real instance (mocked AI client not needed)."""

    @pytest.fixture
    def responder(self):
        from unittest.mock import AsyncMock

        return AIResponder(AsyncMock())

    def test_numeric_extracts_number(self, responder):
        q = Question(id="q1", question="How many years of experience?")
        ans = responder._post_process(q, "I have 7 years of experience")
        assert ans.value == "7"
        assert ans.type == AnswerType.TEXT

    def test_salary_extracts_value(self, responder):
        q = Question(id="q1", question="What is your salary expectation?")
        ans = responder._post_process(q, "I expect around $120,000 annually")
        assert ans.value == "120000"

    def test_option_matching(self, responder):
        q = Question(
            id="q1",
            question="Experience level?",
            options=[
                QuestionOption(label="Junior", value="junior"),
                QuestionOption(label="Senior", value="senior"),
                QuestionOption(label="Lead", value="lead"),
            ],
        )
        ans = responder._post_process(q, "Senior")
        assert ans.type == AnswerType.OPTION
        assert ans.value == "senior"
        assert ans.confidence == 0.8

    def test_option_fuzzy_matching(self, responder):
        q = Question(
            id="q1",
            question="Education?",
            options=[
                QuestionOption(label="Bachelor's Degree", value="bachelors"),
                QuestionOption(label="Master's Degree", value="masters"),
            ],
        )
        ans = responder._post_process(q, "I have a Master's degree")
        assert ans.type == AnswerType.OPTION
        assert ans.value == "masters"

    def test_option_fallback_to_first(self, responder):
        q = Question(
            id="q1",
            question="Pick one",
            options=[
                QuestionOption(label="Alpha", value="alpha"),
                QuestionOption(label="Beta", value="beta"),
            ],
        )
        ans = responder._post_process(q, "completely unrelated garbage xyz")
        assert ans.type == AnswerType.OPTION
        assert ans.value == "alpha"
        assert ans.confidence == 0.5

    def test_plain_text_passthrough(self, responder):
        q = Question(id="q1", question="Tell us about yourself")
        ans = responder._post_process(q, "I am a passionate engineer")
        assert ans.type == AnswerType.TEXT
        assert ans.value == "I am a passionate engineer"
        assert ans.confidence == 0.8
        assert ans.source == "ai"
