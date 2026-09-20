"""Opt-in, disposable MySQL test; never accepts a supplied database URL.

RUN_DASHBOARD_MYSQL_TESTS=1 PYTHONPATH=src .venv/bin/pytest \
    tests/integration/test_dashboard_migration_mysql.py -v

Creates its own Docker network/container, replays all historical migrations,
then exercises 0040. No production credentials or existing DBs are used.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, OperationalError

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/core/versions/0040_dashboard_persistence.py"
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DASHBOARD_MYSQL_TESTS") != "1",
    reason="Explicit opt-in required to start disposable MySQL",
)


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def load_migration():
    spec = importlib.util.spec_from_file_location("dashboard_migration_0040", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(connection):
    result = {}
    for table in sa.inspect(connection).get_table_names():
        ddl = connection.exec_driver_sql(f"SHOW CREATE TABLE `{table}`").one()[1]
        # SHOW CREATE orders indexes by creation time; restoring an implicit
        # FK index may move its line without changing any schema definition.
        ddl = re.sub(r" AUTO_INCREMENT=\d+", "", ddl)
        result[table] = sorted(line.rstrip(",") for line in ddl.splitlines())
    return result


def alembic(url, *args, check=True):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.core.ini", *args],
        cwd=ROOT,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(ROOT / "src"),
            "DATABASE_URL": url,
            "DATABASE_URL_SYNC": url,
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    if check:
        assert result.returncode == 0, result.stdout
    return result


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    name = f"jobito-dashboard-mysql-test-{uuid4().hex[:10]}"
    network = f"{name}-network"
    evidence = tmp_path_factory.mktemp("dashboard-migration-evidence")
    engine = None
    image = os.environ.get("DASHBOARD_MYSQL_IMAGE", "mysql:8.0")
    if image not in {"mysql:8.0", "mysql:9.4"}:
        raise ValueError("Only the reviewed MySQL test images are allowed")
    docker("network", "create", "--internal", network)
    try:
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--network",
            network,
            "--tmpfs",
            "/var/lib/mysql",
            "-e",
            "MYSQL_ROOT_PASSWORD=isolated-test-only",
            "-e",
            "MYSQL_DATABASE=dashboard_migration_test",
            image,
            "--character-set-server=utf8mb4",
            "--collation-server=utf8mb4_0900_ai_ci",
        )
        details = json.loads(docker("inspect", name))[0]
        host = details["NetworkSettings"]["Networks"][network]["IPAddress"]
        url = f"mysql+pymysql://root:isolated-test-only@{host}:3306/dashboard_migration_test?charset=utf8mb4"
        engine = sa.create_engine(url, connect_args={"connect_timeout": 2})
        deadline = time.monotonic() + 60
        while True:
            try:
                with engine.connect() as connection:
                    version = connection.exec_driver_sql("SELECT VERSION()").scalar_one()
                break
            except OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.3)
        bootstrap = alembic(url, "upgrade", "0039")
        (evidence / "bootstrap.log").write_text(bootstrap.stdout)
        with engine.begin() as connection:
            for candidate in (900001, 900002):
                connection.exec_driver_sql(
                    "INSERT INTO candidates (id, full_name, email) VALUES (%s, %s, %s)",
                    (candidate, f"Controlled candidate {candidate}", f"{candidate}@example.test"),
                )
                connection.exec_driver_sql(
                    "INSERT INTO candidate_preferences (candidate_id) VALUES (%s)", (candidate,)
                )
                connection.exec_driver_sql(
                    "INSERT INTO candidate_target_profiles (id,candidate_id,name,is_default) VALUES (%s,%s,'Target',1)",
                    (candidate, candidate),
                )
                connection.exec_driver_sql(
                    "INSERT INTO resume_profiles (candidate_id,summary,source) VALUES (%s,'Existing summary','direct_api')",
                    (candidate,),
                )
            connection.exec_driver_sql(
                "INSERT INTO jobs (id,title) VALUES (900001,'Controlled job')"
            )
            connection.exec_driver_sql(
                "INSERT INTO resume_build_sessions (id,candidate_id) VALUES (900001,900001)"
            )
            connection.exec_driver_sql(
                "INSERT INTO resume_versions (id,candidate_id,session_id,version_number,is_current,content,storage_url) "
                "VALUES (900001,900001,900001,1,1,'Legacy current','https://example.test/current.pdf'),"
                "(900002,900001,900001,0,0,'Legacy historical','https://example.test/history.pdf')"
            )
            baseline = snapshot(connection)
            originals = {
                table: list(
                    connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").mappings()
                )
                for table in (
                    "candidates",
                    "candidate_preferences",
                    "candidate_target_profiles",
                    "resume_profiles",
                    "resume_versions",
                )
            }
        yield {
            "url": url,
            "engine": engine,
            "baseline": baseline,
            "originals": originals,
            "evidence": evidence,
            "version": version,
            "image": details["Image"],
        }
    finally:
        if engine is not None:
            engine.dispose()
        subprocess.run(["docker", "rm", "--force", name], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)


def test_01_conflicts_stop_before_any_ddl(database):
    engine, url = database["engine"], database["url"]
    scenarios = [
        (
            "INSERT INTO resume_versions (id,candidate_id,is_current) VALUES (990001,900001,1)",
            "multiple current resumes",
            "DELETE FROM resume_versions WHERE id=990001",
        ),
        (
            "INSERT INTO candidate_target_profiles (id,candidate_id,name,is_default) VALUES (990001,900001,'Duplicate',1)",
            "multiple primary targets",
            "DELETE FROM candidate_target_profiles WHERE id=990001",
        ),
    ]
    for insert, expected, cleanup in scenarios:
        with engine.begin() as connection:
            connection.exec_driver_sql(insert)
        result = alembic(url, "upgrade", "0040", check=False)
        assert result.returncode != 0 and expected in result.stdout
        with engine.begin() as connection:
            assert snapshot(connection) == database["baseline"]
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == "0039"
            )
            connection.exec_driver_sql(cleanup)
    # Simulates legacy corruption, strictly on the disposable test DB.
    with engine.begin() as connection:
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        connection.exec_driver_sql(
            "INSERT INTO resume_versions (id,candidate_id) VALUES (990001,999999)"
        )
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
    result = alembic(url, "upgrade", "0040", check=False)
    assert result.returncode != 0 and "orphan candidate in resume_versions" in result.stdout
    with engine.begin() as connection:
        assert snapshot(connection) == database["baseline"]
        connection.exec_driver_sql("DELETE FROM resume_versions WHERE id=990001")


def test_02_partial_application_is_reported_without_stamping(database):
    migration = load_migration()
    with database["engine"].begin() as connection:
        connection.exec_driver_sql(migration.UPGRADE_SQL[0])
    result = alembic(database["url"], "upgrade", "0040", check=False)
    assert result.returncode != 0 and "existing/partial objects" in result.stdout
    with database["engine"].begin() as connection:
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0039"
        )
        assert (
            connection.exec_driver_sql("SELECT COUNT(*) FROM auth_verified_identities").scalar_one()
            == 0
        )
        # Explicit recovery of the sole completed DDL, with no writes to discard.
        connection.exec_driver_sql("DROP TABLE auth_verified_identities")
        assert snapshot(connection) == database["baseline"]


@pytest.fixture(scope="module")
def upgraded(database):
    result = alembic(database["url"], "upgrade", "0040")
    (database["evidence"] / "upgrade.log").write_text(result.stdout)
    with database["engine"].connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0040"
        )
        database["upgraded_schema"] = snapshot(connection)
        (database["evidence"] / "schema.json").write_text(
            json.dumps(database["upgraded_schema"], indent=2)
        )
    return database


@pytest.fixture
def connection(upgraded):
    with upgraded["engine"].connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def test_03_existing_values_defaults_and_no_implicit_verification(connection, upgraded):
    for table, rows in upgraded["originals"].items():
        current = list(connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").mappings())
        assert [{key: row[key] for key in rows[0]} for row in current] == [
            dict(row) for row in rows
        ]
    for table in load_migration().NEW_TABLES:
        assert connection.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one() == 0
    for row in connection.exec_driver_sql(
        "SELECT revision,reviewed_sections,headline,portfolio_url FROM resume_profiles"
    ).all():
        assert tuple(row) == (1, None, None, None)
    assert (
        connection.exec_driver_sql(
            "SELECT reviewed_at FROM candidate_preferences LIMIT 1"
        ).scalar_one()
        is None
    )
    assert (
        connection.exec_driver_sql(
            "SELECT current_scope FROM resume_versions WHERE id=900001"
        ).scalar_one()
        == 0
    )
    assert (
        connection.exec_driver_sql(
            "SELECT current_scope FROM resume_versions WHERE id=900002"
        ).scalar_one()
        is None
    )


def reject(connection, statement, params=()):
    with pytest.raises((IntegrityError, OperationalError)) as error:
        connection.exec_driver_sql(statement, params)
    assert error.value.orig.args[0] in (1062, 1452, 3819), str(error.value)


def test_04_verified_identity_uniqueness(connection):
    insert = "INSERT INTO auth_verified_identities (candidate_id,channel,normalized_value,verified_at) VALUES (%s,%s,%s,NOW())"
    connection.exec_driver_sql(insert, (900001, "email", "verified@example.test"))
    reject(connection, insert, (900002, "email", "verified@example.test"))
    reject(connection, insert, (900001, "email", "other@example.test"))
    connection.exec_driver_sql(insert, (900001, "whatsapp", "+5511999990001"))
    reject(connection, insert, (999999, "email", "orphan@example.test"))


def test_05_preference_keys_and_foreign_keys(connection):
    connection.exec_driver_sql(
        "INSERT INTO candidate_notification_preferences (candidate_id,topic,channel,enabled) VALUES (900001,'weekly_digest','email',0)"
    )
    reject(
        connection,
        "INSERT INTO candidate_notification_preferences (candidate_id,topic,channel,enabled) VALUES (900001,'weekly_digest','email',1)",
    )
    connection.exec_driver_sql(
        "INSERT INTO candidate_notification_preferences (candidate_id,topic,channel,enabled) VALUES (900001,'weekly_digest','whatsapp',1)"
    )
    connection.exec_driver_sql(
        "INSERT INTO job_candidate_preferences (candidate_id,job_id) VALUES (900001,900001)"
    )
    assert tuple(
        connection.exec_driver_sql("SELECT saved,dismissed FROM job_candidate_preferences").one()
    ) == (0, 0)
    reject(
        connection,
        "INSERT INTO job_candidate_preferences (candidate_id,job_id) VALUES (900001,900001)",
    )
    reject(
        connection,
        "INSERT INTO job_candidate_preferences (candidate_id,job_id) VALUES (900002,999999)",
    )
    connection.exec_driver_sql(
        "INSERT INTO job_candidate_preferences (candidate_id,job_id,saved) VALUES (900002,900001,1)"
    )


def test_06_persona_owner_uniqueness_and_snapshot_preservation(connection):
    insert = (
        "INSERT INTO resume_personas (candidate_id,target_profile_id,content) VALUES (%s,%s,%s)"
    )
    reject(connection, insert, (900001, 900002, "{}"))
    connection.exec_driver_sql(insert, (900001, 900001, '{"summary":"Independent snapshot"}'))
    reject(connection, insert, (900001, 900001, "{}"))
    assert tuple(
        connection.exec_driver_sql("SELECT enabled,revision FROM resume_personas").one()
    ) == (0, 1)
    connection.exec_driver_sql(
        "UPDATE resume_profiles SET summary='Changed main' WHERE candidate_id=900001"
    )
    connection.exec_driver_sql("UPDATE resume_personas SET enabled=1")
    connection.exec_driver_sql("UPDATE resume_personas SET enabled=0")
    assert json.loads(
        connection.exec_driver_sql("SELECT content FROM resume_personas").scalar_one()
    ) == {"summary": "Independent snapshot"}
    reject(connection, "UPDATE resume_personas SET revision=0")
    # MySQL reports CHECK violations as OperationalError (3819), not IntegrityError.


def test_07_json_checks_and_revision_checks(connection):
    for query in (
        "UPDATE resume_profiles SET revision=0 WHERE candidate_id=900001",
        "UPDATE resume_profiles SET reviewed_sections=JSON_OBJECT() WHERE candidate_id=900001",
        "INSERT INTO resume_personas (candidate_id,target_profile_id,content) VALUES (900001,900001,JSON_ARRAY())",
    ):
        with pytest.raises((IntegrityError, OperationalError)):
            connection.exec_driver_sql(query)
    connection.exec_driver_sql(
        "UPDATE resume_profiles SET reviewed_sections=JSON_ARRAY('experiences','education') WHERE candidate_id=900001"
    )


def test_08_current_documents_are_unique_per_owned_scope_and_keep_history(connection):
    insert = (
        "INSERT INTO resume_versions (candidate_id,target_profile_id,is_current) VALUES (%s,%s,1)"
    )
    reject(connection, insert, (900001, None))
    reject(connection, insert, (900001, 900002))
    connection.exec_driver_sql(insert, (900001, 900001))
    reject(connection, insert, (900001, 900001))
    connection.exec_driver_sql(
        "UPDATE resume_versions SET archived_at=NOW() WHERE target_profile_id=900001"
    )
    connection.exec_driver_sql(insert, (900001, 900001))
    connection.exec_driver_sql(
        "INSERT INTO resume_versions (candidate_id,target_profile_id,is_current) VALUES (900001,900001,0),(900001,900001,0)"
    )
    assert (
        connection.exec_driver_sql(
            "SELECT COUNT(*) FROM resume_versions WHERE archived_at IS NOT NULL"
        ).scalar_one()
        == 1
    )
    assert (
        connection.exec_driver_sql(
            "SELECT storage_url FROM resume_versions WHERE id=900001"
        ).scalar_one()
        == "https://example.test/current.pdf"
    )
    assert (
        connection.exec_driver_sql(
            "SELECT COUNT(*) FROM resume_versions WHERE candidate_id=900002"
        ).scalar_one()
        == 0
    )


def test_09_concurrent_current_document_inserts_have_one_winner(upgraded):
    barrier = Barrier(2)

    def insert():
        with upgraded["engine"].connect() as connection:
            barrier.wait(timeout=10)
            try:
                connection.exec_driver_sql(
                    "INSERT INTO resume_versions (candidate_id,target_profile_id,is_current) VALUES (900002,900002,1)"
                )
                connection.commit()
                return "created"
            except IntegrityError:
                connection.rollback()
                return "duplicate"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: insert(), range(2)))
        assert sorted(results) == ["created", "duplicate"]
    finally:
        with upgraded["engine"].begin() as connection:
            connection.exec_driver_sql("DELETE FROM resume_versions WHERE candidate_id=900002")


def test_10_optimistic_revision_update_has_one_winner(upgraded):
    barrier = Barrier(2)

    def update():
        with upgraded["engine"].begin() as connection:
            barrier.wait(timeout=10)
            return connection.exec_driver_sql(
                "UPDATE resume_profiles SET revision=revision+1 WHERE candidate_id=900002 AND revision=1"
            ).rowcount

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: update(), range(2)))
        assert sorted(results) == [0, 1]
    finally:
        with upgraded["engine"].begin() as connection:
            connection.exec_driver_sql(
                "UPDATE resume_profiles SET revision=1 WHERE candidate_id=900002"
            )


def test_11_downgrade_restores_baseline_and_upgrade_repeats(upgraded):
    result = alembic(upgraded["url"], "downgrade", "0039")
    (upgraded["evidence"] / "downgrade.log").write_text(result.stdout)
    with upgraded["engine"].connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0039"
        )
        assert snapshot(connection) == upgraded["baseline"]
    alembic(upgraded["url"], "upgrade", "0040")
    with upgraded["engine"].connect() as connection:
        assert snapshot(connection) == upgraded["upgraded_schema"]
    evidence = {
        "mysql": upgraded["version"],
        "image": upgraded["image"],
        "migration_sha256": hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
        "baseline": "0039",
        "final_revision": "0040",
    }
    (upgraded["evidence"] / "result.json").write_text(json.dumps(evidence, indent=2))
    print(f"\nEvidence: {upgraded['evidence']}\n{json.dumps(evidence)}")
