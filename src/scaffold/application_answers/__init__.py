"""Universal application form answer engine.

Provides a reusable library for answering job application form questions
based on candidate data (from database) and AI fallback, independent of
any specific platform (LinkedIn, ATS, Indeed, etc.).

Usage::

    from scaffold.application_answers import AnswerEngine, Question, Answer, AnswerType, QuestionOption

    engine = AnswerEngine(session_factory, storage_client=storage, ai_client=ai)
    await engine.load(candidate_id=42)
    answer = await engine.answer(question)
"""

from scaffold.application_answers.contracts import (
    Answer,
    AnswerType,
    CandidateContext,
    Question,
    QuestionOption,
    StoragePort,
)
from scaffold.application_answers.engine import AnswerEngine

__all__ = [
    "Answer",
    "AnswerEngine",
    "AnswerType",
    "CandidateContext",
    "Question",
    "QuestionOption",
    "StoragePort",
]
