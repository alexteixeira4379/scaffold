from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from scaffold.base import CoreBase
from scaffold.db.types import mysql_default, mysql_enum
from scaffold.constants.schema_enums import ApplicationMessageStatus, MessageChannel, MessageType

_application_message_status = mysql_enum(ApplicationMessageStatus, "application_message_status")
_message_channel = mysql_enum(MessageChannel, "message_channel")
_message_type = mysql_enum(MessageType, "message_type")


class ApplicationMessage(CoreBase):
    __tablename__ = "application_messages"
    __table_args__ = (
        Index("ix_application_messages_job_application_id", "job_application_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_application_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_applications.id"), nullable=False
    )
    channel: Mapped[MessageChannel] = mapped_column(_message_channel, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(_message_type, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApplicationMessageStatus] = mapped_column(
        _application_message_status,
        nullable=False,
        server_default=mysql_default(
            "application_message_status", ApplicationMessageStatus.PENDING
        ),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
