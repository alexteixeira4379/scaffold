"""Search domain

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import SearchRunStatus
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_search_run_status = mysql_enum(SearchRunStatus, "search_run_status")


def upgrade() -> None:
    op.create_table(
        "job_collection_definitions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("search_term", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("search_filters", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("schedule", sa.Text(), nullable=True),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_collection_definitions")),
    )
    op.create_index("ix_job_collection_definitions_active", "job_collection_definitions", ["active"])

    op.create_table(
        "job_collection_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_collection_definition_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            _search_run_status,
            server_default=mysql_default("search_run_status", SearchRunStatus.PENDING),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_found_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_metadata", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_collection_definition_id"],
            ["job_collection_definitions.id"],
            name=op.f("fk_job_collection_runs_job_collection_definition_id_job_collection_definitions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_collection_runs")),
    )
    op.create_index("ix_job_collection_runs_job_collection_definition_id", "job_collection_runs", ["job_collection_definition_id"])
    op.create_index("ix_job_collection_runs_status", "job_collection_runs", ["status"])

    op.create_table(
        "job_collection_checkpoints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_collection_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("job_collection_run_id", sa.BigInteger(), nullable=True),
        sa.Column("checkpoint_key", sa.String(512), nullable=False),
        sa.Column("checkpoint_value", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_collection_definition_id"],
            ["job_collection_definitions.id"],
            name=op.f("fk_job_collection_checkpoints_job_collection_definition_id_job_collection_definitions"),
        ),
        sa.ForeignKeyConstraint(
            ["job_collection_run_id"],
            ["job_collection_runs.id"],
            name=op.f("fk_job_collection_checkpoints_job_collection_run_id_job_collection_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_collection_checkpoints")),
        sa.UniqueConstraint(
            "job_collection_definition_id",
            "checkpoint_key",
            name=op.f("uq_job_collection_checkpoints_job_collection_definition_id"),
        ),
    )
    op.create_index(
        "ix_job_collection_checkpoints_job_collection_definition_id",
        "job_collection_checkpoints",
        ["job_collection_definition_id"],
    )


def downgrade() -> None:
    op.drop_table("job_collection_checkpoints")
    op.drop_table("job_collection_runs")
    op.drop_table("job_collection_definitions")
