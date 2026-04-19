from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ApplicationStepStatus

_application_step_status = mysql_enum(ApplicationStepStatus, "application_step_status")


class ApplicationStep(CoreBase):
    __tablename__ = "application_steps"
    __table_args__ = (
        Index("ix_application_steps_application_run_id", "application_run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("application_runs.id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[ApplicationStepStatus] = mapped_column(
        _application_step_status,
        nullable=False,
        server_default=mysql_default("application_step_status", ApplicationStepStatus.PENDING),
    )
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
