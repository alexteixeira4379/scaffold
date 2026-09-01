"""Add stripe_price_id to billing_plans

Revision ID: 0015
Revises: 57861de8b338
Create Date: 2026-08-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "57861de8b338"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "billing_plans",
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_plans", "stripe_price_id")
