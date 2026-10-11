"""Private durable form answers scoped to the authorized application and context."""

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "application_answer_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True, nullable=False),
        sa.Column(
            "candidate_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "application_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "resume_version_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("question_contract_hash", sa.String(64), nullable=False),
        sa.Column("question_id", sa.String(512), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_application_answer_cache_candidate",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["job_applications.id"],
            name="fk_application_answer_cache_application",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_version_id"],
            ["resume_versions.id"],
            name="fk_application_answer_cache_resume",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_application_answer_cache_scope",
        "application_answer_cache",
        ["candidate_id", "application_id"],
    )


def downgrade():
    raise RuntimeError("Private answer history is retained while the account exists")
