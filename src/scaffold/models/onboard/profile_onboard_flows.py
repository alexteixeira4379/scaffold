from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ProfileOnboardFlowStatus

_profile_onboard_flow_status = mysql_enum(ProfileOnboardFlowStatus, "profile_onboard_flow_status")


class ProfileOnboardFlow(CoreBase):
    __tablename__ = "profile_onboard_flows"
    __table_args__ = (
        Index("ix_profile_onboard_flows_profile_id", "profile_id"),
        Index("ix_profile_onboard_flows_candidate_id", "candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(191), nullable=False)
    candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidates.id"), nullable=True
    )
    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("onboard_flows.id"), nullable=False)
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[ProfileOnboardFlowStatus] = mapped_column(
        _profile_onboard_flow_status,
        nullable=False,
        server_default=mysql_default("profile_onboard_flow_status", ProfileOnboardFlowStatus.IN_PROGRESS),
    )
    current_step_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
