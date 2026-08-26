"""Deterministic answer matcher based on candidate data."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from scaffold.application_answers.contracts import (
    Answer,
    AnswerType,
    CandidateContext,
    Question,
    QuestionOption,
)


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def similarity_score(a: str, b: str) -> float:
    """Simple ratio similarity between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def _match_keywords(text: str, keywords: list[str]) -> bool:
    """Check if any keyword appears as a word boundary in text."""
    norm = normalize_text(text)
    for kw in keywords:
        kw_norm = normalize_text(kw)
        if not kw_norm:
            continue
        pattern = rf"\b{re.escape(kw_norm)}\b"
        if re.search(pattern, norm):
            return True
    return False


def _find_best_option(
    value: str, options: list[QuestionOption], threshold: float = 0.6
) -> QuestionOption | None:
    """Fuzzy-match value against question options."""
    if not options or not value:
        return None
    value_norm = normalize_text(value)
    best: QuestionOption | None = None
    best_score = 0.0
    for opt in options:
        label_norm = normalize_text(opt.label)
        value_norm_opt = normalize_text(opt.value)
        # Exact containment → max score
        if value_norm in label_norm or value_norm in value_norm_opt:
            return opt
        score = max(
            SequenceMatcher(None, value_norm, label_norm).ratio(),
            SequenceMatcher(None, value_norm, value_norm_opt).ratio(),
        )
        if score > best_score:
            best_score = score
            best = opt
    if best is not None and best_score >= threshold:
        return best
    return None


def _find_numeric_range_option(
    numeric_value: int, options: list[QuestionOption]
) -> QuestionOption | None:
    """Match a numeric value against range-style options like '1-3', '4-6', '7+'.

    Supported formats: 'N-M', 'N+', 'N or more', 'less than N', 'under N'.
    """
    for opt in options:
        text = normalize_text(opt.label)
        # Pattern: "N-M" or "N - M" (range)
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", opt.label)
        if range_match:
            low, high = int(range_match.group(1)), int(range_match.group(2))
            if low <= numeric_value <= high:
                return opt
            continue
        # Pattern: "N+" or "N or more" or "more than N" or "over N"
        plus_match = re.search(r"(\d+)\s*\+", opt.label)
        if plus_match:
            threshold = int(plus_match.group(1))
            if numeric_value >= threshold:
                return opt
            continue
        or_more_match = re.search(r"(\d+)\s*(?:or more|\+|plus)", text)
        if or_more_match:
            threshold = int(or_more_match.group(1))
            if numeric_value >= threshold:
                return opt
            continue
        more_than_match = re.search(r"(?:more than|over|above)\s*(\d+)", text)
        if more_than_match:
            threshold = int(more_than_match.group(1))
            if numeric_value > threshold:
                return opt
            continue
        # Pattern: "less than N" or "under N"
        less_match = re.search(r"(?:less than|under|below)\s*(\d+)", text)
        if less_match:
            threshold = int(less_match.group(1))
            if numeric_value < threshold:
                return opt
            continue
        # Exact match: option is just a number
        exact_match = re.fullmatch(r"\d+", opt.label.strip())
        if exact_match and int(exact_match.group(0)) == numeric_value:
            return opt
    return None


def _make_answer(
    question: Question,
    value: str,
    answer_type: AnswerType = AnswerType.TEXT,
) -> Answer:
    """Build an Answer, auto-matching against options if present."""
    if question.options:
        # Try numeric range matching first (for "1-3", "4-6", "7+" style options)
        if value.isdigit():
            range_opt = _find_numeric_range_option(int(value), question.options)
            if range_opt is not None:
                return Answer(
                    question_id=question.id,
                    type=AnswerType.OPTION,
                    value=range_opt.value,
                    confidence=1.0,
                    source="database",
                )
        # Fall back to fuzzy text matching
        matched_opt = _find_best_option(value, question.options)
        if matched_opt is not None:
            return Answer(
                question_id=question.id,
                type=AnswerType.OPTION,
                value=matched_opt.value,
                confidence=1.0,
                source="database",
            )
        # If no match and there are options, still return first option as safe default
        return Answer(
            question_id=question.id,
            type=AnswerType.OPTION,
            value=question.options[0].value,
            confidence=0.7,
            source="database",
        )
    return Answer(
        question_id=question.id,
        type=answer_type,
        value=value,
        confidence=1.0,
        source="database",
    )


# --------------------------------------------------------------------------
# Keyword → handler mapping
# --------------------------------------------------------------------------

_EXCLUDE_WORK_AUTH = ["work", "authorized", "autorizado", "permissão", "visto", "permit"]


class CommonMatcher:
    """Deterministic matcher that resolves questions from candidate data."""

    def __init__(self, context: CandidateContext) -> None:
        self._ctx = context
        self._dispatch_table: dict[str, object] = {
            "phone country code": self._handle_phone_country_code,
            "email": self._handle_email,
            "first name": self._handle_first_name,
            "last name": self._handle_last_name,
            "full name": self._handle_full_name,
            "phone": self._handle_phone,
            "linkedin": self._handle_linkedin,
            "resume": self._handle_resume,
            "cover letter": self._handle_cover_letter,
            "work authorization": self._handle_work_authorization,
            "citizenship": self._handle_citizenship,
            "experience": self._handle_experience,
            "education": self._handle_education,
            "salary": self._handle_salary,
            "availability": self._handle_availability,
            "gender": self._handle_gender,
            "veteran": self._handle_veteran,
            "disability": self._handle_disability,
            "city": self._handle_location,
            "country": self._handle_country,
        }

    def match(self, question: Question) -> Answer | None:
        """Try to answer a question from candidate data.

        Returns None if no deterministic answer can be provided.
        """
        # Note: We do NOT skip questions with current_value.
        # The LinkedIn form pre-fills with profile data that may be incorrect.
        # The engine should always provide the correct answer from our database,
        # and the caller (worker) decides whether to overwrite or keep.

        # Check custom_answers first (exact question id or keyword match)
        if self._ctx.custom_answers:
            for key, val in self._ctx.custom_answers.items():
                if key == question.id:
                    return _make_answer(question, str(val))
                # Normalize key (replace underscores with spaces) and check against question text
                key_words = key.replace("_", " ")
                if _match_keywords(question.question, [key_words]):
                    return _make_answer(question, str(val))

        text = question.question
        complement = question.question_complement or ""
        combined = f"{text} {complement}"

        # Ordered handlers — more specific patterns first
        # Each entry: (keywords, exclude_keywords, handler_key)
        handlers: list[tuple[list[str], list[str] | None, str]] = [
            (["phone country code", "country code", "phone code"], None, "phone country code"),
            (["email", "e-mail"], None, "email"),
            (["full name", "nome completo", "complete name"], None, "full name"),
            (
                ["first name", "given name", "nome", "primer nombre"],
                ["full name", "nome completo"],
                "first name",
            ),
            (["last name", "surname", "family name", "sobrenome", "apellido"], None, "last name"),
            (["phone", "telefone", "celular", "mobile"], None, "phone"),
            (["linkedin", "profile url"], None, "linkedin"),
            (["resume", "cv", "currículo", "curriculum"], ["cover letter", "carta"], "resume"),
            (["cover letter", "carta de apresentação"], None, "cover letter"),
            (
                [
                    "work authorization",
                    "autorização de trabalho",
                    "work permit",
                    "legally authorized",
                    "authorized to work",
                ],
                None,
                "work authorization",
            ),
            (["citizenship", "nacionalidade", "nationality"], None, "citizenship"),
            (
                ["experience", "experiência", "years of experience", "anos de experiência"],
                None,
                "experience",
            ),
            (["education", "degree", "graduação", "escolaridade"], None, "education"),
            (["salary", "compensation", "pretensão", "expectation"], None, "salary"),
            (
                ["availability", "disponibilidade", "start date", "notice period"],
                None,
                "availability",
            ),
            (["gender", "gênero", "sexo"], None, "gender"),
            (["veteran", "militar"], None, "veteran"),
            (["disability", "deficiência", "pcd"], None, "disability"),
            (["city", "cidade", "location", "localização"], _EXCLUDE_WORK_AUTH, "city"),
            (["country", "país"], _EXCLUDE_WORK_AUTH, "country"),
        ]

        for keywords, exclude, handler_key in handlers:
            if not _match_keywords(combined, keywords):
                continue
            if exclude and _match_keywords(combined, exclude):
                continue
            result = self._dispatch(handler_key, question)
            if result is not None:
                return result

        return None

    def _dispatch(self, handler_key: str, question: Question) -> Answer | None:
        """Route to the correct handler by primary keyword."""
        handler = self._dispatch_table.get(handler_key)
        if handler is None:
            return None
        return handler(question)  # type: ignore[operator]

    # --- Individual handlers ---

    def _handle_phone_country_code(self, question: Question) -> Answer | None:
        country = self._ctx.country or self._ctx.target_country
        if country and question.options:
            matched = _find_best_option(country, question.options)
            if matched:
                return Answer(
                    question_id=question.id,
                    type=AnswerType.OPTION,
                    value=matched.value,
                    confidence=1.0,
                    source="database",
                )
        return None

    def _handle_email(self, question: Question) -> Answer | None:
        if self._ctx.email:
            return _make_answer(question, self._ctx.email)
        return None

    def _handle_first_name(self, question: Question) -> Answer | None:
        if self._ctx.full_name:
            parts = self._ctx.full_name.strip().split()
            if parts:
                return _make_answer(question, parts[0])
        return None

    def _handle_last_name(self, question: Question) -> Answer | None:
        if self._ctx.full_name:
            parts = self._ctx.full_name.strip().split()
            if len(parts) > 1:
                return _make_answer(question, " ".join(parts[1:]))
        return None

    def _handle_full_name(self, question: Question) -> Answer | None:
        if self._ctx.full_name:
            return _make_answer(question, self._ctx.full_name)
        return None

    def _handle_phone(self, question: Question) -> Answer | None:
        if self._ctx.phone:
            # Strip non-digits for numeric fields
            digits = re.sub(r"\D", "", self._ctx.phone)
            return _make_answer(question, digits if digits else self._ctx.phone)
        return None

    def _handle_linkedin(self, question: Question) -> Answer | None:
        if self._ctx.linkedin_url:
            return Answer(
                question_id=question.id,
                type=AnswerType.LINK,
                value=self._ctx.linkedin_url,
                confidence=1.0,
                source="database",
            )
        return None

    def _handle_resume(self, question: Question) -> Answer | None:
        if self._ctx.resume_local_path:
            return Answer(
                question_id=question.id,
                type=AnswerType.FILE,
                value=self._ctx.resume_local_path,
                confidence=1.0,
                source="database",
            )
        return None

    def _handle_cover_letter(self, question: Question) -> Answer | None:
        if self._ctx.cover_letter_local_path:
            return Answer(
                question_id=question.id,
                type=AnswerType.FILE,
                value=self._ctx.cover_letter_local_path,
                confidence=1.0,
                source="database",
            )
        return None

    def _handle_work_authorization(self, question: Question) -> Answer | None:
        if self._ctx.work_authorization:
            return _make_answer(question, self._ctx.work_authorization)
        return None

    def _handle_citizenship(self, question: Question) -> Answer | None:
        if self._ctx.citizenship:
            return _make_answer(question, self._ctx.citizenship)
        return None

    def _handle_experience(self, question: Question) -> Answer | None:
        if self._ctx.years_of_experience is not None:
            return _make_answer(question, str(self._ctx.years_of_experience))
        return None

    def _handle_education(self, question: Question) -> Answer | None:
        if self._ctx.education_level:
            return _make_answer(question, self._ctx.education_level)
        return None

    def _handle_salary(self, question: Question) -> Answer | None:
        if self._ctx.min_salary is not None:
            return _make_answer(question, str(int(self._ctx.min_salary)))
        return None

    def _handle_availability(self, question: Question) -> Answer | None:
        if self._ctx.availability:
            return _make_answer(question, self._ctx.availability)
        return None

    def _handle_gender(self, question: Question) -> Answer | None:
        if self._ctx.gender:
            return _make_answer(question, self._ctx.gender)
        return None

    def _handle_veteran(self, question: Question) -> Answer | None:
        if self._ctx.veteran_status:
            return _make_answer(question, self._ctx.veteran_status)
        return None

    def _handle_disability(self, question: Question) -> Answer | None:
        if self._ctx.disability_status:
            return _make_answer(question, self._ctx.disability_status)
        return None

    def _handle_location(self, question: Question) -> Answer | None:
        location = self._ctx.location or self._ctx.target_location
        if location:
            return _make_answer(question, location)
        return None

    def _handle_country(self, question: Question) -> Answer | None:
        country = self._ctx.country or self._ctx.target_country
        if country:
            return _make_answer(question, country)
        return None
