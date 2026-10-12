"""Canonical storage migration and stable identities, without a live database."""

import importlib.util
import io
import json
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from scaffold.candidate_information import legacy_seed


def migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/core/versions/0059_canonical_candidate_information.py"
    )
    spec = importlib.util.spec_from_file_location("canonical_0059", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sqlite_upgrade_normalizes_known_facts_without_new_enum_records():
    with create_engine("sqlite://").connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.execute(text("CREATE TABLE candidates (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO candidates VALUES (1),(2)"))
        conn.execute(
            text(
                "CREATE TABLE candidate_application_data (candidate_id INTEGER PRIMARY KEY,work_authorization TEXT,accessibility_resources TEXT,legal_information JSON)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE resume_profile_credentials (id INTEGER PRIMARY KEY,credential_type TEXT,nome TEXT)"
            )
        )
        doc = {
            "schema_version": 1,
            "work_permissions": [
                {
                    "country": "US",
                    "authorization": "no",
                    "sponsorship": "yes",
                    "valid_until": "2030-12-31",
                }
            ],
            "accommodations": {"requested": "yes", "details": "Existing support"},
            "context_notes": "Professional context",
            "professional_credentials": [{"name": "Existing certification"}],
            "declaration": {
                "source": "candidate_declared",
                "candidate_id": 1,
                "updated_at": "2026-10-11T10:00:00Z",
            },
        }
        conn.execute(
            text("INSERT INTO candidate_application_data VALUES (1,:old,:resources,:doc)"),
            {"old": "Yes-BR", "resources": "Existing support", "doc": json.dumps(doc)},
        )
        conn.execute(
            text("INSERT INTO candidate_application_data VALUES (2,:old,NULL,NULL)"), {"old": "Yes"}
        )
        with Operations.context(MigrationContext.configure(conn)):
            migration().upgrade()
        rows = conn.execute(
            text(
                "SELECT country,authorization,sponsorship,declaration_source FROM candidate_work_permissions ORDER BY country"
            )
        ).all()
        assert rows == [
            ("BR", "yes", "unknown", "legacy_explicit"),
            ("US", "no", "yes", "candidate_declared"),
        ]
        assert (
            conn.scalar(
                text(
                    "SELECT accommodation_requested FROM candidate_application_data WHERE candidate_id=1"
                )
            )
            == "yes"
        )
        assert (
            conn.scalar(
                text(
                    "SELECT accommodation_requested FROM candidate_application_data WHERE candidate_id=2"
                )
            )
            == "unknown"
        )
        assert (
            conn.scalar(
                text(
                    "SELECT information_source FROM candidate_application_data WHERE candidate_id=2"
                )
            )
            is None
        )
        assert conn.scalar(text("SELECT count(*) FROM resume_profile_credentials")) == 0
        assert (
            json.loads(
                conn.scalar(
                    text(
                        "SELECT legal_information FROM candidate_application_data WHERE candidate_id=1"
                    )
                )
            )
            == doc
        )
        conn.execute(text("DELETE FROM candidates WHERE id=1"))
        assert conn.scalar(text("SELECT count(*) FROM candidate_work_permissions")) == 0


def test_mysql_schema_has_safe_defaults_and_enum_expansion():
    output = io.StringIO()
    with Operations.context(
        MigrationContext.configure(
            dialect_name="mysql", opts={"as_sql": True, "output_buffer": output}
        )
    ):
        migration().upgrade()
    sql = output.getvalue()
    assert "DEFAULT 'unknown'" in sql
    assert "ENUM('course','certification','license','other')" in sql
    assert "ON DELETE CASCADE" in sql
    assert "valid_until DATE" in sql
    assert "declared_at DATETIME(6)" in sql
    assert "INSERT" not in sql


def test_unknown_legacy_defaults_do_not_override_scoped_fact_or_support():
    doc = {
        "schema_version": 1,
        "work_permissions": [],
        "accommodations": {"requested": "unknown", "details": None},
        "context_notes": "Only notes changed",
        "declaration": {
            "source": "candidate_declared",
            "candidate_id": 1,
            "updated_at": "2026-10-11T10:00:00Z",
        },
    }
    updates, rows = legacy_seed(
        {
            "candidate_id": 1,
            "work_authorization": "Yes-BR",
            "accessibility_resources": "Known support",
            "legal_information": doc,
        }
    )
    assert "work_permissions_adopted" not in updates
    assert rows[0]["authorization"] == "yes"
    assert "accessibility_resources" not in updates
