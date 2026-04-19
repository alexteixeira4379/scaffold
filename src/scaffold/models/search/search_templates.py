from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class SearchTemplate(CoreBase):
    __tablename__ = "search_templates"
    __table_args__ = (
        Index("ix_search_templates_job_discovery_source_id", "job_discovery_source_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_discovery_source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_discovery_sources.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    search_term: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    search_filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
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
