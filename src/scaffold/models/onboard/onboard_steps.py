from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import OnboardPhase, OnboardStepLayoutKind

_onboard_phase = mysql_enum(OnboardPhase, "onboard_phase")
_onboard_step_layout_kind = mysql_enum(OnboardStepLayoutKind, "onboard_step_layout_kind")


class OnboardStep(CoreBase):
    __tablename__ = "onboard_steps"
    __table_args__ = (
        UniqueConstraint("step_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phase: Mapped[OnboardPhase] = mapped_column(
        _onboard_phase,
        nullable=False,
        server_default=mysql_default("onboard_phase", OnboardPhase.BASE_PROFILE),
    )
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    layout_kind: Mapped[OnboardStepLayoutKind] = mapped_column(
        _onboard_step_layout_kind,
        nullable=False,
        server_default=mysql_default("onboard_step_layout_kind", OnboardStepLayoutKind.TEXT),
    )
    layout_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    accepted_answers: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    answer_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
