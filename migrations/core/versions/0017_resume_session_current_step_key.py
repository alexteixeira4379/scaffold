"""Add current_step_key to resume_build_sessions (step_key-driven workflow)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-04

Adds a nullable current_step_key column to resume_build_sessions so the
resume-api can persist the resolved current step of a build session using
step_key (the single stable key of the workflow). The step is guarded by an
existence check so the migration is safe to re-run after a partial failure.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "resume_build_sessions"
_COLUMN = "current_step_key"


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, _TABLE, _COLUMN):
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, _TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
