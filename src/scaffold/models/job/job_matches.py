from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import JobMatchStatus

_job_match_status = mysql_enum(JobMatchStatus, "job_match_status")


class JobMatch(CoreBase):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id"),
        Index("ix_job_matches_score", "score"),
        Index("ix_job_matches_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[JobMatchStatus] = mapped_column(
        _job_match_status,
        nullable=False,
        server_default=mysql_default("job_match_status", JobMatchStatus.PENDING),
    )
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
