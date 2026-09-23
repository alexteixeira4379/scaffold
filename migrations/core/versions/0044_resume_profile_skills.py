"""Add skills column to resume_profiles.

Revision ID: 0044
Revises: 0043
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_TABLE = "resume_profiles"


def _existing_columns(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if "skills" not in _existing_columns(bind):
        op.add_column(_TABLE, sa.Column("skills", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if "skills" in _existing_columns(bind):
        op.drop_column(_TABLE, "skills")
