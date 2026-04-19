"""Candidate domain

Revision ID: 0001
Revises:
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("language_preference", sa.Text(), server_default="pt-BR", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("generated_token", sa.Text(), nullable=True),
        sa.Column("track_code", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint("generated_token", name=op.f("uq_candidates_generated_token")),
    )
    op.create_index("uq_candidates_email_lower", "candidates", [sa.text("lower(email)")], unique=True)
    op.create_index("ix_candidates_status", "candidates", ["status"])
    op.create_index("ix_candidates_track_code", "candidates", ["track_code"])

    op.create_table(
        "candidate_preferences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("target_country", sa.String(2), nullable=True),
        sa.Column("target_location", sa.Text(), nullable=True),
        sa.Column("remote_preference", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("employment_preference", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("experience_level", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("min_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_candidate_preferences_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_preferences")),
        sa.UniqueConstraint("candidate_id", name=op.f("uq_candidate_preferences_candidate_id")),
    )

    op.create_table(
        "candidate_search_presets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("keywords_include", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("keywords_exclude", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("target_country", sa.String(2), nullable=True),
        sa.Column("target_location", sa.Text(), nullable=True),
        sa.Column("remote_preference", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("employment_preference", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("experience_level", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("min_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_candidate_search_presets_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_search_presets")),
    )
    op.create_index("ix_candidate_search_presets_candidate_active", "candidate_search_presets", ["candidate_id", "active"])
    op.create_index(
        "uq_candidate_search_presets_default",
        "candidate_search_presets",
        ["candidate_id", sa.text("(case when is_default = 1 then 0 else id end)")],
        unique=True,
    )

    op.create_table(
        "candidate_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("event_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_candidate_events_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_events")),
    )


def downgrade() -> None:
    op.drop_table("candidate_events")
    op.drop_table("candidate_search_presets")
    op.drop_table("candidate_preferences")
    op.drop_table("candidates")
