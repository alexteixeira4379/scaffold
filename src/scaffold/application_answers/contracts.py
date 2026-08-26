"""Contracts for the universal application answers engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class AnswerType(StrEnum):
    TEXT = "text"
    OPTION = "option"
    FILE = "file"
    BOOLEAN = "boolean"
    LINK = "link"
    SKIP = "skip"


@runtime_checkable
class StoragePort(Protocol):
    """Minimal interface for file storage (download).

    Compatible with scaffold.storage.StorageClient: get() returns
    a StoredObjectBody (with a .body: bytes attribute) or None.
    """

    async def get(self, key: str) -> object | None: ...


@dataclass
class QuestionOption:
    label: str
    value: str


@dataclass
class Question:
    id: str
    question: str
    question_complement: str | None = None
    is_required: bool = False
    options: list[QuestionOption] | None = None
    current_value: str | None = None


@dataclass
class Answer:
    question_id: str
    type: AnswerType
    value: str
    confidence: float = 1.0
    source: str = "unknown"


@dataclass
class CandidateContext:
    """Loaded candidate data for answering questions."""

    candidate_id: int
    full_name: str = ""
    email: str = ""
    phone: str | None = None
    country: str | None = None
    location: str | None = None
    linkedin_url: str | None = None

    # From candidate_preferences
    target_country: str | None = None
    target_location: str | None = None
    min_salary: float | None = None
    currency: str | None = None

    # From candidate_application_data
    years_of_experience: int | None = None
    work_authorization: str | None = None
    citizenship: str | None = None
    education_level: str | None = None
    languages: list[str] = field(default_factory=list)
    availability: str | None = None
    gender: str | None = None
    veteran_status: str | None = None
    disability_status: str | None = None
    custom_answers: dict[str, str] = field(default_factory=dict)

    # File paths (downloaded locally)
    resume_local_path: str | None = None
    cover_letter_local_path: str | None = None
