from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ResumeSessionStatus, ResumeSessionType

_resume_session_type = mysql_enum(ResumeSessionType, "resume_session_type")
_resume_session_status = mysql_enum(ResumeSessionStatus, "resume_session_status")


class ResumeBuildSession(CoreBase):
    __tablename__ = "resume_build_sessions"
    __table_args__ = (
        Index("ix_resume_build_sessions_candidate_id", "candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    session_type: Mapped[ResumeSessionType] = mapped_column(
        _resume_session_type,
        nullable=False,
        server_default=mysql_default("resume_session_type", ResumeSessionType.BUILDER),
    )
    status: Mapped[ResumeSessionStatus] = mapped_column(
        _resume_session_status,
        nullable=False,
        server_default=mysql_default("resume_session_status", ResumeSessionStatus.STARTED),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
