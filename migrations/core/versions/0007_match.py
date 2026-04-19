"""Match domain

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import JobMatchStatus
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_job_match_status = mysql_enum(JobMatchStatus, "job_match_status")


def upgrade() -> None:
    op.create_table(
        "job_matches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "status",
            _job_match_status,
            server_default=mysql_default("job_match_status", JobMatchStatus.PENDING),
            nullable=False,
        ),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_job_matches_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_matches_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_matches")),
        sa.UniqueConstraint("candidate_id", "job_id", name=op.f("uq_job_matches_candidate_id")),
    )
    op.create_index("ix_job_matches_score", "job_matches", ["score"])
    op.create_index("ix_job_matches_status", "job_matches", ["status"])

    op.create_table(
        "job_match_scores",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_match_id", sa.BigInteger(), nullable=False),
        sa.Column("dimension", sa.String(128), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_match_id"], ["job_matches.id"], name=op.f("fk_job_match_scores_job_match_id_job_matches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_match_scores")),
        sa.UniqueConstraint("job_match_id", "dimension", name=op.f("uq_job_match_scores_job_match_id")),
    )
    op.create_index("ix_job_match_scores_job_match_id", "job_match_scores", ["job_match_id"])

    op.create_table(
        "job_match_evaluations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_match_id", sa.BigInteger(), nullable=False),
        sa.Column("engine_name", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.Text(), nullable=True),
        sa.Column("input_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("output_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_match_id"], ["job_matches.id"], name=op.f("fk_job_match_evaluations_job_match_id_job_matches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_match_evaluations")),
    )
    op.create_index("ix_job_match_evaluations_job_match_id", "job_match_evaluations", ["job_match_id"])

    op.create_table(
        "job_match_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_match_id", sa.BigInteger(), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_match_id"], ["job_matches.id"], name=op.f("fk_job_match_events_job_match_id_job_matches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_match_events")),
    )
    op.create_index("ix_job_match_events_job_match_id", "job_match_events", ["job_match_id"])


def downgrade() -> None:
    op.drop_table("job_match_events")
    op.drop_table("job_match_evaluations")
    op.drop_table("job_match_scores")
    op.drop_table("job_matches")
