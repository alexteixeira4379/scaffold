"""Durable ATS catalog cycles, fenced leases and persisted scheduling."""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("collection_state", sa.String(24), nullable=False, server_default="idle"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("next_collection_at", sa.DateTime(timezone=True)),
        sa.Column("collection_cycle_id", sa.String(36)),
        sa.Column("collection_lease_token", sa.String(36)),
        sa.Column("collection_lease_until", sa.DateTime(timezone=True)),
        sa.Column("collection_failures", sa.Integer(), nullable=False, server_default="0"),
    ):
        op.add_column("ats_discovery_sources", column)
    op.create_index("ix_ats_collection_due", "ats_discovery_sources", ["active", "next_collection_at", "collection_lease_until"])
    op.create_table(
        "ats_collection_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("ats_discovery_sources.id"), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_category", sa.String(64)),
        sa.Column("next_execution_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ats_runs_source", "ats_collection_runs", ["source_id", "started_at"])
    # ATS schedules govern full scans, never page continuation. No activation.
    op.execute("UPDATE ats_provider_schedules SET interval_seconds=345600")
    op.alter_column("ats_provider_schedules", "interval_seconds", existing_type=sa.Integer(), server_default="345600", existing_nullable=False)


def downgrade():
    op.drop_table("ats_collection_runs")
    op.drop_index("ix_ats_collection_due", table_name="ats_discovery_sources")
    for name in ("collection_failures", "collection_lease_until", "collection_lease_token", "collection_cycle_id", "next_collection_at", "last_attempt_at", "collection_state"):
        op.drop_column("ats_discovery_sources", name)
    op.alter_column("ats_provider_schedules", "interval_seconds", existing_type=sa.Integer(), server_default="3600", existing_nullable=False)
