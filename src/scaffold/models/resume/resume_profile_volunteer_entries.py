from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ResumeVolunteerType
from scaffold.db.types import mysql_enum

_resume_volunteer_type = mysql_enum(ResumeVolunteerType, "resume_volunteer_type")


class ResumeProfileVolunteerEntry(CoreBase):
    __tablename__ = "resume_profile_volunteer_entries"
    __table_args__ = (Index("ix_resume_profile_volunteer_entries_profile_id", "resume_profile_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resume_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resume_profiles.id"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[ResumeVolunteerType] = mapped_column(_resume_volunteer_type, nullable=False)
    funcao: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    impacto: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
