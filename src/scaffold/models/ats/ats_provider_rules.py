from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, SmallInteger, String, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class AtsProviderRule(CoreBase):
    __tablename__ = "ats_provider_rules"
    __table_args__ = (
        Index("ix_ats_provider_rules_ats_provider_id", "ats_provider_id"),
        UniqueConstraint("ats_provider_id", "rule_type", "rule_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ats_provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
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
