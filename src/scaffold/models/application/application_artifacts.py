from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_enum
from scaffold.constants.schema_enums import ApplicationArtifactType

_application_artifact_type = mysql_enum(ApplicationArtifactType, "application_artifact_type")


class ApplicationArtifact(CoreBase):
    __tablename__ = "application_artifacts"
    __table_args__ = (
        Index("ix_application_artifacts_job_application_id", "job_application_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_application_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_applications.id"), nullable=False
    )
    artifact_type: Mapped[ApplicationArtifactType] = mapped_column(
        _application_artifact_type, nullable=False
    )
    artifact_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
