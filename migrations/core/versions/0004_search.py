"""Search domain

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_discovery_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_discovery_sources")),
        sa.UniqueConstraint("code", name=op.f("uq_job_discovery_sources_code")),
    )

    op.create_table(
        "search_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_discovery_source_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("search_term", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("search_filters", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("is_shared", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_discovery_source_id"], ["job_discovery_sources.id"], name=op.f("fk_search_templates_job_discovery_source_id_job_discovery_sources")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_templates")),
    )
    op.create_index("ix_search_templates_job_discovery_source_id", "search_templates", ["job_discovery_source_id"])

    op.create_table(
        "search_definitions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("search_template_id", sa.BigInteger(), nullable=True),
        sa.Column("job_discovery_source_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("candidate_search_preset_id", sa.BigInteger(), nullable=True),
        sa.Column("search_term", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("search_filters", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("schedule", sa.Text(), nullable=True),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_search_definitions_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["candidate_search_preset_id"], ["candidate_search_presets.id"], name=op.f("fk_search_definitions_candidate_search_preset_id_candidate_search_presets")),
        sa.ForeignKeyConstraint(["job_discovery_source_id"], ["job_discovery_sources.id"], name=op.f("fk_search_definitions_job_discovery_source_id_job_discovery_sources")),
        sa.ForeignKeyConstraint(["search_template_id"], ["search_templates.id"], name=op.f("fk_search_definitions_search_template_id_search_templates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_definitions")),
    )
    op.create_index("ix_search_definitions_scope_type", "search_definitions", ["scope_type"])
    op.create_index("ix_search_definitions_candidate_id", "search_definitions", ["candidate_id"])
    op.create_index("ix_search_definitions_active", "search_definitions", ["active"])

    op.create_table(
        "candidate_search_subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("candidate_search_preset_id", sa.BigInteger(), nullable=True),
        sa.Column("search_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_candidate_search_subscriptions_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["candidate_search_preset_id"], ["candidate_search_presets.id"], name=op.f("fk_candidate_search_subscriptions_candidate_search_preset_id_candidate_search_presets")),
        sa.ForeignKeyConstraint(["search_definition_id"], ["search_definitions.id"], name=op.f("fk_candidate_search_subscriptions_search_definition_id_search_definitions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_search_subscriptions")),
        sa.UniqueConstraint("candidate_id", "search_definition_id", name=op.f("uq_candidate_search_subscriptions_candidate_id")),
    )

    op.create_table(
        "search_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("search_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_found_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["search_definition_id"], ["search_definitions.id"], name=op.f("fk_search_runs_search_definition_id_search_definitions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_runs")),
    )
    op.create_index("ix_search_runs_search_definition_id", "search_runs", ["search_definition_id"])
    op.create_index("ix_search_runs_status", "search_runs", ["status"])

    op.create_table(
        "search_checkpoints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("search_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("search_run_id", sa.BigInteger(), nullable=True),
        sa.Column("checkpoint_key", sa.Text(), nullable=False),
        sa.Column("checkpoint_value", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["search_definition_id"], ["search_definitions.id"], name=op.f("fk_search_checkpoints_search_definition_id_search_definitions")),
        sa.ForeignKeyConstraint(["search_run_id"], ["search_runs.id"], name=op.f("fk_search_checkpoints_search_run_id_search_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_checkpoints")),
        sa.UniqueConstraint("search_definition_id", "checkpoint_key", name=op.f("uq_search_checkpoints_search_definition_id")),
    )
    op.create_index("ix_search_checkpoints_search_definition_id", "search_checkpoints", ["search_definition_id"])


def downgrade() -> None:
    op.drop_table("search_checkpoints")
    op.drop_table("search_runs")
    op.drop_table("candidate_search_subscriptions")
    op.drop_table("search_definitions")
    op.drop_table("search_templates")
    op.drop_table("job_discovery_sources")
