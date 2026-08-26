"""Tests for application_answers contracts."""

from scaffold.application_answers.contracts import (
    Answer,
    AnswerType,
    CandidateContext,
    Question,
    QuestionOption,
)


class TestQuestionOption:
    def test_creation(self):
        opt = QuestionOption(label="Yes", value="yes")
        assert opt.label == "Yes"
        assert opt.value == "yes"


class TestQuestion:
    def test_minimal(self):
        q = Question(id="q1", question="What is your email?")
        assert q.id == "q1"
        assert q.question == "What is your email?"
        assert q.question_complement is None
        assert q.is_required is False
        assert q.options is None
        assert q.current_value is None

    def test_full(self):
        opts = [QuestionOption(label="Yes", value="yes"), QuestionOption(label="No", value="no")]
        q = Question(
            id="q2",
            question="Do you have experience?",
            question_complement="Select one",
            is_required=True,
            options=opts,
            current_value="yes",
        )
        assert q.is_required is True
        assert len(q.options) == 2
        assert q.current_value == "yes"


class TestAnswerType:
    def test_values(self):
        assert AnswerType.TEXT == "text"
        assert AnswerType.OPTION == "option"
        assert AnswerType.FILE == "file"
        assert AnswerType.BOOLEAN == "boolean"
        assert AnswerType.LINK == "link"
        assert AnswerType.SKIP == "skip"

    def test_strenum(self):
        assert str(AnswerType.TEXT) == "text"
        assert AnswerType("option") == AnswerType.OPTION


class TestAnswer:
    def test_defaults(self):
        a = Answer(question_id="q1", type=AnswerType.TEXT, value="hello")
        assert a.confidence == 1.0
        assert a.source == "unknown"

    def test_custom_confidence(self):
        a = Answer(
            question_id="q2",
            type=AnswerType.OPTION,
            value="yes",
            confidence=0.8,
            source="ai",
        )
        assert a.confidence == 0.8
        assert a.source == "ai"


class TestCandidateContext:
    def test_defaults(self):
        ctx = CandidateContext(candidate_id=1)
        assert ctx.candidate_id == 1
        assert ctx.full_name == ""
        assert ctx.email == ""
        assert ctx.languages == []
        assert ctx.custom_answers == {}
        assert ctx.resume_local_path is None

    def test_populated(self):
        ctx = CandidateContext(
            candidate_id=42,
            full_name="John Doe",
            email="john@example.com",
            phone="+1234567890",
            country="US",
            years_of_experience=5,
            languages=["English", "Portuguese"],
            custom_answers={"favorite_color": "blue"},
        )
        assert ctx.full_name == "John Doe"
        assert ctx.years_of_experience == 5
        assert len(ctx.languages) == 2
