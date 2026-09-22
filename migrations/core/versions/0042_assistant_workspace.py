"""Versioned career tasks, sources, artifacts and resumable agent runs.

Revision ID: 0042
Revises: 0041
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("objective", sa.String(1000), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_assistant_tasks_conversation", "assistant_tasks", ["conversation_id", "updated_at"]
    )
    op.create_table(
        "assistant_sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("message_id", sa.String(64)),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_assistant_sources_conversation", "assistant_sources", ["conversation_id", "created_at"]
    )
    op.create_table(
        "assistant_artifact_versions",
        sa.Column("artifact_id", sa.String(64), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_assistant_artifacts_conversation",
        "assistant_artifact_versions",
        ["conversation_id", "created_at"],
    )
    op.create_table(
        "assistant_runs",
        sa.Column("message_id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_assistant_runs_conversation", "assistant_runs", ["conversation_id", "updated_at"]
    )


def downgrade():
    for name in (
        "assistant_runs",
        "assistant_artifact_versions",
        "assistant_sources",
        "assistant_tasks",
    ):
        op.drop_table(name)
