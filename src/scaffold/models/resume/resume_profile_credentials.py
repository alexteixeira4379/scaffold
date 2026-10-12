from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import DATETIME

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ResumeCredentialType
from scaffold.db.types import mysql_enum

_resume_credential_type = mysql_enum(ResumeCredentialType, "resume_credential_type")


class ResumeProfileCredential(CoreBase):
    __tablename__ = "resume_profile_credentials"
    __table_args__ = (Index("ix_resume_profile_credentials_profile_id", "resume_profile_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resume_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resume_profiles.id"), nullable=False
    )
    credential_type: Mapped[ResumeCredentialType] = mapped_column(
        _resume_credential_type, nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    declaration_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    declared_at: Mapped[datetime | None] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
