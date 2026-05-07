from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ProfessionalEntitySource(CoreBase):
    __tablename__ = "professional_entity_sources"
    __table_args__ = (
        # In MySQL, UNIQUE on nullable column allows multiple NULLs for external_source_id
        UniqueConstraint("source", "external_source_id"),
        Index("ix_professional_entity_sources_entity_id", "entity_id"),
        Index("ix_professional_entity_sources_source", "source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
