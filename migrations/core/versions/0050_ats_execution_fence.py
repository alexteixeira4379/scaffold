"""Reserve ATS applications and fence ambiguous external sends."""

from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ats_executions",
        sa.Column("application_id", sa.BigInteger(), primary_key=True),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("resume_version_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("owner", sa.String(36), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("intent_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_ats_execution_identity"),
    )
    op.create_index("ix_ats_execution_recovery", "ats_executions", ["state", "lease_until"])


def downgrade():
    raise RuntimeError("ATS send fences must not be dropped during rollback")
