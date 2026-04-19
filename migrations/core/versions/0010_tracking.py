"""Tracking domain

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracking_visits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_tracking_visits_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracking_visits")),
    )
    op.create_index("ix_tracking_visits_session_id", "tracking_visits", ["session_id"])
    op.create_index("ix_tracking_visits_candidate_id", "tracking_visits", ["candidate_id"])

    op.create_table(
        "tracking_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_key", sa.String(128), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_tracking_sessions_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracking_sessions")),
        sa.UniqueConstraint("session_key", name=op.f("uq_tracking_sessions_session_key")),
    )
    op.create_index("ix_tracking_sessions_candidate_id", "tracking_sessions", ["candidate_id"])

    op.create_table(
        "tracking_clicks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("track_code", sa.String(128), nullable=True),
        sa.Column("click_key", sa.String(255), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("full_url", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("utm_source", sa.Text(), nullable=True),
        sa.Column("utm_medium", sa.Text(), nullable=True),
        sa.Column("utm_campaign", sa.Text(), nullable=True),
        sa.Column("utm_content", sa.Text(), nullable=True),
        sa.Column("utm_term", sa.Text(), nullable=True),
        sa.Column("utm_id", sa.Text(), nullable=True),
        sa.Column("fbclid", sa.String(256), nullable=True),
        sa.Column("fbc", sa.Text(), nullable=True),
        sa.Column("fbp", sa.Text(), nullable=True),
        sa.Column("pixel_id", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("referer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_tracking_clicks_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracking_clicks")),
        sa.UniqueConstraint("click_key", name=op.f("uq_tracking_clicks_click_key")),
    )
    op.create_index("ix_tracking_clicks_track_code", "tracking_clicks", ["track_code"])
    op.create_index("ix_tracking_clicks_session_id", "tracking_clicks", ["session_id"])
    op.create_index("ix_tracking_clicks_candidate_id", "tracking_clicks", ["candidate_id"])
    op.create_index("ix_tracking_clicks_fbclid", "tracking_clicks", ["fbclid"])

    op.create_table(
        "tracking_attributions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("tracking_click_id", sa.BigInteger(), nullable=True),
        sa.Column("attribution_type", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("medium", sa.Text(), nullable=True),
        sa.Column("campaign", sa.Text(), nullable=True),
        sa.Column("attributed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_tracking_attributions_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["tracking_click_id"], ["tracking_clicks.id"], name=op.f("fk_tracking_attributions_tracking_click_id_tracking_clicks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracking_attributions")),
    )
    op.create_index("ix_tracking_attributions_candidate_id", "tracking_attributions", ["candidate_id"])

    op.create_table(
        "tracking_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("tracking_click_id", sa.BigInteger(), nullable=True),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_tracking_events_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["tracking_click_id"], ["tracking_clicks.id"], name=op.f("fk_tracking_events_tracking_click_id_tracking_clicks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracking_events")),
    )
    op.create_index("ix_tracking_events_session_id", "tracking_events", ["session_id"])
    op.create_index("ix_tracking_events_candidate_id", "tracking_events", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("tracking_events")
    op.drop_table("tracking_attributions")
    op.drop_table("tracking_clicks")
    op.drop_table("tracking_sessions")
    op.drop_table("tracking_visits")
