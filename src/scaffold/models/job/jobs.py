from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import EmploymentType, ExperienceLevel, JobStatus, RemoteType

_job_status = mysql_enum(JobStatus, "job_status")
_job_remote_type = mysql_enum(RemoteType, "job_remote_type")
_job_employment_type = mysql_enum(EmploymentType, "job_employment_type")
_job_experience_level = mysql_enum(ExperienceLevel, "job_experience_level")


class Job(CoreBase):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_company_id", "company_id"),
        Index("ix_jobs_job_discovery_source_id", "job_discovery_source_id"),
        Index("ix_jobs_ats_provider_id", "ats_provider_id"),
        UniqueConstraint(
            "job_discovery_source_id", "external_job_id", name="uq_jobs_source_external_id"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("companies.id"), nullable=True)
    job_discovery_source_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("job_discovery_sources.id"), nullable=True
    )
    ats_provider_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=True
    )
    external_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote_type: Mapped[RemoteType] = mapped_column(
        _job_remote_type,
        nullable=False,
        server_default=mysql_default("job_remote_type", RemoteType.UNKNOWN),
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        _job_employment_type,
        nullable=False,
        server_default=mysql_default("job_employment_type", EmploymentType.UNKNOWN),
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        _job_experience_level,
        nullable=False,
        server_default=mysql_default("job_experience_level", ExperienceLevel.UNKNOWN),
    )
    salary_min: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        _job_status,
        nullable=False,
        server_default=mysql_default("job_status", JobStatus.ACTIVE),
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    company_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_domain_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
