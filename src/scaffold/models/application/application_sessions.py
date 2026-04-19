from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ApplicationSession(CoreBase):
    __tablename__ = "application_sessions"
    __table_args__ = (
        Index("ix_application_sessions_candidate_id", "candidate_id"),
        Index("ix_application_sessions_ats_provider_id", "ats_provider_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    ats_provider_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=True
    )
    platform_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
