"""Billing domain

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import BillingPaymentStatus, BillingSubscriptionStatus
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_billing_subscription_status = mysql_enum(BillingSubscriptionStatus, "billing_subscription_status")
_billing_payment_status = mysql_enum(BillingPaymentStatus, "billing_payment_status")


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("interval", sa.Text(), nullable=True),
        sa.Column("interval_count", sa.Integer(), nullable=True),
        sa.Column("features", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_plans")),
        sa.UniqueConstraint("code", name=op.f("uq_billing_plans_code")),
    )

    op.create_table(
        "billing_customers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("external_customer_id", sa.String(255), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_billing_customers_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_customers")),
        sa.UniqueConstraint("candidate_id", name=op.f("uq_billing_customers_candidate_id")),
    )
    op.create_index("ix_billing_customers_external_customer_id", "billing_customers", ["external_customer_id"])

    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("billing_customer_id", sa.BigInteger(), nullable=False),
        sa.Column("billing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("external_subscription_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            _billing_subscription_status,
            server_default=mysql_default(
                "billing_subscription_status", BillingSubscriptionStatus.ACTIVE
            ),
            nullable=False,
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["billing_customer_id"], ["billing_customers.id"], name=op.f("fk_billing_subscriptions_billing_customer_id_billing_customers")),
        sa.ForeignKeyConstraint(["billing_plan_id"], ["billing_plans.id"], name=op.f("fk_billing_subscriptions_billing_plan_id_billing_plans")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_subscriptions")),
    )
    op.create_index("ix_billing_subscriptions_billing_customer_id", "billing_subscriptions", ["billing_customer_id"])
    op.create_index("ix_billing_subscriptions_status", "billing_subscriptions", ["status"])

    op.create_table(
        "billing_payments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("billing_customer_id", sa.BigInteger(), nullable=False),
        sa.Column("billing_subscription_id", sa.BigInteger(), nullable=True),
        sa.Column("external_payment_id", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column(
            "status",
            _billing_payment_status,
            server_default=mysql_default("billing_payment_status", BillingPaymentStatus.PENDING),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("payment_metadata", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["billing_customer_id"], ["billing_customers.id"], name=op.f("fk_billing_payments_billing_customer_id_billing_customers")),
        sa.ForeignKeyConstraint(["billing_subscription_id"], ["billing_subscriptions.id"], name=op.f("fk_billing_payments_billing_subscription_id_billing_subscriptions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_payments")),
    )
    op.create_index("ix_billing_payments_billing_customer_id", "billing_payments", ["billing_customer_id"])
    op.create_index("ix_billing_payments_status", "billing_payments", ["status"])

    op.create_table(
        "billing_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("billing_customer_id", sa.BigInteger(), nullable=True),
        sa.Column("billing_subscription_id", sa.BigInteger(), nullable=True),
        sa.Column("billing_payment_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["billing_customer_id"], ["billing_customers.id"], name=op.f("fk_billing_events_billing_customer_id_billing_customers")),
        sa.ForeignKeyConstraint(["billing_payment_id"], ["billing_payments.id"], name=op.f("fk_billing_events_billing_payment_id_billing_payments")),
        sa.ForeignKeyConstraint(["billing_subscription_id"], ["billing_subscriptions.id"], name=op.f("fk_billing_events_billing_subscription_id_billing_subscriptions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_events")),
    )
    op.create_index("ix_billing_events_billing_customer_id", "billing_events", ["billing_customer_id"])


def downgrade() -> None:
    op.drop_table("billing_events")
    op.drop_table("billing_payments")
    op.drop_table("billing_subscriptions")
    op.drop_table("billing_customers")
    op.drop_table("billing_plans")
