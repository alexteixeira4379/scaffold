"""Application entitlements — tracks candidate auto-apply quota.

This table is maintained by billing-worker as a projection and read by application-worker.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ApplicationEntitlement(CoreBase):
    __tablename__ = "application_entitlements"
    __table_args__ = (
        Index("ix_application_entitlements_candidate_id", "candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=False
    )
    can_auto_apply: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    applications_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    applications_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
