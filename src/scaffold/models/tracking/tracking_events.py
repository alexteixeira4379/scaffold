from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class TrackingEvent(CoreBase):
    __tablename__ = "tracking_events"
    __table_args__ = (
        Index("ix_tracking_events_session_id", "session_id"),
        Index("ix_tracking_events_candidate_id", "candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=True
    )
    tracking_click_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tracking_clicks.id"), nullable=True
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
