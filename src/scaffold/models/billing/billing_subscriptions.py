from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import BillingSubscriptionStatus

_billing_subscription_status = mysql_enum(BillingSubscriptionStatus, "billing_subscription_status")


class BillingSubscription(CoreBase):
    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        Index("ix_billing_subscriptions_billing_customer_id", "billing_customer_id"),
        Index("ix_billing_subscriptions_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    billing_customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("billing_customers.id"), nullable=False
    )
    billing_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("billing_plans.id"), nullable=False
    )
    external_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BillingSubscriptionStatus] = mapped_column(
        _billing_subscription_status,
        nullable=False,
        server_default=mysql_default(
            "billing_subscription_status", BillingSubscriptionStatus.ACTIVE
        ),
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
