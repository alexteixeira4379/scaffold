from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import EmploymentType, ExperienceLevel, RemoteType

_job_remote_type = mysql_enum(RemoteType, "job_remote_type")
_job_employment_type = mysql_enum(EmploymentType, "job_employment_type")
_job_experience_level = mysql_enum(ExperienceLevel, "job_experience_level")


class CandidateTargetProfile(CoreBase):
    __tablename__ = "candidate_target_profiles"
    __table_args__ = (
        Index("ix_candidate_target_profiles_candidate_active", "candidate_id", "active"),
        Index("ix_candidate_target_profiles_candidate_is_default", "candidate_id", "is_default"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    target_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote_preference: Mapped[RemoteType] = mapped_column(
        _job_remote_type,
        nullable=False,
        server_default=mysql_default("job_remote_type", RemoteType.UNKNOWN),
    )
    employment_preference: Mapped[EmploymentType] = mapped_column(
        _job_employment_type,
        nullable=False,
        server_default=mysql_default("job_employment_type", EmploymentType.UNKNOWN),
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        _job_experience_level,
        nullable=False,
        server_default=mysql_default("job_experience_level", ExperienceLevel.UNKNOWN),
    )
    min_salary: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
