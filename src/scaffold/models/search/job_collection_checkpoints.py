from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase


class JobCollectionCheckpoint(CoreBase):
    __tablename__ = "job_collection_checkpoints"
    __table_args__ = (
        Index(
            "ix_job_collection_checkpoints_job_collection_definition_id",
            "job_collection_definition_id",
        ),
        UniqueConstraint(
            "job_collection_definition_id",
            "checkpoint_key",
            name="uq_job_collection_checkpoints_job_collection_definition_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_collection_definition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_collection_definitions.id"), nullable=False
    )
    job_collection_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("job_collection_runs.id"), nullable=True
    )
    checkpoint_key: Mapped[str] = mapped_column(String(512), nullable=False)
    checkpoint_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
