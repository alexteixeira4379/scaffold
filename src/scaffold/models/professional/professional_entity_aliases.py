from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ProfessionalEntityAlias(CoreBase):
    __tablename__ = "professional_entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "normalized_alias", "language", "source"),
        Index("ix_professional_entity_aliases_entity_id", "entity_id"),
        Index("ix_professional_entity_aliases_normalized_alias", "normalized_alias"),
        Index("ix_professional_entity_aliases_source", "source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
