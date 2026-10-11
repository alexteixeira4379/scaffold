"""Private application answer reuse; these records never update candidate facts."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from scaffold.base import CoreBase


class ApplicationAnswerCache(CoreBase):
    __tablename__ = "application_answer_cache"
    __table_args__ = (Index("ix_application_answer_cache_scope", "candidate_id", "application_id"),)
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey(
            "candidates.id", name="fk_application_answer_cache_candidate", ondelete="CASCADE"
        ),
    )
    application_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey(
            "job_applications.id",
            name="fk_application_answer_cache_application",
            ondelete="CASCADE",
        ),
    )
    resume_version_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey(
            "resume_versions.id", name="fk_application_answer_cache_resume", ondelete="CASCADE"
        ),
    )
    context_hash: Mapped[str] = mapped_column(String(64))
    question_contract_hash: Mapped[str] = mapped_column(String(64))
    question_id: Mapped[str] = mapped_column(String(512))
    answer: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
