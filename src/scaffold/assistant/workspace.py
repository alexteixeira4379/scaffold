"""Durable workspace shared by the assistant worker and its HTTP ingress."""

from sqlalchemy import BigInteger, Column, Index, Integer, JSON, MetaData, String, Table

metadata = MetaData()
tasks = Table(
    "assistant_tasks",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("conversation_id", String(64), nullable=False),
    Column("status", String(24), nullable=False),
    Column("objective", String(1000), nullable=False),
    Column("state", JSON, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Column("updated_at", BigInteger, nullable=False),
    Index("ix_assistant_tasks_conversation", "conversation_id", "updated_at"),
)
sources = Table(
    "assistant_sources",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("conversation_id", String(64), nullable=False),
    Column("message_id", String(64)),
    Column("kind", String(32), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("content", JSON, nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Index("ix_assistant_sources_conversation", "conversation_id", "created_at"),
)
artifact_versions = Table(
    "assistant_artifact_versions",
    metadata,
    Column("artifact_id", String(64), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("conversation_id", String(64), nullable=False),
    Column("task_id", String(64), nullable=False),
    Column("message_id", String(64), nullable=False),
    Column("title", String(160), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("content", JSON, nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Index("ix_assistant_artifacts_conversation", "conversation_id", "created_at"),
)
runs = Table(
    "assistant_runs",
    metadata,
    Column("message_id", String(64), primary_key=True),
    Column("conversation_id", String(64), nullable=False),
    Column("status", String(24), nullable=False),
    Column("stage", String(64), nullable=False),
    Column("checkpoint", JSON, nullable=False),
    Column("metrics", JSON, nullable=False),
    Column("updated_at", BigInteger, nullable=False),
    Index("ix_assistant_runs_conversation", "conversation_id", "updated_at"),
)
