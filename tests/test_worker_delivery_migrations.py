"""Rehearse only the incremental worker migrations on isolated MySQL."""
import hashlib
import importlib.util
import os
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from scaffold.models.domain_delivery import DomainOutbox


@pytest.mark.asyncio
@pytest.mark.parametrize("original_collation", ["utf8mb4_bin", "utf8mb3_unicode_ci"])
async def test_incremental_migrations_preserve_column_attributes_and_large_payload(original_collation):
    url = os.getenv("TEST_WORKER_DATABASE_URL")
    if not url:
        pytest.skip("requires isolated localhost MySQL TEST_WORKER_DATABASE_URL")
    target = make_url(url)
    assert target.host in {"localhost", "127.0.0.1"} and target.database.endswith("_test")
    engine = create_async_engine(url)
    metadata = sa.MetaData()
    old = sa.Table("domain_outbox", metadata, *(column._copy() for column in DomainOutbox.__table__.columns
                   if column.name not in {"headers", "raw_body", "claim_token", "claimed_until", "quarantined_at"}))
    sa.Index("ix_domain_outbox_ready", old.c.source, old.c.delivered_at, old.c.available_at, old.c.id)
    sa.Table("domain_inbox", metadata, sa.Column("consumer", sa.String(64), primary_key=True),
             sa.Column("event_id", sa.String(64), primary_key=True), sa.Column("processed_at", sa.DateTime()))
    from sqlalchemy.dialects.mysql import TEXT
    sa.Table("jobs", metadata, sa.Column("id", sa.Integer(), primary_key=True),
             sa.Column("description", TEXT(collation=original_collation), nullable=False, comment="preserve this comment"))
    directory = Path(__file__).parents[1] / "migrations/core/versions"

    def migrate(connection):
        metadata.create_all(connection)
        connection.execute(metadata.tables["jobs"].insert().values(id=2, description="Experiência anterior"))
        with Operations.context(MigrationContext.configure(connection)):
            for name in ("0062_worker_delivery", "0063_job_description_capacity", "0064_job_content_observation"):
                spec = importlib.util.spec_from_file_location(name, directory / f"{name}.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.upgrade()
                with pytest.raises(RuntimeError):
                    module.downgrade()
        columns = {column["name"]: column for column in sa.inspect(connection).get_columns("jobs")}
        description = columns["description"]
        assert description["type"].__class__.__name__ == "MEDIUMTEXT"
        assert description["nullable"] is False and description["comment"] == "preserve this comment"
        assert description["type"].collation == original_collation.replace("utf8mb3_", "utf8mb4_")
        assert "content_observed_at" in columns
        assert {"raw_body", "headers", "claim_token", "claimed_until"} <= {
            column["name"] for column in sa.inspect(connection).get_columns(old.name)}
        ready = next(index for index in sa.inspect(connection).get_indexes(old.name)
                     if index["name"] == "ix_domain_outbox_ready")
        assert ready["column_names"] == ["source", "delivered_at", "quarantined_at", "available_at", "id"]
        reflected = sa.MetaData()
        reflected.reflect(connection)
        text = "Engenharia 😀 " * 10000
        connection.execute(reflected.tables["jobs"].insert().values(id=1, description=text))
        assert connection.scalar(sa.select(reflected.tables["jobs"].c.description).where(reflected.tables["jobs"].c.id == 1)) == text
        assert connection.scalar(sa.select(reflected.tables["jobs"].c.description).where(reflected.tables["jobs"].c.id == 2)) == "Experiência anterior"
        # MEDIUMBLOB would fail at this exact boundary, even though a default
        # RabbitMQ message of this size can reach the quarantine path.
        raw = b"x" * (16 * 1024 * 1024)
        connection.execute(reflected.tables["worker_quarantine"].insert().values(
            id="boundary-test", consumer="test", event_id="test", queue="test",
            reason="size_boundary", attempts=1, payload_sha256=hashlib.sha256(raw).hexdigest(),
            raw_body=raw, created_at=datetime.utcnow(),
        ))
        assert connection.scalar(sa.select(sa.func.length(reflected.tables["worker_quarantine"].c.raw_body))) == len(raw)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(migrate)
    finally:
        async with engine.begin() as connection:
            def clean(conn):
                remaining = sa.MetaData()
                remaining.reflect(conn)
                remaining.drop_all(conn)
            await connection.run_sync(clean)
        await engine.dispose()
