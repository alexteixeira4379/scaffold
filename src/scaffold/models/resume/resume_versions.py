from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ResumeDocumentFormat

_resume_document_format = mysql_enum(ResumeDocumentFormat, "resume_document_format")


class ResumeVersion(CoreBase):
    __tablename__ = "resume_versions"
    __table_args__ = (
        Index("ix_resume_versions_candidate_id", "candidate_id"),
        Index(
            "uq_resume_versions_current",
            "candidate_id",
            text("(case when is_current = 1 then 0 else id end)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("resume_build_sessions.id"), nullable=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    format: Mapped[ResumeDocumentFormat] = mapped_column(
        _resume_document_format,
        nullable=False,
        server_default=mysql_default("resume_document_format", ResumeDocumentFormat.PDF),
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
