"""Application domain

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_applications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_match_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("apply_mode", sa.Text(), server_default="auto", nullable=False),
        sa.Column("easy_apply", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("prepared", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("process_details", sa.Text(), nullable=True),
        sa.Column("application_url_snapshot", sa.Text(), nullable=True),
        sa.Column("job_title_snapshot", sa.Text(), nullable=True),
        sa.Column("company_name_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_match_id"], ["job_matches.id"], name=op.f("fk_job_applications_job_match_id_job_matches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_applications")),
        sa.UniqueConstraint("job_match_id", name=op.f("uq_job_applications_job_match_id")),
    )
    op.create_index("ix_job_applications_status", "job_applications", ["status"])

    op.create_table(
        "application_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_application_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], name=op.f("fk_application_runs_job_application_id_job_applications")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_runs")),
    )
    op.create_index("ix_application_runs_job_application_id", "application_runs", ["job_application_id"])
    op.create_index("ix_application_runs_status", "application_runs", ["status"])

    op.create_table(
        "application_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_run_id", sa.BigInteger(), nullable=False),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("step_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("input_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("output_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_run_id"], ["application_runs.id"], name=op.f("fk_application_steps_application_run_id_application_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_steps")),
    )
    op.create_index("ix_application_steps_application_run_id", "application_steps", ["application_run_id"])

    op.create_table(
        "application_artifacts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_application_id", sa.BigInteger(), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("artifact_name", sa.Text(), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], name=op.f("fk_application_artifacts_job_application_id_job_applications")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_artifacts")),
    )
    op.create_index("ix_application_artifacts_job_application_id", "application_artifacts", ["job_application_id"])

    op.create_table(
        "application_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=True),
        sa.Column("platform_domain", sa.Text(), nullable=True),
        sa.Column("session_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ats_provider_id"], ["ats_providers.id"], name=op.f("fk_application_sessions_ats_provider_id_ats_providers")),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_application_sessions_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_sessions")),
    )
    op.create_index("ix_application_sessions_candidate_id", "application_sessions", ["candidate_id"])
    op.create_index("ix_application_sessions_ats_provider_id", "application_sessions", ["ats_provider_id"])

    op.create_table(
        "application_domain_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("rule_value", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_domain_rules")),
        sa.UniqueConstraint("domain", "rule_type", "rule_key", name=op.f("uq_application_domain_rules_domain")),
    )
    op.create_index("ix_application_domain_rules_domain", "application_domain_rules", ["domain"])

    op.create_table(
        "application_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_application_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("message_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], name=op.f("fk_application_messages_job_application_id_job_applications")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_messages")),
    )
    op.create_index("ix_application_messages_job_application_id", "application_messages", ["job_application_id"])

    op.create_table(
        "application_failures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_application_id", sa.BigInteger(), nullable=False),
        sa.Column("application_run_id", sa.BigInteger(), nullable=True),
        sa.Column("failure_type", sa.Text(), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("failure_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_run_id"], ["application_runs.id"], name=op.f("fk_application_failures_application_run_id_application_runs")),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], name=op.f("fk_application_failures_job_application_id_job_applications")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_failures")),
    )
    op.create_index("ix_application_failures_job_application_id", "application_failures", ["job_application_id"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_application_id", sa.BigInteger(), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_application_id"], ["job_applications.id"], name=op.f("fk_application_events_job_application_id_job_applications")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_events")),
    )
    op.create_index("ix_application_events_job_application_id", "application_events", ["job_application_id"])


def downgrade() -> None:
    op.drop_table("application_events")
    op.drop_table("application_failures")
    op.drop_table("application_messages")
    op.drop_table("application_domain_rules")
    op.drop_table("application_sessions")
    op.drop_table("application_artifacts")
    op.drop_table("application_steps")
    op.drop_table("application_runs")
    op.drop_table("job_applications")
