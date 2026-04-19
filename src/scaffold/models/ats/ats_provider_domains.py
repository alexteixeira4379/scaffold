from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import AtsProviderDomainType

_ats_provider_domain_type = mysql_enum(AtsProviderDomainType, "ats_provider_domain_type")


class AtsProviderDomain(CoreBase):
    __tablename__ = "ats_provider_domains"
    __table_args__ = (
        UniqueConstraint("domain"),
        Index("ix_ats_provider_domains_ats_provider_id", "ats_provider_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ats_provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_type: Mapped[AtsProviderDomainType] = mapped_column(
        _ats_provider_domain_type,
        nullable=False,
        server_default=mysql_default("ats_provider_domain_type", AtsProviderDomainType.MAIN),
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
