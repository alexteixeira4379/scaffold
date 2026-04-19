from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import CandidateStatus, LanguagePreference

_candidate_status = mysql_enum(CandidateStatus, "candidate_status")
_candidate_language = mysql_enum(LanguagePreference, "candidate_language_preference")


class Candidate(CoreBase):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("uq_candidates_email_lower", sa_text("lower(email)"), unique=True),
        Index("ix_candidates_status", "status"),
        Index("ix_candidates_track_code", "track_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_preference: Mapped[LanguagePreference] = mapped_column(
        _candidate_language,
        nullable=False,
        server_default=mysql_default("candidate_language_preference", LanguagePreference.PT_BR),
    )
    status: Mapped[CandidateStatus] = mapped_column(
        _candidate_status,
        nullable=False,
        server_default=mysql_default("candidate_status", CandidateStatus.PENDING),
    )
    generated_token: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    track_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
