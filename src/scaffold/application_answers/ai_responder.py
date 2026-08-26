"""AI-based fallback responder using scaffold.ai.AIClient."""

from __future__ import annotations

import logging
import re

from scaffold.ai import AIClient, ResponseMode
from scaffold.application_answers.contracts import (
    Answer,
    AnswerType,
    CandidateContext,
    Question,
)
from scaffold.application_answers.matcher import _find_best_option
from scaffold.application_answers.prompts import (
    SYSTEM_PROMPT,
    build_batch_prompt,
    build_single_question_prompt,
)

logger = logging.getLogger(__name__)

_AI_TEMPERATURE = 0.3
_AI_MAX_TOKENS_SINGLE = 500
_AI_MAX_TOKENS_BATCH = 2000


class AIResponder:
    """Fallback responder that uses an LLM to answer application questions."""

    def __init__(self, ai_client: AIClient) -> None:
        self._ai = ai_client

    async def answer(self, question: Question, context: CandidateContext) -> Answer:
        """Answer a single question using AI."""
        prompt = build_single_question_prompt(question, context)

        result = await self._ai.basic(
            prompt,
            ResponseMode.TEXT,
            system=SYSTEM_PROMPT,
            temperature=_AI_TEMPERATURE,
            max_tokens=_AI_MAX_TOKENS_SINGLE,
        )

        raw_answer = result.as_text().strip()
        return self._post_process(question, raw_answer)

    async def answer_batch(
        self, questions: list[Question], context: CandidateContext
    ) -> list[Answer]:
        """Answer multiple questions in a single AI call."""
        if not questions:
            return []

        # For a single question, just use the single-question method
        if len(questions) == 1:
            return [await self.answer(questions[0], context)]

        prompt = build_batch_prompt(questions, context)

        result = await self._ai.basic(
            prompt,
            ResponseMode.JSON,
            system=SYSTEM_PROMPT,
            temperature=_AI_TEMPERATURE,
            max_tokens=_AI_MAX_TOKENS_BATCH,
        )

        answers: list[Answer] = []
        try:
            data = result.as_json()
        except Exception as exc:
            logger.warning("ai_batch_json_parse_failed error=%s, falling back to individual", exc)
            # Fallback: answer individually
            for q in questions:
                try:
                    ans = await self.answer(q, context)
                    answers.append(ans)
                except Exception as e:
                    logger.warning("ai_individual_answer_failed question_id=%s error=%s", q.id, e)
                    answers.append(self._default_answer(q))
            return answers

        for question in questions:
            raw = data.get(question.id, "")
            if raw:
                answers.append(self._post_process(question, str(raw)))
            else:
                answers.append(self._default_answer(question))

        return answers

    def _post_process(self, question: Question, raw_answer: str) -> Answer:
        """Post-process AI answer: match options, extract numbers, etc."""
        q_lower = question.question.lower()

        # Numeric questions → extract number
        if _is_numeric(q_lower):
            numbers = re.findall(r"\d+", raw_answer)
            if numbers:
                raw_answer = numbers[0]

        # Salary questions → extract numeric value
        if _is_salary(q_lower):
            raw_answer = _extract_salary(raw_answer)

        # If question has options, match against them
        if question.options:
            matched = _find_best_option(raw_answer, question.options, threshold=0.5)
            if matched is not None:
                return Answer(
                    question_id=question.id,
                    type=AnswerType.OPTION,
                    value=matched.value,
                    confidence=0.8,
                    source="ai",
                )
            # Fallback to first option if no match
            return Answer(
                question_id=question.id,
                type=AnswerType.OPTION,
                value=question.options[0].value,
                confidence=0.5,
                source="ai",
            )

        return Answer(
            question_id=question.id,
            type=AnswerType.TEXT,
            value=raw_answer,
            confidence=0.8,
            source="ai",
        )

    def _default_answer(self, question: Question) -> Answer:
        """Provide a safe default answer when AI fails."""
        if question.options:
            return Answer(
                question_id=question.id,
                type=AnswerType.OPTION,
                value=question.options[0].value,
                confidence=0.3,
                source="default",
            )
        return Answer(
            question_id=question.id,
            type=AnswerType.TEXT,
            value="N/A",
            confidence=0.3,
            source="default",
        )


def _is_numeric(text: str) -> bool:
    patterns = ["how many", "number of", "scale", "1-10", "1 to 10", "rate", "numeric"]
    return any(p in text for p in patterns)


def _is_salary(text: str) -> bool:
    patterns = ["salary", "compensation", "expectation", "pretensão"]
    return any(p in text for p in patterns)


def _extract_salary(raw: str) -> str:
    """Extract numeric salary value from text."""
    clean = raw.replace(",", "").replace("$", "").replace(" ", "")
    numbers = re.findall(r"\d{4,7}", clean)
    if numbers:
        return numbers[0]
    # Handle "90k" style
    k_match = re.findall(r"(\d+)\s*[kK]", raw)
    if k_match:
        return str(int(k_match[0]) * 1000)
    # Just try to extract any number
    numbers = re.findall(r"\d+", clean)
    if numbers:
        return numbers[0]
    return raw
