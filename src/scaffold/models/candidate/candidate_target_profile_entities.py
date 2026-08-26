from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class CandidateTargetProfileEntity(CoreBase):
    __tablename__ = "candidate_target_profile_entities"
    __table_args__ = (
        UniqueConstraint(
            "candidate_target_profile_id",
            "professional_entity_id",
            name="uq_candidate_target_profile_entities_profile_entity",
        ),
        Index("ix_candidate_target_profile_entities_candidate_target_profile_id", "candidate_target_profile_id"),
        Index("ix_candidate_target_profile_entities_professional_entity_id", "professional_entity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_target_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidate_target_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    professional_entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("professional_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relevance: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    matched_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
