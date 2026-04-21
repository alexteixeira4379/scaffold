"""Job domain

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import EmploymentType, ExperienceLevel, JobStatus, RemoteType
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_job_status = mysql_enum(JobStatus, "job_status")
_job_remote_type = mysql_enum(RemoteType, "job_remote_type")
_job_employment_type = mysql_enum(EmploymentType, "job_employment_type")
_job_experience_level = mysql_enum(ExperienceLevel, "job_experience_level")


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("ats_provider_id", sa.BigInteger(), nullable=True),
        sa.Column("external_job_id", sa.String(255), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("source_label", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column(
            "remote_type",
            _job_remote_type,
            server_default=mysql_default("job_remote_type", RemoteType.UNKNOWN),
            nullable=False,
        ),
        sa.Column(
            "employment_type",
            _job_employment_type,
            server_default=mysql_default("job_employment_type", EmploymentType.UNKNOWN),
            nullable=False,
        ),
        sa.Column(
            "experience_level",
            _job_experience_level,
            server_default=mysql_default("job_experience_level", ExperienceLevel.UNKNOWN),
            nullable=False,
        ),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            _job_status,
            server_default=mysql_default("job_status", JobStatus.ACTIVE),
            nullable=False,
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_name_snapshot", sa.Text(), nullable=True),
        sa.Column("company_domain_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ats_provider_id"], ["ats_providers.id"], name=op.f("fk_jobs_ats_provider_id_ats_providers")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_jobs_company_id_companies")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("ats_provider_id", "external_job_id", name="uq_jobs_ats_provider_external_id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"])
    op.create_index("ix_jobs_ats_provider_id", "jobs", ["ats_provider_id"])

    op.create_table(
        "job_raw_payloads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_raw_payloads_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_raw_payloads")),
    )
    op.create_index("ix_job_raw_payloads_job_id", "job_raw_payloads", ["job_id"])

    op.create_table(
        "job_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_events_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_events")),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])

    op.create_table(
        "job_routing_keywords",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("keyword", sa.String(512), nullable=False),
        sa.Column("keyword_source", sa.String(64), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_routing_keywords_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_routing_keywords")),
        sa.UniqueConstraint(
            "job_id",
            "keyword",
            "keyword_source",
            name=op.f("uq_job_routing_keywords_job_keyword_source"),
        ),
    )
    op.create_index("ix_job_routing_keywords_job_id", "job_routing_keywords", ["job_id"])
    op.create_index("ix_job_routing_keywords_keyword", "job_routing_keywords", ["keyword"])


def downgrade() -> None:
    op.drop_table("job_routing_keywords")
    op.drop_table("job_events")
    op.drop_table("job_raw_payloads")
    op.drop_table("jobs")
