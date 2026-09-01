from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ResumeBuildAnswer(CoreBase):
    __tablename__ = "resume_build_answers"
    __table_args__ = (
        # NULL repeat_index (the common case: a non-repeated step) is not
        # deduplicated by this constraint alone (NULL != NULL in SQL) —
        # submit_answer() still does an explicit lookup-before-insert, same
        # as it always has, so this is a backstop, not the sole guarantee.
        UniqueConstraint("session_id", "step_id", "repeat_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resume_build_sessions.id"), nullable=False
    )
    step_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resume_build_steps.id"), nullable=False
    )
    # Set only for steps expanded from a `repeat_for` config (e.g. one
    # "previous company details" instance per company) — NULL for regular,
    # non-repeated steps. See ResumeFlowService._expand_repeated_steps.
    repeat_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
