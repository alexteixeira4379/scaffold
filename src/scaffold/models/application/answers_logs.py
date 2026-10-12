"""Complete diagnostic snapshots for unsuccessful application attempts."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class AnswersLog(CoreBase):
    __tablename__ = "answers_logs"
    __table_args__ = (
        Index("ix_answers_logs_application_run", "application_id", "run_id"),
        Index("ix_answers_logs_provider_created", "provider", "created_at"),
        Index("ix_answers_logs_candidate_created", "candidate_id", "created_at"),
    )
    # UUID identifies a concrete worker attempt, including retries of the same run.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    run_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    candidate_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    job_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    resume_version_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    provider: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
