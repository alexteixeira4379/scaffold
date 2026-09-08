"""Backfill professional_entities columns missing on older-created tables.

The table was originally created (revision 0011) before the model gained
``language``, ``description`` and ``metadata``. Databases created from that
earlier revision never received those columns, so the classifier query
(SELECT ... professional_entities.language ...) fails with
"Unknown column 'professional_entities.language'". This migration adds the
columns only when absent, so it is a no-op where 0011 already created them.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "professional_entities"
# name -> column definition
_COLUMNS = {
    "language": sa.Column("language", sa.String(16), nullable=True),
    "description": sa.Column("description", sa.Text(), nullable=True),
    "metadata": sa.Column("metadata", sa.JSON(), nullable=True),
}


def _existing_columns(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind)
    for name, column in _COLUMNS.items():
        if name not in existing:
            op.add_column(_TABLE, column)

    # Ensure the (entity_type, normalized_name, language) uniqueness the model
    # declares. Only create it if a unique constraint on those columns is not
    # already present, to stay idempotent.
    inspector = sa.inspect(bind)
    uniques = inspector.get_unique_constraints(_TABLE)
    have_triple = any(
        set(uc.get("column_names") or []) == {"entity_type", "normalized_name", "language"}
        for uc in uniques
    )
    if not have_triple and "language" in _existing_columns(bind):
        try:
            op.create_unique_constraint(
                "uq_professional_entities_entity_type",
                _TABLE,
                ["entity_type", "normalized_name", "language"],
            )
        except Exception:
            # A differently-named equivalent constraint may already exist; the
            # column backfill above is the critical part, so don't hard-fail.
            pass


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind)
    for name in ("metadata", "description", "language"):
        if name in existing:
            op.drop_column(_TABLE, name)
