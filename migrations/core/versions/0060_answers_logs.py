"""Complete snapshots of failed LinkedIn and ATS application attempts."""

from alembic import op
import sqlalchemy as sa

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade():
    identifier = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "answers_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        *[sa.Column(name, identifier, nullable=False) for name in (
            "application_id", "run_id", "candidate_id", "job_id", "resume_version_id")],
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=True),
        sa.Column("outcome", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_answers_logs_application_run", "answers_logs", ["application_id", "run_id"])
    op.create_index("ix_answers_logs_provider_created", "answers_logs", ["provider", "created_at"])
    op.create_index("ix_answers_logs_candidate_created", "answers_logs", ["candidate_id", "created_at"])


def downgrade():
    op.drop_table("answers_logs")
