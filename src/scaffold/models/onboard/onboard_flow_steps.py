from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import OrchestratorStepKind

_orchestrator_step_kind = mysql_enum(OrchestratorStepKind, "orchestrator_step_kind")


class OnboardFlowStep(CoreBase):
    __tablename__ = "onboard_flow_steps"
    __table_args__ = (
        UniqueConstraint("flow_id", "step_key"),
        Index("ix_onboard_flow_steps_flow_id", "flow_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("onboard_flows.id"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    kind: Mapped[OrchestratorStepKind] = mapped_column(
        _orchestrator_step_kind,
        nullable=False,
        server_default=mysql_default("orchestrator_step_kind", OrchestratorStepKind.QUESTION),
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
