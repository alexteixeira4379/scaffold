from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ResumeStepInputType

_workflow_step_input_type = mysql_enum(ResumeStepInputType, "workflow_step_input_type")


class BillingWorkflowStep(CoreBase):
    __tablename__ = "billing_workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_key", "step_key"),
        Index("ix_billing_workflow_steps_workflow_key", "workflow_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_key: Mapped[str] = mapped_column(String(128), nullable=False)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_type: Mapped[ResumeStepInputType] = mapped_column(
        _workflow_step_input_type,
        nullable=False,
        server_default=mysql_default("workflow_step_input_type", ResumeStepInputType.TEXT),
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
