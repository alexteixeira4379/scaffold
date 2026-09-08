"""Add Stripe sync columns to billing_plans; fix billing_subscriptions default

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import BillingSubscriptionStatus
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_billing_subscription_status = mysql_enum(BillingSubscriptionStatus, "billing_subscription_status")


def upgrade() -> None:
    op.add_column(
        "billing_plans",
        sa.Column("stripe_product_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "billing_plans",
        sa.Column("stripe_price_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "billing_plans",
        sa.Column("stripe_price_type", sa.String(32), nullable=True),
    )
    op.alter_column(
        "billing_subscriptions",
        "status",
        existing_type=_billing_subscription_status,
        server_default=mysql_default(
            "billing_subscription_status", BillingSubscriptionStatus.INCOMPLETE
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "billing_subscriptions",
        "status",
        existing_type=_billing_subscription_status,
        server_default=mysql_default(
            "billing_subscription_status", BillingSubscriptionStatus.ACTIVE
        ),
        existing_nullable=False,
    )
    op.drop_column("billing_plans", "stripe_price_type")
    op.drop_column("billing_plans", "stripe_price_created_at")
    op.drop_column("billing_plans", "stripe_product_id")
