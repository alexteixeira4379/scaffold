from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ProfessionalCollectionMembership(CoreBase):
    __tablename__ = "professional_collection_memberships"
    __table_args__ = (
        UniqueConstraint("collection_id", "entity_id"),
        Index("ix_professional_collection_memberships_collection", "collection_id"),
        Index("ix_professional_collection_memberships_entity", "entity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_collections.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
