from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.models.dashboard_types import DATETIME_6
from scaffold.constants.schema_enums import ResumeDocumentFormat
from scaffold.db.types import mysql_default, mysql_enum

_resume_document_format = mysql_enum(ResumeDocumentFormat, "resume_document_format")


class ResumeVersion(CoreBase):
    __tablename__ = "resume_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_id", "target_profile_id"],
            ["candidate_target_profiles.candidate_id", "candidate_target_profiles.id"],
            name="fk_resume_owned_target",
        ),
        UniqueConstraint("candidate_id", "current_scope", name="uq_resume_current_scope"),
        Index("ix_resume_owned_target", "candidate_id", "target_profile_id"),
        Index("ix_resume_session", "session_id"),
        Index("ix_resume_versions_candidate_id", "candidate_id"),
        Index("ix_resume_versions_candidate_is_current", "candidate_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=False
    )
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
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    target_profile_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)
    current_scope: Mapped[int | None] = mapped_column(
        BigInteger,
        Computed(
            "CASE WHEN is_current = 1 AND archived_at IS NULL THEN COALESCE(target_profile_id, 0) ELSE NULL END",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
