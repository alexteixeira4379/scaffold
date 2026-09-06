from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ResumeReferenceType
from scaffold.db.types import mysql_enum

_resume_reference_type = mysql_enum(ResumeReferenceType, "resume_reference_type")


class ResumeProfileReference(CoreBase):
    __tablename__ = "resume_profile_references"
    __table_args__ = (Index("ix_resume_profile_references_profile_id", "resume_profile_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resume_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resume_profiles.id"), nullable=False)
    tipo: Mapped[ResumeReferenceType | None] = mapped_column(_resume_reference_type, nullable=True)
    nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cargo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

