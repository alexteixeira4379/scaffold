"""Durable conversation turns, billing operations and partial candidates."""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_target_profiles", sa.Column("automation_authorized", sa.Boolean(), nullable=False, server_default="0"))
    op.alter_column("candidates", "email", existing_type=sa.String(320), nullable=True)
    op.create_table("conversation_journeys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("state", sa.JSON(), nullable=False),
    )
    op.create_table("conversation_turns",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False, index=True),
        sa.Column("replies", sa.JSON(), nullable=False),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table("billing_checkout_operations",
        sa.Column("operation_key", sa.String(128), primary_key=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("plan_code", sa.String(128), nullable=False),
        sa.Column("subscription_id", sa.BigInteger(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("candidate_target_profiles", "automation_authorized")
    op.drop_table("billing_checkout_operations")
    op.drop_table("conversation_turns")
    op.drop_table("conversation_journeys")
    # Keep nullable email: partial candidates must not be replaced with fake contacts.
