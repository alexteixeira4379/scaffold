from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.ats_identity import identify
from scaffold.base import CoreBase


class AtsDiscoverySource(CoreBase):
    __tablename__ = "ats_discovery_sources"
    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("canonical_identity_hash"),
        Index("ix_ats_discovery_sources_ats_provider_id", "ats_provider_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ats_provider_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=True
    )
    canonical_identity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_identity: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qualification_validation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discovery_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    checkpoint_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    checkpoint_value: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    checkpoint_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Shared ORM writes derive semantic identity as well as enforcing its unique digest.


@event.listens_for(AtsDiscoverySource, "before_insert")
@event.listens_for(AtsDiscoverySource, "before_update")
def _identity_before_write(mapper, connection, target):
    if target.qualification_status == "legacy_ambiguous" or not target.base_url:
        return
    try:
        identity = identify(target.base_url)
    except ValueError:
        identity = None
    if identity:
        if target.canonical_identity and target.canonical_identity != identity.key:
            raise ValueError("ATS source identity mismatch")
        target.canonical_identity = identity.key
        target.canonical_identity_hash = identity.digest
