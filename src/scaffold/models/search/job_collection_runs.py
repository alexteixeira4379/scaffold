from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import SearchRunStatus

_search_run_status = mysql_enum(SearchRunStatus, "search_run_status")


class JobCollectionRun(CoreBase):
    __tablename__ = "job_collection_runs"
    __table_args__ = (
        Index("ix_job_collection_runs_job_collection_definition_id", "job_collection_definition_id"),
        Index("ix_job_collection_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_collection_definition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_collection_definitions.id"), nullable=False
    )
    status: Mapped[SearchRunStatus] = mapped_column(
        _search_run_status,
        nullable=False,
        server_default=mysql_default("search_run_status", SearchRunStatus.PENDING),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jobs_found_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    jobs_new_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    jobs_updated_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
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
