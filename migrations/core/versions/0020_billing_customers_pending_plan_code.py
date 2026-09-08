"""Add pending_plan_code to billing_customers

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "billing_customers",
        sa.Column("pending_plan_code", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_customers", "pending_plan_code")
