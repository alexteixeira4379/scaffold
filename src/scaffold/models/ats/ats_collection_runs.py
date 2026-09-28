from datetime import datetime
from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from scaffold.base import CoreBase


class AtsCollectionRun(CoreBase):
    __tablename__ = "ats_collection_runs"
    __table_args__ = (Index("ix_ats_runs_source", "source_id", "started_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ats_discovery_sources.id"), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    batches: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    observed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    discarded: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error_detail: Mapped[dict | None] = mapped_column(JSON)
    last_error_category: Mapped[str | None] = mapped_column(String(64))
    next_execution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
