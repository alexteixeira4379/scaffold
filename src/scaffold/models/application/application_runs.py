from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ApplicationRunStatus

_application_run_status = mysql_enum(ApplicationRunStatus, "application_run_status")


class ApplicationRun(CoreBase):
    __tablename__ = "application_runs"
    __table_args__ = (
        Index("ix_application_runs_job_application_id", "job_application_id"),
        Index("ix_application_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_application_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_applications.id"), nullable=False
    )
    status: Mapped[ApplicationRunStatus] = mapped_column(
        _application_run_status,
        nullable=False,
        server_default=mysql_default("application_run_status", ApplicationRunStatus.PENDING),
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
