"""Durable domain subscriptions and application authorization ledger.

Schema is frozen here rather than importing mutable application models.
"""

from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "domain_outbox",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(191), nullable=False),
        sa.Column("destination", sa.String(191), nullable=False),
        sa.Column("exchange", sa.String(191), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source", "dedupe_key"),
    )
    op.create_index("ix_domain_outbox_source", "domain_outbox", ["source"])
    op.create_index("ix_domain_outbox_available_at", "domain_outbox", ["available_at"])
    op.create_index(
        "ix_domain_outbox_ready", "domain_outbox", ["source", "delivered_at", "available_at", "id"]
    )
    op.create_table(
        "domain_inbox",
        sa.Column("consumer", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "domain_projections",
        sa.Column("consumer", sa.String(64), primary_key=True),
        sa.Column("aggregate", sa.String(128), primary_key=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "application_authorizations",
        sa.Column("candidate_id", sa.BigInteger(), primary_key=True),
        sa.Column("job_id", sa.BigInteger(), primary_key=True),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_application_authorizations_status", "application_authorizations", ["status"]
    )
    op.create_table(
        "collection_coverage",
        sa.Column("niche_key", sa.String(191), primary_key=True),
        sa.Column("definition_id", sa.BigInteger(), nullable=False),
    )


def downgrade():
    for table in (
        "collection_coverage",
        "application_authorizations",
        "domain_projections",
        "domain_inbox",
        "domain_outbox",
    ):
        op.drop_table(table)
