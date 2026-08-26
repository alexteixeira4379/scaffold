"""Candidate application data

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_application_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("work_authorization", sa.String(length=100), nullable=True),
        sa.Column("citizenship", sa.String(length=100), nullable=True),
        sa.Column("education_level", sa.String(length=100), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("availability", sa.String(length=50), nullable=True),
        sa.Column("gender", sa.String(length=50), nullable=True),
        sa.Column("veteran_status", sa.String(length=50), nullable=True),
        sa.Column("disability_status", sa.String(length=50), nullable=True),
        sa.Column("custom_answers", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_candidate_application_data_candidate_id_candidates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_application_data")),
        sa.UniqueConstraint(
            "candidate_id", name="uq_candidate_application_data_candidate_id"
        ),
    )
    op.create_index(
        "ix_candidate_application_data_candidate_id",
        "candidate_application_data",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_application_data_candidate_id", "candidate_application_data"
    )
    op.drop_table("candidate_application_data")
