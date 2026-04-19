from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import AtsAuthType, AtsPaginationType, ScraperType

_ats_scraper_type = mysql_enum(ScraperType, "ats_scraper_type")
_ats_auth_type = mysql_enum(AtsAuthType, "ats_auth_type")
_ats_pagination_type = mysql_enum(AtsPaginationType, "ats_pagination_type")


class AtsProviderConfig(CoreBase):
    __tablename__ = "ats_provider_configs"
    __table_args__ = (
        Index("ix_ats_provider_configs_ats_provider_id", "ats_provider_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ats_provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ats_providers.id"), nullable=False
    )
    scraper_type: Mapped[ScraperType] = mapped_column(
        _ats_scraper_type,
        nullable=False,
        server_default=mysql_default("ats_scraper_type", ScraperType.HTTP),
    )
    auth_type: Mapped[AtsAuthType | None] = mapped_column(_ats_auth_type, nullable=True)
    pagination_type: Mapped[AtsPaginationType | None] = mapped_column(
        _ats_pagination_type, nullable=True
    )
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    config_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
