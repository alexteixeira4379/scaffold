from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ResumeStepInputType

_resume_step_input_type = mysql_enum(ResumeStepInputType, "resume_step_input_type")


class ResumeBuildStep(CoreBase):
    __tablename__ = "resume_build_steps"
    __table_args__ = (
        UniqueConstraint("step_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    step_label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_type: Mapped[ResumeStepInputType] = mapped_column(
        _resume_step_input_type,
        nullable=False,
        server_default=mysql_default("resume_step_input_type", ResumeStepInputType.TEXT),
    )
    options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
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
