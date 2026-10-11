"""Durable object cleanup references survive account cascade deletion."""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_private_objects",
        sa.Column("key", sa.String(512), nullable=False, primary_key=True),
        sa.Column("bucket", sa.String(191), nullable=False),
        sa.Column(
            "message_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "candidate_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploading"),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["email_messages.id"],
            name="fk_email_private_objects_message_id_email_messages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_email_private_objects_candidate_id_candidates",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_email_private_objects_message_id", "email_private_objects", ["message_id"])
    op.create_index(
        "ix_email_private_objects_candidate_id", "email_private_objects", ["candidate_id"]
    )


def downgrade():
    raise RuntimeError("Private object deletion references must survive rollback")
