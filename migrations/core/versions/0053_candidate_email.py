"""Private candidate inbox and per-application email snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_messages",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("resend_account_id", sa.String(length=64), nullable=False),
        sa.Column("provider_email_id", sa.String(length=191), nullable=False),
        sa.Column("sender", sa.String(length=512), nullable=False),
        sa.Column("reply_to", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("authentication", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("body_bucket", sa.String(length=191), nullable=True),
        sa.Column("body_object_key", sa.String(length=512), nullable=True),
        sa.Column("body_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "attachment_status", sa.String(length=32), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.UniqueConstraint(
            "resend_account_id", "provider_email_id", name="uq_email_messages_resend_account_id"
        ),
    )
    op.create_table(
        "email_recovery_cursors",
        sa.Column("resend_account_id", sa.String(length=64), nullable=False, primary_key=True),
        sa.Column("stream", sa.String(length=64), nullable=False, primary_key=True),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("high_watermark", sa.DateTime(), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(), nullable=True),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_table(
        "email_webhook_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("resend_account_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=191), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("provider_email_id", sa.String(length=191), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.String(length=256), nullable=True),
        sa.UniqueConstraint(
            "resend_account_id", "event_id", name="uq_email_webhook_events_resend_account_id"
        ),
    )
    op.create_index(
        "ix_email_webhook_pending", "email_webhook_events", ["status", "received_at"], unique=False
    )
    op.create_table(
        "email_attachments",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "message_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("provider_attachment_id", sa.String(length=191), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=191), nullable=True),
        sa.Column(
            "size_bytes", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("bucket", sa.String(length=191), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["email_messages.id"],
            name="fk_email_attachments_message_id_email_messages",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "message_id", "provider_attachment_id", name="uq_email_attachments_message_id"
        ),
    )
    op.create_table(
        "candidate_mailboxes",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "candidate_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=320), nullable=False),
        sa.Column("resend_account_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "forward_identity_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_candidate_mailboxes_candidate_id_candidates",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "candidate_id", "environment", name="uq_candidate_mailboxes_candidate_id"
        ),
        sa.ForeignKeyConstraint(
            ["forward_identity_id"],
            ["auth_verified_identities.id"],
            name="fk_candidate_mailboxes_forward_identity",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("address", name="uq_candidate_mailboxes_address"),
    )
    op.create_table(
        "email_message_recipients",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "message_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "mailbox_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "candidate_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("recipient_address", sa.String(length=320), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "application_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["email_messages.id"],
            name="fk_email_message_recipients_message_id_email_messages",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "message_id", "mailbox_id", name="uq_email_message_recipients_message_id"
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["job_applications.id"],
            name="fk_email_message_recipients_application_id_job_applications",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["mailbox_id"],
            ["candidate_mailboxes.id"],
            name="fk_email_message_recipients_mailbox_id_candidate_mailboxes",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_email_message_recipients_candidate_id_candidates",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_email_recipient_list",
        "email_message_recipients",
        ["candidate_id", "read_at", "id"],
        unique=False,
    )
    op.create_table(
        "application_email_challenges",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "candidate_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "mailbox_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column(
            "application_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("run_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("execution_owner", sa.String(length=64), nullable=False),
        sa.Column("fence_version", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=191), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="greenhouse"),
        sa.Column("recipient_address", sa.String(length=320), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("screen_observed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="waiting"),
        sa.Column(
            "message_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("encrypted_code", sa.Text(), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(), nullable=True),
        sa.Column("reservation_token", sa.String(length=64), nullable=True),
        sa.Column("reserved_by", sa.String(length=64), nullable=True),
        sa.Column("reserved_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_application_email_challenges_candidate_id_candidates",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "application_id",
            "run_id",
            "session_id",
            name="uq_application_email_challenges_application_id",
        ),
        sa.UniqueConstraint(
            "reservation_token", name="uq_application_email_challenges_reservation_token"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["application_runs.id"],
            name="fk_application_email_challenges_run_id_application_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mailbox_id"],
            ["candidate_mailboxes.id"],
            name="fk_application_email_challenges_mailbox_id_candidate_mailboxes",
        ),
        sa.UniqueConstraint("message_id", name="uq_application_email_challenges_message_id"),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["email_messages.id"],
            name="fk_application_email_challenges_message_id_email_messages",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["job_applications.id"],
            name="fk_application_email_challenges_application_id_job_applications",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_email_challenge_active",
        "application_email_challenges",
        ["candidate_id", "provider", "status", "expires_at"],
        unique=False,
    )
    op.create_table(
        "email_deliveries",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "recipient_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.Column("destination", sa.String(length=320), nullable=True),
        sa.Column("destination_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "identity_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
        sa.Column("destination_verified_at", sa.DateTime(), nullable=True),
        sa.Column("resend_account_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=191), nullable=False),
        sa.Column("provider_send_id", sa.String(length=191), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("retry_at", sa.DateTime(), nullable=True),
        sa.Column("unknown_since", sa.DateTime(), nullable=True),
        sa.Column("provider_event_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=256), nullable=True),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.UniqueConstraint(
            "resend_account_id", "provider_send_id", name="uq_email_deliveries_resend_account_id"
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["auth_verified_identities.id"],
            name="fk_email_deliveries_identity_id_auth_verified_identities",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "recipient_id", "destination_version", name="uq_email_deliveries_recipient_id"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_email_deliveries_idempotency_key"),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["email_message_recipients.id"],
            name="fk_email_deliveries_recipient_id_email_message_recipients",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_email_delivery_pending", "email_deliveries", ["status", "retry_at"], unique=False
    )
    op.add_column("job_applications", sa.Column("application_email", sa.String(320), nullable=True))
    op.add_column(
        "job_applications",
        sa.Column(
            "mailbox_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True
        ),
    )
    with op.batch_alter_table("job_applications") as batch:
        batch.create_foreign_key(
            "fk_job_applications_mailbox_id_candidate_mailboxes",
            "candidate_mailboxes",
            ["mailbox_id"],
            ["id"],
        )


def downgrade():
    raise RuntimeError(
        "Mailbox tombstones and historical application addresses must survive rollback"
    )
