"""Tests for the AnswerEngine orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from scaffold.application_answers.contracts import (
    AnswerType,
    CandidateContext,
    Question,
    QuestionOption,
)
from scaffold.application_answers.engine import AnswerEngine


# --- Fixtures ---


@pytest.fixture
def mock_session_factory():
    factory = AsyncMock()
    return factory


@pytest.fixture
def mock_ai_client():
    client = AsyncMock()
    return client


@pytest.fixture
def loaded_context() -> CandidateContext:
    return CandidateContext(
        candidate_id=42,
        full_name="Ana Costa",
        email="ana@test.com",
        phone="+5511988776655",
        country="BR",
        location="Rio de Janeiro",
        linkedin_url="https://linkedin.com/in/anacosta",
        min_salary=100000.0,
        years_of_experience=5,
        work_authorization="Yes",
        education_level="Bachelor's",
        availability="2 weeks",
        resume_local_path="/tmp/resume_42.pdf",
    )


# --- Engine initialization ---


class TestEngineInit:
    async def test_raises_if_not_loaded(self, mock_session_factory):
        engine = AnswerEngine(mock_session_factory)
        q = Question(id="q1", question="Email?")
        with pytest.raises(RuntimeError, match="load\\(\\) must be called"):
            await engine.answer(q)

    def test_context_is_none_before_load(self, mock_session_factory):
        engine = AnswerEngine(mock_session_factory)
        assert engine.context is None


# --- Engine with pre-loaded context (bypassing DB) ---


class TestEngineAnswer:
    @pytest.fixture
    def engine(self, mock_session_factory, mock_ai_client, loaded_context):
        e = AnswerEngine(mock_session_factory, ai_client=mock_ai_client)
        # Bypass actual load — inject context directly
        e._context = loaded_context
        from scaffold.application_answers.matcher import CommonMatcher

        e._matcher = CommonMatcher(loaded_context)
        from scaffold.application_answers.ai_responder import AIResponder

        e._ai_responder = AIResponder(mock_ai_client)
        return e

    async def test_matcher_resolves_email(self, engine):
        q = Question(id="q1", question="What is your email address?")
        ans = await engine.answer(q)
        assert ans.type == AnswerType.TEXT
        assert ans.value == "ana@test.com"
        assert ans.source == "database"
        assert ans.confidence == 1.0

    async def test_matcher_resolves_resume(self, engine):
        q = Question(id="q1", question="Please upload your CV")
        ans = await engine.answer(q)
        assert ans.type == AnswerType.FILE
        assert ans.value == "/tmp/resume_42.pdf"

    async def test_ai_fallback_when_matcher_fails(self, engine, mock_ai_client):
        """When matcher cannot answer, AI is used as fallback."""
        from scaffold.ai.contracts import CompletionResult, ResponseMode

        mock_ai_client.basic.return_value = CompletionResult(
            output=ResponseMode.TEXT,
            text="I am passionate about technology",
            data=None,
        )

        q = Question(id="q1", question="Why do you want this job?", is_required=True)
        ans = await engine.answer(q)
        assert ans.source == "ai"
        assert ans.confidence < 1.0
        assert "passionate" in ans.value

    async def test_ai_with_options_matches_best(self, engine, mock_ai_client):
        """AI response is matched against available options."""
        from scaffold.ai.contracts import CompletionResult, ResponseMode

        mock_ai_client.basic.return_value = CompletionResult(
            output=ResponseMode.TEXT,
            text="Yes, I am authorized",
            data=None,
        )

        q = Question(
            id="q1",
            question="Can you relocate?",
            options=[
                QuestionOption(label="Yes", value="yes"),
                QuestionOption(label="No", value="no"),
            ],
        )
        ans = await engine.answer(q)
        assert ans.type == AnswerType.OPTION
        assert ans.value == "yes"

    async def test_default_for_optional_when_all_fail(self, engine, mock_ai_client):
        """Optional question gets SKIP when nothing works."""
        mock_ai_client.basic.side_effect = RuntimeError("AI unavailable")

        q = Question(id="q1", question="Any additional comments?", is_required=False)
        ans = await engine.answer(q)
        assert ans.type == AnswerType.SKIP
        assert ans.source == "default"

    async def test_default_for_required_when_all_fail(self, engine, mock_ai_client):
        """Required question gets a TEXT default when nothing works."""
        mock_ai_client.basic.side_effect = RuntimeError("AI unavailable")

        q = Question(id="q1", question="Explain your motivation", is_required=True)
        ans = await engine.answer(q)
        assert ans.type == AnswerType.TEXT
        assert ans.value == "N/A"
        assert ans.source == "default"

    async def test_skip_already_filled(self, engine):
        q = Question(id="q1", question="Name?", current_value="Already There")
        ans = await engine.answer(q)
        assert ans.type == AnswerType.SKIP
        assert ans.value == "Already There"


class TestEngineAnswerBatch:
    @pytest.fixture
    def engine(self, mock_session_factory, mock_ai_client, loaded_context):
        e = AnswerEngine(mock_session_factory, ai_client=mock_ai_client)
        e._context = loaded_context
        from scaffold.application_answers.matcher import CommonMatcher

        e._matcher = CommonMatcher(loaded_context)
        from scaffold.application_answers.ai_responder import AIResponder

        e._ai_responder = AIResponder(mock_ai_client)
        return e

    async def test_batch_mixes_matcher_and_ai(self, engine, mock_ai_client):
        from scaffold.ai.contracts import CompletionResult, ResponseMode

        mock_ai_client.basic.return_value = CompletionResult(
            output=ResponseMode.TEXT,
            text="I love building distributed systems",
            data=None,
        )

        questions = [
            Question(id="q1", question="What is your email?"),
            Question(id="q2", question="Phone number"),
            Question(id="q3", question="Why do you want this job?", is_required=True),
        ]

        answers = await engine.answer_batch(questions)
        assert len(answers) == 3
        assert answers[0].value == "ana@test.com"
        assert answers[0].source == "database"
        assert answers[1].value == "5511988776655"
        assert answers[2].source == "ai"
        assert "distributed" in answers[2].value

    async def test_batch_empty(self, engine):
        answers = await engine.answer_batch([])
        assert answers == []

    async def test_batch_all_matcher(self, engine):
        questions = [
            Question(id="q1", question="Email?"),
            Question(id="q2", question="First name"),
        ]
        answers = await engine.answer_batch(questions)
        assert len(answers) == 2
        assert all(a.source == "database" for a in answers)

    async def test_batch_ai_failure_uses_defaults(self, engine, mock_ai_client):
        mock_ai_client.basic.side_effect = RuntimeError("AI down")

        questions = [
            Question(id="q1", question="Unknown question X?", is_required=True),
        ]
        answers = await engine.answer_batch(questions)
        assert len(answers) == 1
        assert answers[0].source == "default"


class TestEngineNoAI:
    """Test engine behavior when no AI client is provided."""

    @pytest.fixture
    def engine(self, mock_session_factory, loaded_context):
        e = AnswerEngine(mock_session_factory, ai_client=None)
        e._context = loaded_context
        from scaffold.application_answers.matcher import CommonMatcher

        e._matcher = CommonMatcher(loaded_context)
        # No AI responder
        e._ai_responder = None
        return e

    async def test_falls_through_to_default(self, engine):
        q = Question(id="q1", question="Random unknown thing?", is_required=True)
        ans = await engine.answer(q)
        assert ans.source == "default"
        assert ans.value == "N/A"

    async def test_options_default_to_first(self, engine):
        q = Question(
            id="q1",
            question="Something weird?",
            options=[
                QuestionOption(label="A", value="a"),
                QuestionOption(label="B", value="b"),
            ],
        )
        ans = await engine.answer(q)
        assert ans.type == AnswerType.OPTION
        assert ans.value == "a"
        assert ans.source == "default"
