from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class CandidateApplicationData(CoreBase):
    __tablename__ = "candidate_application_data"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_candidate_application_data_candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=False
    )

    # Application-specific data
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    citizenship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    availability: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Demographic data (US forms)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    veteran_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    disability_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Custom overrides for recurring questions
    custom_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
