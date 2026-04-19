from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Text, func
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import CompanyDomainType

_company_domain_type = mysql_enum(CompanyDomainType, "company_domain_type")


class CompanyDomain(CoreBase):
    __tablename__ = "company_domains"
    __table_args__ = (
        Index("uq_company_domains_domain_lower", sa_text("lower(domain)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("companies.id"), nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    domain_type: Mapped[CompanyDomainType] = mapped_column(
        _company_domain_type,
        nullable=False,
        server_default=mysql_default("company_domain_type", CompanyDomainType.PRIMARY),
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
