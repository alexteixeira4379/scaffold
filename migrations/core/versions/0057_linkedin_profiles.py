"""Durable connection state and fencing for candidate LinkedIn browser profiles."""

from alembic import op
import sqlalchemy as sa

revision = "0057_linkedin_profiles"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_linkedin_profiles",
        sa.Column(
            "candidate_id",
            sa.BigInteger(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("profile_id", sa.String(36), nullable=False, unique=True),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("authenticated_fence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("fence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(32), nullable=False, server_default="login_required"),
        sa.Column("reason", sa.String(128)),
        sa.Column("last_authenticated_at", sa.DateTime()),
        sa.Column("last_used_at", sa.DateTime()),
        sa.Column("lease_owner", sa.String(36)),
        sa.Column("lease_operation", sa.String(16)),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column("next_application_allowed_at", sa.DateTime()),
    )


def downgrade():
    raise RuntimeError("Removing LinkedIn profile tombstones can resurrect disconnected sessions")
