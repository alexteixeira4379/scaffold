from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, func, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class AtsProviderSchedule(CoreBase):
    __tablename__ = "ats_provider_schedules"
    __table_args__ = (UniqueConstraint("ats_provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ats_provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=False
    )
    interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3600"
    )
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
