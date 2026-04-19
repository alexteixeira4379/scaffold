from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class TrackingClick(CoreBase):
    __tablename__ = "tracking_clicks"
    __table_args__ = (
        UniqueConstraint("click_key"),
        Index("ix_tracking_clicks_track_code", "track_code"),
        Index("ix_tracking_clicks_session_id", "session_id"),
        Index("ix_tracking_clicks_candidate_id", "candidate_id"),
        Index("ix_tracking_clicks_fbclid", "fbclid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    track_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    click_key: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=True
    )
    full_url: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbclid: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbc: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbp: Mapped[str | None] = mapped_column(Text, nullable=True)
    pixel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    referer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
