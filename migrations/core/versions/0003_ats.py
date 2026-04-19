"""ATS domain

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ats_providers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_providers")),
        sa.UniqueConstraint("code", name=op.f("uq_ats_providers_code")),
    )

    op.create_table(
        "ats_provider_domains",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("domain_type", sa.Text(), server_default="main", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ats_provider_id"], ["ats_providers.id"], name=op.f("fk_ats_provider_domains_ats_provider_id_ats_providers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_provider_domains")),
        sa.UniqueConstraint("domain", name=op.f("uq_ats_provider_domains_domain")),
    )
    op.create_index("ix_ats_provider_domains_ats_provider_id", "ats_provider_domains", ["ats_provider_id"])

    op.create_table(
        "ats_provider_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=False),
        sa.Column("scraper_type", sa.Text(), server_default="http", nullable=False),
        sa.Column("auth_type", sa.Text(), nullable=True),
        sa.Column("pagination_type", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("config_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ats_provider_id"], ["ats_providers.id"], name=op.f("fk_ats_provider_configs_ats_provider_id_ats_providers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_provider_configs")),
    )
    op.create_index("ix_ats_provider_configs_ats_provider_id", "ats_provider_configs", ["ats_provider_id"])

    op.create_table(
        "ats_provider_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("rule_value", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ats_provider_id"], ["ats_providers.id"], name=op.f("fk_ats_provider_rules_ats_provider_id_ats_providers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_provider_rules")),
        sa.UniqueConstraint("ats_provider_id", "rule_type", "rule_key", name=op.f("uq_ats_provider_rules_ats_provider_id")),
    )
    op.create_index("ix_ats_provider_rules_ats_provider_id", "ats_provider_rules", ["ats_provider_id"])


def downgrade() -> None:
    op.drop_table("ats_provider_rules")
    op.drop_table("ats_provider_configs")
    op.drop_table("ats_provider_domains")
    op.drop_table("ats_providers")
