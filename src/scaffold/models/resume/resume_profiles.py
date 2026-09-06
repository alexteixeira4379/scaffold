from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ResumeProfileSource
from scaffold.db.types import mysql_enum

_resume_profile_source = mysql_enum(ResumeProfileSource, "resume_profile_source")


class ResumeProfile(CoreBase):
    __tablename__ = "resume_profiles"
    __table_args__ = (UniqueConstraint("candidate_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    source: Mapped[ResumeProfileSource] = mapped_column(_resume_profile_source, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

