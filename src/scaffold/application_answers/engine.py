"""AnswerEngine — Universal application form answer engine."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from scaffold.application_answers.ai_responder import AIResponder
from scaffold.application_answers.candidate_context import load_candidate_context
from scaffold.application_answers.contracts import (
    Answer,
    AnswerType,
    CandidateContext,
    Question,
    StoragePort,
)
from scaffold.application_answers.matcher import CommonMatcher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scaffold.ai import AIClient

logger = logging.getLogger(__name__)


class AnswerEngine:
    """Universal engine for answering job application form questions.

    Usage::

        engine = AnswerEngine(session_factory, storage_client=storage, ai_client=ai)
        await engine.load(candidate_id=42)

        answer = await engine.answer(question)
        answers = await engine.answer_batch(questions)
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage_client: StoragePort | None = None,
        ai_client: AIClient | None = None,
    ) -> None:
        """Initialize the AnswerEngine.

        Args:
            session_factory: SQLAlchemy async session factory (from scaffold).
            storage_client: Optional StoragePort implementation for file downloads.
            ai_client: Optional scaffold AIClient. If None, AI fallback is disabled.
        """
        self._session_factory = session_factory
        self._storage_client = storage_client
        self._ai_client = ai_client
        self._context: CandidateContext | None = None
        self._matcher: CommonMatcher | None = None
        self._ai_responder: AIResponder | None = None

    @property
    def context(self) -> CandidateContext | None:
        """Access the loaded candidate context (None if load() not called)."""
        return self._context

    async def load(self, candidate_id: int) -> None:
        """Load candidate data from the database.

        Must be called once before answer() or answer_batch().
        Downloads resume/cover letter to temp files if storage_client is provided.
        """
        self._context = await load_candidate_context(
            self._session_factory,
            candidate_id,
            storage_client=self._storage_client,
        )
        self._matcher = CommonMatcher(self._context)
        if self._ai_client is not None:
            self._ai_responder = AIResponder(self._ai_client)

        logger.info(
            "answer_engine_loaded candidate_id=%d has_resume=%s has_ai=%s",
            candidate_id,
            self._context.resume_local_path is not None,
            self._ai_responder is not None,
        )

    async def answer(self, question: Question) -> Answer:
        """Answer a single question.

        Strategy (in order):
          1. CommonMatcher: deterministic answer from candidate data
          2. AIResponder: LLM fallback if matcher cannot resolve
          3. Default: safe generic value for required questions

        Returns:
            Answer with type, value, confidence, and source.
        """
        if self._context is None or self._matcher is None:
            raise RuntimeError("AnswerEngine.load() must be called before answer()")

        # 1. Try deterministic matcher
        result = self._matcher.match(question)
        if result is not None:
            logger.debug(
                "answer_matched question_id=%s source=database type=%s",
                question.id,
                result.type,
            )
            return result

        # 2. Try AI fallback
        if self._ai_responder is not None:
            try:
                result = await self._ai_responder.answer(question, self._context)
                logger.debug(
                    "answer_ai question_id=%s confidence=%s",
                    question.id,
                    result.confidence,
                )
                return result
            except Exception as exc:
                logger.warning(
                    "ai_answer_failed question_id=%s error=%s",
                    question.id,
                    exc,
                )

        # 3. Default fallback
        return self._default_answer(question)

    async def answer_batch(self, questions: list[Question]) -> list[Answer]:
        """Answer a batch of questions.

        Tries CommonMatcher individually first. Unanswered questions go to AI
        in a single batch request for efficiency.
        """
        if self._context is None or self._matcher is None:
            raise RuntimeError("AnswerEngine.load() must be called before answer_batch()")

        answers: list[Answer] = []
        unanswered: list[tuple[int, Question]] = []

        # Phase 1: deterministic matching
        for i, question in enumerate(questions):
            result = self._matcher.match(question)
            if result is not None:
                answers.append(result)
            else:
                answers.append(None)  # type: ignore[arg-type]
                unanswered.append((i, question))

        # Phase 2: AI batch
        if unanswered and self._ai_responder is not None:
            ai_questions = [q for _, q in unanswered]
            try:
                ai_answers = await self._ai_responder.answer_batch(ai_questions, self._context)
                for (idx, _), ai_answer in zip(unanswered, ai_answers):
                    answers[idx] = ai_answer
            except Exception as exc:
                logger.warning("ai_batch_failed error=%s, using defaults", exc)
                for idx, question in unanswered:
                    if answers[idx] is None:
                        answers[idx] = self._default_answer(question)

        # Phase 3: fill remaining None slots with defaults
        for i, ans in enumerate(answers):
            if ans is None:
                answers[i] = self._default_answer(questions[i])

        return answers

    def _default_answer(self, question: Question) -> Answer:
        """Safe default for unanswerable questions."""
        if question.options:
            return Answer(
                question_id=question.id,
                type=AnswerType.OPTION,
                value=question.options[0].value,
                confidence=0.3,
                source="default",
            )
        if not question.is_required:
            return Answer(
                question_id=question.id,
                type=AnswerType.SKIP,
                value="",
                confidence=0.0,
                source="default",
            )
        return Answer(
            question_id=question.id,
            type=AnswerType.TEXT,
            value="N/A",
            confidence=0.3,
            source="default",
        )
