"""Add repeat_index to resume_build_answers (repeat_for support)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_build_answers",
        sa.Column("repeat_index", sa.Integer(), nullable=True),
    )
    op.drop_constraint(
        "uq_resume_build_answers_session_id", "resume_build_answers", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_resume_build_answers_session_id"),
        "resume_build_answers",
        ["session_id", "step_id", "repeat_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_resume_build_answers_session_id", "resume_build_answers", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_resume_build_answers_session_id"),
        "resume_build_answers",
        ["session_id", "step_id"],
    )
    op.drop_column("resume_build_answers", "repeat_index")
