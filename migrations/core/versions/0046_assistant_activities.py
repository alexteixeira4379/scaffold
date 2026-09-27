"""Assistant activities and explicit session state (additive).

- ``assistant_activities``: one user objective across turns (drafts live in
  ``assistant_artifact_versions`` with task_id = activity id; operations and
  their results in ``assistant_proposals``).
- ``assistant_session_states``: session generation (inactivity TTL), focus,
  conducting specialist, consulted data and the auxiliary summary.

Nothing existing is altered or backfilled: conversations without a state row
start at generation 0, which keeps using the existing Agents SDK session.

Revision ID: 0046
Revises: 0045
"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_activities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("objective", sa.String(1000), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("session_generation", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_assistant_activities_conversation", "assistant_activities", ["conversation_id", "updated_at"]
    )
    op.create_table(
        "assistant_session_states",
        sa.Column("conversation_id", sa.String(64), primary_key=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("last_user_at", sa.BigInteger(), nullable=False),
        sa.Column("last_input_key", sa.String(128)),
        sa.Column("focus_activity_id", sa.String(64)),
        sa.Column("specialist", sa.String(64)),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )


def downgrade():
    op.drop_table("assistant_session_states")
    op.drop_index("ix_assistant_activities_conversation", table_name="assistant_activities")
    op.drop_table("assistant_activities")
