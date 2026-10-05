"""Durable ATS send fence. Candidate/job uniqueness survives duplicate application IDs."""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class AtsExecution(CoreBase):
    __tablename__ = "ats_executions"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_ats_execution_identity"),
        Index("ix_ats_execution_recovery", "state", "lease_until"),
    )
    application_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger)
    job_id: Mapped[int] = mapped_column(BigInteger)
    run_id: Mapped[int] = mapped_column(BigInteger)
    resume_version_id: Mapped[int] = mapped_column(BigInteger)
    provider: Mapped[str] = mapped_column(String(32))
    executor: Mapped[str] = mapped_column(String(32), default="ats", server_default="ats")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fence_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="reserved")
    owner: Mapped[str] = mapped_column(String(36))
    lease_until: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    intent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
