from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ResumeCredentialType
from scaffold.db.types import mysql_enum

_resume_credential_type = mysql_enum(ResumeCredentialType, "resume_credential_type")


class ResumeProfileCredential(CoreBase):
    __tablename__ = "resume_profile_credentials"
    __table_args__ = (Index("ix_resume_profile_credentials_profile_id", "resume_profile_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resume_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resume_profiles.id"), nullable=False)
    credential_type: Mapped[ResumeCredentialType] = mapped_column(_resume_credential_type, nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

