from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class JobProfessionalEntity(CoreBase):
    __tablename__ = "job_professional_entities"
    __table_args__ = (
        UniqueConstraint("job_id", "entity_id", "source_field"),
        Index("ix_job_professional_entities_job_id", "job_id"),
        Index("ix_job_professional_entities_entity_id", "entity_id"),
        Index("ix_job_professional_entities_job_id_source_field", "job_id", "source_field"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("professional_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    matched_text: Mapped[str] = mapped_column(String(512), nullable=False)
    source_field: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
