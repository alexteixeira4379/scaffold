from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class BillingWorkflowAnswer(CoreBase):
    __tablename__ = "billing_workflow_answers"
    __table_args__ = (
        UniqueConstraint("session_id", "step_id", "repeat_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("billing_workflow_sessions.id"), nullable=False
    )
    step_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("billing_workflow_steps.id"), nullable=False
    )
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
