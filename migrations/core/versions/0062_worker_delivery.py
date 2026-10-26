"""Durable worker attempts, quarantine and short outbox claims."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, LONGBLOB, VARCHAR

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade():
    # Event identities are exact keys, including case, accents and trailing
    # characters. Keep existing values while removing CI/PAD SPACE comparison.
    if op.get_bind().dialect.name == "mysql":
        op.alter_column("domain_inbox", "event_id", existing_type=sa.String(64),
                        type_=VARCHAR(64, collation="utf8mb4_0900_bin"), existing_nullable=False)
    op.add_column("domain_outbox", sa.Column("headers", sa.JSON(), nullable=True))
    op.add_column("domain_outbox", sa.Column("quarantined_at", sa.DateTime(), nullable=True))
    op.add_column("domain_outbox", sa.Column("raw_body", sa.LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True))
    op.add_column("domain_outbox", sa.Column("claim_token", sa.String(36), nullable=True))
    op.add_column("domain_outbox", sa.Column("claimed_until", sa.DateTime(), nullable=True))
    op.drop_index("ix_domain_outbox_ready", table_name="domain_outbox")
    op.create_index("ix_domain_outbox_ready", "domain_outbox",
                    ["source", "delivered_at", "quarantined_at", "available_at", "id"])
    op.create_table(
        "worker_deliveries",
        sa.Column("consumer", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64).with_variant(VARCHAR(64, collation="utf8mb4_0900_bin"), "mysql"), primary_key=True),
        sa.Column("queue", sa.String(191), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("retry_generation", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime()),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("claimed_until", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")),
        sa.Column("last_error", sa.String(255)),
        sa.Column("receipt", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_worker_delivery_status", "worker_deliveries", ["consumer", "status", "updated_at"])
    op.create_table(
        "worker_quarantine",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("consumer", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64).with_variant(VARCHAR(64, collation="utf8mb4_0900_bin"), "mysql"), nullable=False),
        sa.Column("queue", sa.String(191), nullable=False),
        sa.Column("correlation_id", sa.String(255)),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("raw_body", sa.LargeBinary().with_variant(LONGBLOB(), "mysql")),
        sa.Column("storage_key", sa.String(512)),
        sa.Column("headers", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("replayed_at", sa.DateTime()),
        sa.Column("replayed_by", sa.String(191)),
        sa.Column("replay_metadata", sa.JSON()),
    )
    op.create_index("ix_worker_quarantine_consumer_time", "worker_quarantine", ["consumer", "created_at"])


def downgrade():
    raise RuntimeError("Worker delivery history must be preserved; roll back code without dropping data")
