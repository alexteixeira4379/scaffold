"""Durable cross-domain delivery; effects stay owned by their services."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
    LargeBinary,
)
from sqlalchemy.dialects.mysql import DATETIME, LONGBLOB, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase

_event_key_type = String(64).with_variant(VARCHAR(64, collation="utf8mb4_0900_bin"), "mysql")


class DomainOutbox(CoreBase):
    __tablename__ = "domain_outbox"
    __table_args__ = (
        UniqueConstraint("source", "dedupe_key"),
        Index("ix_domain_outbox_ready", "source", "delivered_at", "quarantined_at", "available_at", "id"),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    source: Mapped[str] = mapped_column(String(64), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(191))
    destination: Mapped[str] = mapped_column(String(191))
    exchange: Mapped[str] = mapped_column(String(191), default="")
    payload: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_body: Mapped[bytes | None] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DomainInbox(CoreBase):
    __tablename__ = "domain_inbox"
    consumer: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(_event_key_type, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WorkerDelivery(CoreBase):
    """Application attempts and recovery state, independent of broker redelivery."""

    __tablename__ = "worker_deliveries"
    __table_args__ = (Index("ix_worker_delivery_status", "consumer", "status", "updated_at"),)
    consumer: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(_event_key_type, primary_key=True)
    queue: Mapped[str] = mapped_column(String(191))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    retry_generation: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkerQuarantine(CoreBase):
    __tablename__ = "worker_quarantine"
    __table_args__ = (Index("ix_worker_quarantine_consumer_time", "consumer", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    consumer: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(_event_key_type)
    queue: Mapped[str] = mapped_column(String(191))
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    raw_body: Mapped[bytes | None] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replayed_by: Mapped[str | None] = mapped_column(String(191), nullable=True)
    replay_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DomainProjection(CoreBase):
    __tablename__ = "domain_projections"
    consumer: Mapped[str] = mapped_column(String(64), primary_key=True)
    aggregate: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ApplicationAuthorization(CoreBase):
    """One durable intent per candidate/job, surviving dispatch failures."""

    __tablename__ = "application_authorizations"
    candidate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="waiting", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    application_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CollectionCoverage(CoreBase):
    __tablename__ = "collection_coverage"
    niche_key: Mapped[str] = mapped_column(String(191), primary_key=True)
    definition_id: Mapped[int] = mapped_column(BigInteger)
