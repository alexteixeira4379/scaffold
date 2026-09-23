from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv
from scaffold.models.dashboard_types import UNSIGNED_REVISION, mysql_ddl_only

from scaffold.base import CoreBase
from scaffold.constants.schema_enums import ResumeProfileSource
from scaffold.db.types import mysql_enum

_resume_profile_source = mysql_enum(ResumeProfileSource, "resume_profile_source")


class ResumeProfile(CoreBase):
    __tablename__ = "resume_profiles"
    __table_args__ = (
        UniqueConstraint("candidate_id"),
        CheckConstraint("revision >= 1", name=conv("ck_resume_revision")),
        CheckConstraint(
            "reviewed_sections IS NULL OR JSON_TYPE(reviewed_sections) = 'ARRAY'",
            name=conv("ck_resume_reviewed_array"),
            _create_rule=mysql_ddl_only,
        ).ddl_if(dialect="mysql"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_sections: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    skills: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    revision: Mapped[int] = mapped_column(UNSIGNED_REVISION, nullable=False, server_default="1")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    source: Mapped[ResumeProfileSource] = mapped_column(_resume_profile_source, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
