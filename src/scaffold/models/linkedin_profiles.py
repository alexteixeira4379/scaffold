"""Durable LinkedIn connection metadata; authentication material stays in browser volume."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class LinkedInProfile(CoreBase):
    __tablename__ = "candidate_linkedin_profiles"
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    authenticated_fence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    fence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="login_required")
    reason: Mapped[str | None] = mapped_column(String(128))
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_owner: Mapped[str | None] = mapped_column(String(36))
    lease_operation: Mapped[str | None] = mapped_column(String(16))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_application_allowed_at: Mapped[datetime | None] = mapped_column(DateTime)
