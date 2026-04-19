from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class CandidateTargetProfileKeyword(CoreBase):
    __tablename__ = "candidate_target_profile_keywords"
    __table_args__ = (
        UniqueConstraint(
            "candidate_target_profile_id",
            "keyword",
            "match_policy",
            name="uq_candidate_target_profile_keywords_profile_keyword_policy",
        ),
        Index("ix_candidate_target_profile_keywords_candidate_target_profile_id", "candidate_target_profile_id"),
        Index("ix_candidate_target_profile_keywords_keyword", "keyword"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_target_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidate_target_profiles.id"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    match_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
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
