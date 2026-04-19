from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import BillingPaymentStatus

_billing_payment_status = mysql_enum(BillingPaymentStatus, "billing_payment_status")


class BillingPayment(CoreBase):
    __tablename__ = "billing_payments"
    __table_args__ = (
        Index("ix_billing_payments_billing_customer_id", "billing_customer_id"),
        Index("ix_billing_payments_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    billing_customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("billing_customers.id"), nullable=False
    )
    billing_subscription_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("billing_subscriptions.id"), nullable=True
    )
    external_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[BillingPaymentStatus] = mapped_column(
        _billing_payment_status,
        nullable=False,
        server_default=mysql_default("billing_payment_status", BillingPaymentStatus.PENDING),
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
