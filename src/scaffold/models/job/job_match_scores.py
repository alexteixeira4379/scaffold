from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class JobMatchScore(CoreBase):
    __tablename__ = "job_match_scores"
    __table_args__ = (
        Index("ix_job_match_scores_job_match_id", "job_match_id"),
        UniqueConstraint("job_match_id", "dimension"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("job_matches.id"), nullable=False)
    dimension: Mapped[str] = mapped_column(String(128), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
