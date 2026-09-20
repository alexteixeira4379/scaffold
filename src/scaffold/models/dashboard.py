"""Persistent dashboard resources introduced by migration 0040."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    text,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv
from scaffold.models.dashboard_types import (
    DATETIME_6,
    UNSIGNED_REVISION,
    mysql_ddl_only,
    IDENTITY_CHANNEL,
    NOTIFICATION_CHANNEL,
    IDENTITY_VALUE,
    NOTIFICATION_TOPIC,
    CurrentTimestamp6,
)

from scaffold.base import CoreBase


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DATETIME_6, nullable=False, server_default=CurrentTimestamp6()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME_6, nullable=False, server_default=CurrentTimestamp6(), onupdate=CurrentTimestamp6()
    )


class AuthVerifiedIdentity(Timestamps, CoreBase):
    __tablename__ = "auth_verified_identities"
    __table_args__ = (
        UniqueConstraint("channel", "normalized_value", name="uq_auth_identity_channel_value"),
        UniqueConstraint("candidate_id", "channel", name="uq_auth_identity_candidate_channel"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id", name="fk_auth_identity_candidate"), nullable=False
    )
    channel: Mapped[str] = mapped_column(IDENTITY_CHANNEL, nullable=False)
    normalized_value: Mapped[str] = mapped_column(IDENTITY_VALUE, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DATETIME_6, nullable=False)


class CandidateNotificationPreference(Timestamps, CoreBase):
    __tablename__ = "candidate_notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "topic", "channel", name="uq_notification_candidate_topic_channel"
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidates.id", name="fk_notification_preference_candidate"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(NOTIFICATION_TOPIC, nullable=False)
    channel: Mapped[str] = mapped_column(NOTIFICATION_CHANNEL, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)


class JobCandidatePreference(Timestamps, CoreBase):
    __tablename__ = "job_candidate_preferences"
    __table_args__ = (
        Index("ix_job_preference_job", "job_id"),
        Index("ix_job_preference_saved", "candidate_id", "saved", "updated_at"),
        Index("ix_job_preference_dismissed", "candidate_id", "dismissed", "updated_at"),
    )
    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidates.id", name="fk_job_preference_candidate"),
        primary_key=True,
    )
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jobs.id", name="fk_job_preference_job"), primary_key=True
    )
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))


class ResumePersona(Timestamps, CoreBase):
    __tablename__ = "resume_personas"
    __table_args__ = (
        UniqueConstraint("target_profile_id", name="uq_resume_persona_target"),
        CheckConstraint("revision >= 1", name=conv("ck_persona_revision")),
        CheckConstraint(
            "JSON_TYPE(content) = 'OBJECT'",
            name=conv("ck_persona_content_object"),
            _create_rule=mysql_ddl_only,
        ).ddl_if(dialect="mysql"),
        Index("ix_persona_candidate_target", "candidate_id", "target_profile_id"),
        ForeignKeyConstraint(
            ["candidate_id", "target_profile_id"],
            ["candidate_target_profiles.candidate_id", "candidate_target_profiles.id"],
            name="fk_persona_owned_target",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.id", name="fk_persona_candidate"), nullable=False
    )
    target_profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(UNSIGNED_REVISION, nullable=False, server_default="1")
    source_updated_at: Mapped[datetime | None] = mapped_column(DATETIME_6, nullable=True)
