from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class JobRoutingKeyword(CoreBase):
    __tablename__ = "job_routing_keywords"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "keyword",
            "keyword_source",
            name="uq_job_routing_keywords_job_keyword_source",
        ),
        Index("ix_job_routing_keywords_job_id", "job_id"),
        Index("ix_job_routing_keywords_keyword", "keyword"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    keyword_source: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
