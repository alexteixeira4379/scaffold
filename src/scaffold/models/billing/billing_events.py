from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class BillingEvent(CoreBase):
    __tablename__ = "billing_events"
    __table_args__ = (
        Index("ix_billing_events_billing_customer_id", "billing_customer_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    billing_customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("billing_customers.id"), nullable=True
    )
    billing_subscription_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("billing_subscriptions.id"), nullable=True
    )
    billing_payment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("billing_payments.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    external_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
