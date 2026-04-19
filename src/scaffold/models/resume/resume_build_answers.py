from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ResumeBuildAnswer(CoreBase):
    __tablename__ = "resume_build_answers"
    __table_args__ = (
        UniqueConstraint("session_id", "step_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resume_build_sessions.id"), nullable=False
    )
    step_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resume_build_steps.id"), nullable=False
    )
    answer_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
