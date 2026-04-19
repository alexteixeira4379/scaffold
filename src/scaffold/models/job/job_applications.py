from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ApplyMode, JobApplicationStatus

_job_application_status = mysql_enum(JobApplicationStatus, "job_application_status")
_job_apply_mode = mysql_enum(ApplyMode, "job_apply_mode")


class JobApplication(CoreBase):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("job_match_id"),
        Index("ix_job_applications_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("job_matches.id"), nullable=False)
    status: Mapped[JobApplicationStatus] = mapped_column(
        _job_application_status,
        nullable=False,
        server_default=mysql_default("job_application_status", JobApplicationStatus.PENDING),
    )
    apply_mode: Mapped[ApplyMode] = mapped_column(
        _job_apply_mode,
        nullable=False,
        server_default=mysql_default("job_apply_mode", ApplyMode.AUTO),
    )
    easy_apply: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    prepared: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    process_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_url_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_title_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
