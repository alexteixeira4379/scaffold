"""Reuse the durable ATS send fence for every application executor."""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ats_executions", sa.Column("executor", sa.String(32), nullable=False, server_default="ats"))
    op.add_column("ats_executions", sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column("ats_executions", sa.Column("fence_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("ats_executions", sa.Column("policy_version", sa.String(32), nullable=True))


def downgrade():
    raise RuntimeError("Execution send fences must not be removed during rollback")
