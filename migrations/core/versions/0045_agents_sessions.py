"""Durable OpenAI Agents SDK conversation sessions.

Revision ID: 0045
Revises: 0044
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_agent_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "assistant_agent_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("assistant_agent_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_data", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("idx_assistant_agent_messages_session_time", "assistant_agent_messages", ["session_id", "created_at"])


def downgrade():
    op.drop_table("assistant_agent_messages")
    op.drop_table("assistant_agent_sessions")
