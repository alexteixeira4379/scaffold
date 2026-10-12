"""Candidate-declared, country-specific legal facts; unknown is never a negative."""

from datetime import date, datetime
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column
from scaffold.base import CoreBase


class CandidateWorkPermission(CoreBase):
    __tablename__ = "candidate_work_permissions"
    __table_args__ = (
        UniqueConstraint("candidate_id", "country", name="uq_candidate_work_permission_country"),
        CheckConstraint(
            "authorization IN ('yes','no','unknown')", name="work_permission_authorization"
        ),
        CheckConstraint(
            "sponsorship IN ('yes','no','unknown')", name="work_permission_sponsorship"
        ),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    candidate_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("candidates.id", name="fk_work_permission_candidate", ondelete="CASCADE"),
    )
    country: Mapped[str] = mapped_column(String(2))
    authorization: Mapped[str] = mapped_column(
        String(8), default="unknown", server_default="unknown"
    )
    sponsorship: Mapped[str] = mapped_column(String(8), default="unknown", server_default="unknown")
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    declaration_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    declared_at: Mapped[datetime | None] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True
    )
