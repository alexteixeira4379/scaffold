from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import EmploymentType, ExperienceLevel, RemoteType

_job_remote_type = mysql_enum(RemoteType, "job_remote_type")
_job_employment_type = mysql_enum(EmploymentType, "job_employment_type")
_job_experience_level = mysql_enum(ExperienceLevel, "job_experience_level")


class CandidatePreference(CoreBase):
    __tablename__ = "candidate_preferences"
    __table_args__ = (
        UniqueConstraint("candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
