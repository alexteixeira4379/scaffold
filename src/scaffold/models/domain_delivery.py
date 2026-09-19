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
)
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class DomainOutbox(CoreBase):
    __tablename__ = "domain_outbox"
    __table_args__ = (
        UniqueConstraint("source", "dedupe_key"),
        Index("ix_domain_outbox_ready", "source", "delivered_at", "available_at", "id"),
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
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DomainInbox(CoreBase):
    __tablename__ = "domain_inbox"
    consumer: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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
