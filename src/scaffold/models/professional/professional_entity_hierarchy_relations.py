from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ProfessionalEntityHierarchyRelation(CoreBase):
    __tablename__ = "professional_entity_hierarchy_relations"
    __table_args__ = (
        UniqueConstraint("child_entity_id", "parent_entity_id", "relation_type", "source"),
        Index("ix_professional_entity_hierarchy_child", "child_entity_id"),
        Index("ix_professional_entity_hierarchy_parent", "parent_entity_id"),
        Index("ix_professional_entity_hierarchy_type", "relation_type"),
        Index("ix_professional_entity_hierarchy_source", "source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    child_entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    parent_entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("professional_entities.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
