from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import WorkflowSessionStatus

_workflow_session_status = mysql_enum(WorkflowSessionStatus, "workflow_session_status")


class BillingWorkflowSession(CoreBase):
    __tablename__ = "billing_workflow_sessions"
    __table_args__ = (
        Index("ix_billing_workflow_sessions_candidate_id", "candidate_id"),
        Index("ix_billing_workflow_sessions_candidate_workflow", "candidate_id", "workflow_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    workflow_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[WorkflowSessionStatus] = mapped_column(
        _workflow_session_status,
        nullable=False,
        server_default=mysql_default("workflow_session_status", WorkflowSessionStatus.STARTED),
    )
    current_step_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    session_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
