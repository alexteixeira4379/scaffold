"""Migration 0052 regression on a disposable, dedicated MySQL database."""

import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url


def test_0052_preserves_existing_intent_and_unique_identity():
    raw = os.getenv("SCAFFOLD_MIGRATION_TEST_MYSQL_URL")
    if not raw:
        pytest.skip("requires disposable SCAFFOLD_MIGRATION_TEST_MYSQL_URL")
    url = make_url(raw)
    assert url.host in {"127.0.0.1", "localhost"} and url.database == "migration_regression"
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    old = sa.Table(
        "ats_executions", metadata,
        sa.Column("application_id", sa.BigInteger, primary_key=True),
        sa.Column("candidate_id", sa.BigInteger, nullable=False),
        sa.Column("job_id", sa.BigInteger, nullable=False),
        sa.Column("run_id", sa.BigInteger, nullable=False),
        sa.Column("resume_version_id", sa.BigInteger, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("owner", sa.String(36), nullable=False),
        sa.Column("lease_until", sa.DateTime, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("checkpoint", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON),
        sa.Column("intent_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_ats_execution_identity"),
    )
    module_path = Path(__file__).resolve().parents[2] / "migrations/core/versions/0052_application_execution_channels.py"
    spec = importlib.util.spec_from_file_location("migration_0052_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.begin() as connection:
            metadata.drop_all(connection, checkfirst=True)
            metadata.create_all(connection)
            connection.execute(old.insert().values(
                application_id=1, candidate_id=2, job_id=3, run_id=4, resume_version_id=55,
                provider="teamtailor", state="uncertain", owner="old-owner",
                lease_until="2026-10-05 03:00:00", attempts=1, checkpoint={"step": "submit"},
                result={"outcome": "uncertain"}, intent_at="2026-10-05 02:00:00",
            ))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
            row = connection.execute(sa.text(
                "SELECT provider, executor, fence_version, state, intent_at, result FROM ats_executions WHERE application_id=1"
            )).one()
            assert row.provider == "teamtailor" and row.executor == "ats" and row.fence_version == 1
            assert row.state == "uncertain" and row.intent_at is not None
            assert '"outcome": "uncertain"' in row.result
            indexes = sa.inspect(connection).get_unique_constraints("ats_executions")
            assert any(item["name"] == "uq_ats_execution_identity" for item in indexes)
    finally:
        with engine.begin() as connection:
            metadata.drop_all(connection, checkfirst=True)
        engine.dispose()
