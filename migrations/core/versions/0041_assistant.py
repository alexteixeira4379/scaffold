"""Durable post-activation assistant; does not change onboarding tables.

Revision ID: 0041
Revises: 0040
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("lease_owner", sa.String(64)),
        sa.Column("lease_until", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("candidate_id", "channel", name="uq_assistant_candidate_channel"),
    )
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON()),
        sa.UniqueConstraint("conversation_id", "request_id", name="uq_assistant_message_request"),
    )
    op.create_index(
        "ix_assistant_messages_history",
        "assistant_messages",
        ["conversation_id", "created_at", "id"],
    )
    op.create_index("ix_assistant_messages_pending", "assistant_messages", ["status", "created_at"])
    op.create_table(
        "assistant_proposals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_assistant_proposals_owner", "assistant_proposals", ["conversation_id", "status"]
    )
    op.create_table(
        "assistant_command_receipts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("service", sa.String(48), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )


def downgrade():
    for table in (
        "assistant_command_receipts",
        "assistant_proposals",
        "assistant_messages",
        "assistant_conversations",
    ):
        op.drop_table(table)
