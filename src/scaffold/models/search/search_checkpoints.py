from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class SearchCheckpoint(CoreBase):
    __tablename__ = "search_checkpoints"
    __table_args__ = (
        Index("ix_search_checkpoints_search_definition_id", "search_definition_id"),
        UniqueConstraint("search_definition_id", "checkpoint_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    search_definition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("search_definitions.id"), nullable=False
    )
    search_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("search_runs.id"), nullable=True
    )
    checkpoint_key: Mapped[str] = mapped_column(String(512), nullable=False)
    checkpoint_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
