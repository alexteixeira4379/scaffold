"""Resume domain

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from scaffold.constants.schema_enums import (
    ResumeDocumentFormat,
    ResumeSessionStatus,
    ResumeSessionType,
    ResumeStepInputType,
)
from scaffold.db.types import mysql_default, mysql_enum

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_resume_step_input_type = mysql_enum(ResumeStepInputType, "resume_step_input_type")
_resume_session_type = mysql_enum(ResumeSessionType, "resume_session_type")
_resume_session_status = mysql_enum(ResumeSessionStatus, "resume_session_status")
_resume_document_format = mysql_enum(ResumeDocumentFormat, "resume_document_format")


def upgrade() -> None:
    op.create_table(
        "resume_build_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("step_key", sa.String(128), nullable=False),
        sa.Column("step_label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("step_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "input_type",
            _resume_step_input_type,
            server_default=mysql_default("resume_step_input_type", ResumeStepInputType.TEXT),
            nullable=False,
        ),
        sa.Column("options", sa.JSON(), server_default=sa.text("(JSON_ARRAY())"), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_build_steps")),
        sa.UniqueConstraint("step_key", name=op.f("uq_resume_build_steps_step_key")),
    )

    op.create_table(
        "resume_build_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "session_type",
            _resume_session_type,
            server_default=mysql_default("resume_session_type", ResumeSessionType.BUILDER),
            nullable=False,
        ),
        sa.Column(
            "status",
            _resume_session_status,
            server_default=mysql_default("resume_session_status", ResumeSessionStatus.STARTED),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_metadata", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_resume_build_sessions_candidate_id_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_build_sessions")),
    )
    op.create_index("ix_resume_build_sessions_candidate_id", "resume_build_sessions", ["candidate_id"])

    op.create_table(
        "resume_build_answers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("step_id", sa.BigInteger(), nullable=False),
        sa.Column("answer_data", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["resume_build_sessions.id"], name=op.f("fk_resume_build_answers_session_id_resume_build_sessions")),
        sa.ForeignKeyConstraint(["step_id"], ["resume_build_steps.id"], name=op.f("fk_resume_build_answers_step_id_resume_build_steps")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_build_answers")),
        sa.UniqueConstraint("session_id", "step_id", name=op.f("uq_resume_build_answers_session_id")),
    )

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "format",
            _resume_document_format,
            server_default=mysql_default("resume_document_format", ResumeDocumentFormat.PDF),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_resume_versions_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["session_id"], ["resume_build_sessions.id"], name=op.f("fk_resume_versions_session_id_resume_build_sessions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_versions")),
    )
    op.create_index("ix_resume_versions_candidate_id", "resume_versions", ["candidate_id"])
    op.create_index(
        "ix_resume_versions_candidate_is_current",
        "resume_versions",
        ["candidate_id", "is_current"],
    )

    op.create_table(
        "cover_letter_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name=op.f("fk_cover_letter_versions_candidate_id_candidates")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_cover_letter_versions_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cover_letter_versions")),
    )
    op.create_index("ix_cover_letter_versions_candidate_id", "cover_letter_versions", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("cover_letter_versions")
    op.drop_table("resume_versions")
    op.drop_table("resume_build_answers")
    op.drop_table("resume_build_sessions")
    op.drop_table("resume_build_steps")
