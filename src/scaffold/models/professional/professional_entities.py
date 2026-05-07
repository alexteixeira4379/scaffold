from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ProfessionalEntityType
from scaffold.db.types import mysql_enum

_entity_type = mysql_enum(ProfessionalEntityType, "professional_entity_type")


class ProfessionalEntity(CoreBase):
    __tablename__ = "professional_entities"
    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_name", "language"),
        Index("ix_professional_entities_type", "entity_type"),
        Index("ix_professional_entities_normalized_name", "normalized_name"),
        Index("ix_professional_entities_active", "active"),
        Index("ix_professional_entities_type_name", "entity_type", "normalized_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[ProfessionalEntityType] = mapped_column(_entity_type, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
