from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class ResumeProfileExperience(CoreBase):
    __tablename__ = "resume_profile_experiences"
    __table_args__ = (Index("ix_resume_profile_experiences_profile_id", "resume_profile_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resume_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resume_profiles.id"), nullable=False)
    empresa: Mapped[str] = mapped_column(String(255), nullable=False)
    cargo: Mapped[str] = mapped_column(String(255), nullable=False)
    atividades: Mapped[str] = mapped_column(Text, nullable=False)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_saida: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
