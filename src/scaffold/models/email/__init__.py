"""Private inbound email metadata. Bodies and attachments live in private storage."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects import mysql
from scaffold.models.dashboard_types import CurrentTimestamp6

from scaffold.base import CoreBase

ID = BigInteger().with_variant(Integer, "sqlite")
EMAIL_DATETIME_6 = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


class EmailTimestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CandidateMailbox(EmailTimestamps, CoreBase):
    __tablename__ = "candidate_mailboxes"
    __table_args__ = (UniqueConstraint("candidate_id", "environment"), UniqueConstraint("address"))
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True
    )
    environment: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(320))
    resend_account_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")
    forward_identity_id: Mapped[int | None] = mapped_column(
        ID,
        ForeignKey(
            "auth_verified_identities.id",
            name="fk_candidate_mailboxes_forward_identity",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EmailWebhookEvent(CoreBase):
    __tablename__ = "email_webhook_events"
    __table_args__ = (
        UniqueConstraint("resend_account_id", "event_id"),
        Index("ix_email_webhook_pending", "status", "received_at"),
    )
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    resend_account_id: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(String(191))
    event_type: Mapped[str] = mapped_column(String(64))
    provider_email_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    last_error: Mapped[str | None] = mapped_column(String(256), nullable=True)


class EmailMessage(EmailTimestamps, CoreBase):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("resend_account_id", "provider_email_id"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    resend_account_id: Mapped[str] = mapped_column(String(64))
    provider_email_id: Mapped[str] = mapped_column(String(191))
    sender: Mapped[str] = mapped_column(String(512))
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    authentication: Mapped[dict] = mapped_column(JSON, default=dict)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    body_bucket: Mapped[str | None] = mapped_column(String(191), nullable=True)
    body_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body_status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending"
    )
    attachment_status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending"
    )


class EmailMessageRecipient(EmailTimestamps, CoreBase):
    __tablename__ = "email_message_recipients"
    __table_args__ = (
        UniqueConstraint("message_id", "mailbox_id"),
        Index("ix_email_recipient_list", "candidate_id", "read_at", "id"),
    )
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ID, ForeignKey("email_messages.id", ondelete="CASCADE"))
    mailbox_id: Mapped[int] = mapped_column(ID, ForeignKey("candidate_mailboxes.id"))
    candidate_id: Mapped[int] = mapped_column(ID, ForeignKey("candidates.id", ondelete="CASCADE"))
    recipient_address: Mapped[str] = mapped_column(String(320))
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    application_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True
    )


class EmailAttachment(EmailTimestamps, CoreBase):
    __tablename__ = "email_attachments"
    __table_args__ = (UniqueConstraint("message_id", "provider_attachment_id"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ID, ForeignKey("email_messages.id", ondelete="CASCADE"))
    provider_attachment_id: Mapped[str] = mapped_column(String(191))
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(191), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(ID, nullable=True)
    bucket: Mapped[str | None] = mapped_column(String(191), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")


class EmailDelivery(EmailTimestamps, CoreBase):
    __tablename__ = "email_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        UniqueConstraint("recipient_id", "destination_version"),
        UniqueConstraint("resend_account_id", "provider_send_id"),
        Index("ix_email_delivery_pending", "status", "retry_at"),
    )
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(
        ID, ForeignKey("email_message_recipients.id", ondelete="CASCADE")
    )
    destination: Mapped[str | None] = mapped_column(String(320), nullable=True)
    destination_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    identity_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("auth_verified_identities.id", ondelete="SET NULL"), nullable=True
    )
    destination_verified_at: Mapped[datetime | None] = mapped_column(
        EMAIL_DATETIME_6, nullable=True
    )
    resend_account_id: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(191))
    provider_send_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    first_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unknown_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApplicationEmailChallenge(EmailTimestamps, CoreBase):
    __tablename__ = "application_email_challenges"
    created_at: Mapped[datetime] = mapped_column(
        EMAIL_DATETIME_6, server_default=CurrentTimestamp6()
    )
    updated_at: Mapped[datetime] = mapped_column(
        EMAIL_DATETIME_6, server_default=CurrentTimestamp6(), onupdate=datetime.utcnow
    )
    __table_args__ = (
        UniqueConstraint("application_id", "run_id", "session_id"),
        UniqueConstraint("reservation_token"),
        UniqueConstraint("message_id"),
        Index("ix_email_challenge_active", "candidate_id", "provider", "status", "expires_at"),
    )
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ID, ForeignKey("candidates.id", ondelete="CASCADE"))
    mailbox_id: Mapped[int] = mapped_column(ID, ForeignKey("candidate_mailboxes.id"))
    application_id: Mapped[int] = mapped_column(
        ID, ForeignKey("job_applications.id", ondelete="CASCADE")
    )
    run_id: Mapped[int] = mapped_column(ID, ForeignKey("application_runs.id", ondelete="CASCADE"))
    execution_owner: Mapped[str] = mapped_column(String(64))
    fence_version: Mapped[int] = mapped_column(Integer)
    session_id: Mapped[str] = mapped_column(String(191))
    provider: Mapped[str] = mapped_column(
        String(32), default="greenhouse", server_default="greenhouse"
    )
    recipient_address: Mapped[str] = mapped_column(String(320))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_at: Mapped[datetime] = mapped_column(EMAIL_DATETIME_6)
    expires_at: Mapped[datetime] = mapped_column(EMAIL_DATETIME_6)
    screen_observed_at: Mapped[datetime | None] = mapped_column(EMAIL_DATETIME_6, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="waiting", server_default="waiting")
    message_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True
    )
    encrypted_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(EMAIL_DATETIME_6, nullable=True)
    reservation_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reserved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reserved_at: Mapped[datetime | None] = mapped_column(EMAIL_DATETIME_6, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(EMAIL_DATETIME_6, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(EMAIL_DATETIME_6, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class EmailRecoveryCursor(EmailTimestamps, CoreBase):
    __tablename__ = "email_recovery_cursors"
    resend_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stream: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    high_watermark: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = [
    "CandidateMailbox",
    "EmailWebhookEvent",
    "EmailMessage",
    "EmailMessageRecipient",
    "EmailAttachment",
    "EmailDelivery",
    "ApplicationEmailChallenge",
    "EmailRecoveryCursor",
]


class EmailPrivateObject(CoreBase):
    """Durable deletion references survive account and delivery cascades."""

    __tablename__ = "email_private_objects"
    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(191))
    message_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    candidate_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="uploading", server_default="uploading")
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


__all__ += ["EmailPrivateObject"]
