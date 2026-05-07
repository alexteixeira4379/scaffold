from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ProfessionalEntityRelation(CoreBase):
    __tablename__ = "professional_entity_relations"
    __table_args__ = (
        UniqueConstraint("source_entity_id", "target_entity_id", "relation_type", "source"),
        Index("ix_professional_entity_relations_source_entity", "source_entity_id"),
        Index("ix_professional_entity_relations_target_entity", "target_entity_id"),
        Index("ix_professional_entity_relations_type", "relation_type"),
        Index("ix_professional_entity_relations_source", "source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    relation_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
