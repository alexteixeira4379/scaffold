from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class JobCandidateEligibility(CoreBase):
    __tablename__ = "job_candidate_eligibilities"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "candidate_id",
            "candidate_target_profile_id",
            name="uq_job_candidate_eligibilities_job_candidate_profile",
        ),
        Index("ix_job_candidate_eligibilities_job_id", "job_id"),
        Index("ix_job_candidate_eligibilities_candidate_id", "candidate_id"),
        Index("ix_job_candidate_eligibilities_candidate_target_profile_id", "candidate_target_profile_id"),
        Index("ix_job_candidate_eligibilities_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    candidate_target_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidate_target_profiles.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="pending")
    routing_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    routing_reason: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
