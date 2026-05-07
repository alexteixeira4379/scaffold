"""Professional taxonomy domain

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENTITY_TYPE_ENUM = sa.Enum(
    "skill",
    "technology",
    "tool",
    "methodology",
    "certification",
    "language",
    "job_title",
    "occupation",
    "domain",
    name="professional_entity_type",
    native_enum=True,
)


def upgrade() -> None:
    op.create_table(
        "professional_entities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_type", _ENTITY_TYPE_ENUM, nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.String(512), nullable=False),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_entities")),
        sa.UniqueConstraint("entity_type", "normalized_name", "language", name=op.f("uq_professional_entities_entity_type")),
    )
    op.create_index("ix_professional_entities_type", "professional_entities", ["entity_type"])
    op.create_index("ix_professional_entities_normalized_name", "professional_entities", ["normalized_name"])
    op.create_index("ix_professional_entities_active", "professional_entities", ["active"])
    op.create_index("ix_professional_entities_type_name", "professional_entities", ["entity_type", "normalized_name"])

    op.create_table(
        "professional_entity_aliases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.String(512), nullable=False),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_entity_aliases_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_entity_aliases")),
        sa.UniqueConstraint("entity_id", "normalized_alias", "language", "source", name=op.f("uq_professional_entity_aliases_entity_id")),
    )
    op.create_index("ix_professional_entity_aliases_entity_id", "professional_entity_aliases", ["entity_id"])
    op.create_index("ix_professional_entity_aliases_normalized_alias", "professional_entity_aliases", ["normalized_alias"])
    op.create_index("ix_professional_entity_aliases_source", "professional_entity_aliases", ["source"])

    op.create_table(
        "professional_entity_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_source_id", sa.String(255), nullable=True),
        sa.Column("external_source_uri", sa.Text(), nullable=True),
        sa.Column("source_label", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_entity_sources_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_entity_sources")),
        # In MySQL, UNIQUE on (source, external_source_id) allows multiple NULLs in external_source_id
        sa.UniqueConstraint("source", "external_source_id", name=op.f("uq_professional_entity_sources_source")),
    )
    op.create_index("ix_professional_entity_sources_entity_id", "professional_entity_sources", ["entity_id"])
    op.create_index("ix_professional_entity_sources_source", "professional_entity_sources", ["source"])

    op.create_table(
        "professional_entity_relations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("target_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_entity_relations_source_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_entity_relations_target_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_entity_relations")),
        sa.UniqueConstraint("source_entity_id", "target_entity_id", "relation_type", "source", name=op.f("uq_professional_entity_relations_source_entity_id")),
    )
    op.create_index("ix_professional_entity_relations_source_entity", "professional_entity_relations", ["source_entity_id"])
    op.create_index("ix_professional_entity_relations_target_entity", "professional_entity_relations", ["target_entity_id"])
    op.create_index("ix_professional_entity_relations_type", "professional_entity_relations", ["relation_type"])
    op.create_index("ix_professional_entity_relations_source", "professional_entity_relations", ["source"])

    op.create_table(
        "professional_entity_hierarchy_relations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("child_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["child_entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_entity_hierarchy_relations_child_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_entity_hierarchy_relations_parent_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_entity_hierarchy_relations")),
        sa.UniqueConstraint("child_entity_id", "parent_entity_id", "relation_type", "source", name=op.f("uq_professional_entity_hierarchy_relations_child_entity_id")),
    )
    op.create_index("ix_professional_entity_hierarchy_child", "professional_entity_hierarchy_relations", ["child_entity_id"])
    op.create_index("ix_professional_entity_hierarchy_parent", "professional_entity_hierarchy_relations", ["parent_entity_id"])
    op.create_index("ix_professional_entity_hierarchy_type", "professional_entity_hierarchy_relations", ["relation_type"])
    op.create_index("ix_professional_entity_hierarchy_source", "professional_entity_hierarchy_relations", ["source"])

    op.create_table(
        "professional_collections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_collections")),
        sa.UniqueConstraint("slug", name=op.f("uq_professional_collections_slug")),
    )

    op.create_table(
        "professional_collection_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("collection_id", sa.BigInteger(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["professional_collections.id"],
            name=op.f("fk_professional_collection_memberships_collection_id_professional_collections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["professional_entities.id"],
            name=op.f("fk_professional_collection_memberships_entity_id_professional_entities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_collection_memberships")),
        sa.UniqueConstraint("collection_id", "entity_id", name=op.f("uq_professional_collection_memberships_collection_id")),
    )
    op.create_index("ix_professional_collection_memberships_collection", "professional_collection_memberships", ["collection_id"])
    op.create_index("ix_professional_collection_memberships_entity", "professional_collection_memberships", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_professional_collection_memberships_entity", "professional_collection_memberships")
    op.drop_index("ix_professional_collection_memberships_collection", "professional_collection_memberships")
    op.drop_table("professional_collection_memberships")

    op.drop_table("professional_collections")

    op.drop_index("ix_professional_entity_hierarchy_source", "professional_entity_hierarchy_relations")
    op.drop_index("ix_professional_entity_hierarchy_type", "professional_entity_hierarchy_relations")
    op.drop_index("ix_professional_entity_hierarchy_parent", "professional_entity_hierarchy_relations")
    op.drop_index("ix_professional_entity_hierarchy_child", "professional_entity_hierarchy_relations")
    op.drop_table("professional_entity_hierarchy_relations")

    op.drop_index("ix_professional_entity_relations_source", "professional_entity_relations")
    op.drop_index("ix_professional_entity_relations_type", "professional_entity_relations")
    op.drop_index("ix_professional_entity_relations_target_entity", "professional_entity_relations")
    op.drop_index("ix_professional_entity_relations_source_entity", "professional_entity_relations")
    op.drop_table("professional_entity_relations")

    op.drop_index("ix_professional_entity_sources_source", "professional_entity_sources")
    op.drop_index("ix_professional_entity_sources_entity_id", "professional_entity_sources")
    op.drop_table("professional_entity_sources")

    op.drop_index("ix_professional_entity_aliases_source", "professional_entity_aliases")
    op.drop_index("ix_professional_entity_aliases_normalized_alias", "professional_entity_aliases")
    op.drop_index("ix_professional_entity_aliases_entity_id", "professional_entity_aliases")
    op.drop_table("professional_entity_aliases")

    op.drop_index("ix_professional_entities_type_name", "professional_entities")
    op.drop_index("ix_professional_entities_active", "professional_entities")
    op.drop_index("ix_professional_entities_normalized_name", "professional_entities")
    op.drop_index("ix_professional_entities_type", "professional_entities")
    op.drop_table("professional_entities")
