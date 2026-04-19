from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_enum
from scaffold.constants.schema_enums import ApplicationFailureType

_application_failure_type = mysql_enum(ApplicationFailureType, "application_failure_type")


class ApplicationFailure(CoreBase):
    __tablename__ = "application_failures"
    __table_args__ = (
        Index("ix_application_failures_job_application_id", "job_application_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_application_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_applications.id"), nullable=False
    )
    application_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("application_runs.id"), nullable=True
    )
    failure_type: Mapped[ApplicationFailureType] = mapped_column(
        _application_failure_type, nullable=False
    )
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
