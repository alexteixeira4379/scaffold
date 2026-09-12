from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import OrchestratorStepStatus

_orchestrator_step_status = mysql_enum(OrchestratorStepStatus, "orchestrator_step_status")


class ProfileOnboardStepState(CoreBase):
    __tablename__ = "profile_onboard_step_states"
    __table_args__ = (
        UniqueConstraint("profile_flow_id", "step_key"),
        Index("ix_profile_onboard_step_states_profile_flow_id", "profile_flow_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_flow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profile_onboard_flows.id"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[OrchestratorStepStatus] = mapped_column(
        _orchestrator_step_status,
        nullable=False,
        server_default=mysql_default("orchestrator_step_status", OrchestratorStepStatus.PENDING),
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Points at a domain-owned workflow session (e.g. a candidate_workflow_sessions
    # row) when kind == api_workflow; intentionally not a FK — cross-domain link.
    api_session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    local_answer: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
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
