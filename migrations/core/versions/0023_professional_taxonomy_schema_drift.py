"""Reconcile professional-taxonomy schema drift with the models.

Several taxonomy tables were created (revision 0011) before their models
gained additional columns; the 0011 file was later edited in place, so
databases that already had 0011 applied never received the new columns/table.
This caused runtime "Unknown column ..." errors in the matching/classifier
paths (e.g. job_professional_entities.matched_text).

This migration is fully idempotent: it inspects the live schema and only
creates the table / adds the columns that are actually missing. All added
columns carry a safe server_default so it is valid even on populated tables
(these tables are empty in production today).

Missing (audited against production):
  - table: professional_collections
  - job_professional_entities: matched_text, weight, extraction_method
  - professional_collection_memberships: collection_id
  - professional_entity_aliases: language, source
  - professional_entity_hierarchy_relations: depth, relation_type, source
  - professional_entity_relations: metadata, source, weight
  - professional_entity_sources: external_source_id, external_source_uri,
        metadata, source, source_label

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# table -> { column_name: sa.Column(...) }. Columns are added only if absent.
# NOT NULL columns include a server_default so the ADD is safe on any row.
_MISSING_COLUMNS: dict[str, dict[str, sa.Column]] = {
    "job_professional_entities": {
        "matched_text": sa.Column("matched_text", sa.String(512), nullable=False, server_default=""),
        "weight": sa.Column("weight", sa.Numeric(6, 2), nullable=False, server_default="0"),
        "extraction_method": sa.Column("extraction_method", sa.String(64), nullable=False, server_default="unknown"),
    },
    "professional_collection_memberships": {
        "collection_id": sa.Column("collection_id", sa.BigInteger(), nullable=False, server_default="0"),
    },
    "professional_entity_aliases": {
        "language": sa.Column("language", sa.String(16), nullable=True),
        "source": sa.Column("source", sa.String(64), nullable=False, server_default="unknown"),
    },
    "professional_entity_hierarchy_relations": {
        "depth": sa.Column("depth", sa.Integer(), nullable=False, server_default="1"),
        "relation_type": sa.Column("relation_type", sa.String(64), nullable=False, server_default="unknown"),
        "source": sa.Column("source", sa.String(64), nullable=False, server_default="unknown"),
    },
    "professional_entity_relations": {
        "metadata": sa.Column("metadata", sa.JSON(), nullable=True),
        "source": sa.Column("source", sa.String(64), nullable=False, server_default="unknown"),
        "weight": sa.Column("weight", sa.Numeric(8, 4), nullable=True),
    },
    "professional_entity_sources": {
        "external_source_id": sa.Column("external_source_id", sa.String(255), nullable=True),
        "external_source_uri": sa.Column("external_source_uri", sa.Text(), nullable=True),
        "source_label": sa.Column("source_label", sa.Text(), nullable=True),
        "metadata": sa.Column("metadata", sa.JSON(), nullable=True),
        "source": sa.Column("source", sa.String(64), nullable=False, server_default="unknown"),
    },
}


def _existing_tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _existing_columns(bind, table: str) -> set[str]:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _existing_tables(bind)

    # 1. Missing table: professional_collections.
    if "professional_collections" not in tables:
        op.create_table(
            "professional_collections",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("slug", sa.String(128), nullable=False),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.UniqueConstraint("slug", name=op.f("uq_professional_collections_slug")),
        )

    # 2. Missing columns per table.
    for table, columns in _MISSING_COLUMNS.items():
        if table not in _existing_tables(bind):
            # Table itself absent (unexpected) — skip; a full create belongs elsewhere.
            continue
        existing = _existing_columns(bind, table)
        for name, column in columns.items():
            if name not in existing:
                op.add_column(table, column)


def downgrade() -> None:
    bind = op.get_bind()
    for table, columns in _MISSING_COLUMNS.items():
        existing = _existing_columns(bind, table)
        for name in columns:
            if name in existing:
                op.drop_column(table, name)
    if "professional_collections" in _existing_tables(bind):
        op.drop_table("professional_collections")
