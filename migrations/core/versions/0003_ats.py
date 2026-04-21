"""ATS domain

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import (
    AtsAuthType,
    AtsPaginationType,
    AtsProviderDomainType,
    ScraperType,
)
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ats_domain_type = mysql_enum(AtsProviderDomainType, "ats_provider_domain_type")
_ats_scraper_type = mysql_enum(ScraperType, "ats_scraper_type")
_ats_auth_type = mysql_enum(AtsAuthType, "ats_auth_type")
_ats_pagination_type = mysql_enum(AtsPaginationType, "ats_pagination_type")


def upgrade() -> None:
    op.create_table(
        "ats_providers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_providers")),
        sa.UniqueConstraint("code", name=op.f("uq_ats_providers_code")),
    )

    op.create_table(
        "ats_provider_domains",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column(
            "domain_type",
            _ats_domain_type,
            server_default=mysql_default("ats_provider_domain_type", AtsProviderDomainType.MAIN),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
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
        sa.Column(
            "scraper_type",
            _ats_scraper_type,
            server_default=mysql_default("ats_scraper_type", ScraperType.HTTP),
            nullable=False,
        ),
        sa.Column("auth_type", _ats_auth_type, nullable=True),
        sa.Column("pagination_type", _ats_pagination_type, nullable=True),
        sa.Column("capabilities", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("config_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
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
        sa.Column("rule_type", sa.String(64), nullable=False),
        sa.Column("rule_key", sa.String(128), nullable=False),
        sa.Column("rule_value", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ats_provider_id"], ["ats_providers.id"], name=op.f("fk_ats_provider_rules_ats_provider_id_ats_providers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_provider_rules")),
        sa.UniqueConstraint("ats_provider_id", "rule_type", "rule_key", name=op.f("uq_ats_provider_rules_ats_provider_id")),
    )
    op.create_index("ix_ats_provider_rules_ats_provider_id", "ats_provider_rules", ["ats_provider_id"])

    op.create_table(
        "ats_discovery_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=True),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("checkpoint_key", sa.String(512), nullable=True),
        sa.Column("checkpoint_value", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("checkpoint_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ats_provider_id"],
            ["ats_providers.id"],
            name=op.f("fk_ats_discovery_sources_ats_provider_id_ats_providers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ats_discovery_sources")),
        sa.UniqueConstraint("code", name=op.f("uq_ats_discovery_sources_code")),
    )
    op.create_index(
        "ix_ats_discovery_sources_ats_provider_id",
        "ats_discovery_sources",
        ["ats_provider_id"],
    )


def downgrade() -> None:
    op.drop_table("ats_discovery_sources")
    op.drop_table("ats_provider_rules")
    op.drop_table("ats_provider_configs")
    op.drop_table("ats_provider_domains")
    op.drop_table("ats_providers")
