"""Private answer history is additive, deduplicated and removed with its account."""

import importlib.util
import io
import re
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from scaffold.models import ApplicationAnswerCache


def load_migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/core/versions/0056_application_answer_cache.py"
    )
    spec = importlib.util.spec_from_file_location("application_answer_cache_0056", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_sqlite_unique_cache_and_account_cascade():
    with create_engine("sqlite://").connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        for parent in ("candidates", "job_applications", "resume_versions"):
            connection.execute(text(f"CREATE TABLE {parent} (id INTEGER PRIMARY KEY)"))
            connection.execute(text(f"INSERT INTO {parent} VALUES (1)"))
        with Operations.context(MigrationContext.configure(connection)):
            load_migration().upgrade()
        assert {
            c["name"] for c in inspect(connection).get_columns("application_answer_cache")
        } == set(ApplicationAnswerCache.__table__.columns.keys())
        statement = text(
            "INSERT INTO application_answer_cache (cache_key,candidate_id,application_id,resume_version_id,context_hash,question_contract_hash,question_id,answer) VALUES (:key,1,1,1,:context,:contract,'language',:answer)"
        )
        data = {
            "key": "a" * 64,
            "context": "b" * 64,
            "contract": "c" * 64,
            "answer": '{"value":"python","source":"explicit_application_answer","provenance":"fact"}',
        }
        connection.execute(statement, data)
        with pytest.raises(IntegrityError):
            connection.execute(statement, data)
        connection.execute(text("DELETE FROM candidates WHERE id=1"))
        assert connection.scalar(text("SELECT count(*) FROM application_answer_cache")) == 0


def test_migration_mysql_ddl_and_constraint_names():
    output = io.StringIO()
    with Operations.context(
        MigrationContext.configure(
            dialect_name="mysql", opts={"as_sql": True, "output_buffer": output}
        )
    ):
        load_migration().upgrade()
    for sql in (
        output.getvalue(),
        str(CreateTable(ApplicationAnswerCache.__table__).compile(dialect=mysql.dialect())),
    ):
        assert "answer JSON NOT NULL" in sql
        assert "ON DELETE CASCADE" in sql
        assert "PRIMARY KEY (cache_key)" in sql
        for name in re.findall(r"(?:CONSTRAINT|INDEX)\s+`?([a-zA-Z0-9_]+)`?", sql):
            assert len(name) <= 64, name
