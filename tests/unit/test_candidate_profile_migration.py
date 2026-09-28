"""Exercise the additive migration on existing rows without external databases."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_additive_migration_preserves_old_values_and_allows_new_facts():
    path = (
        Path(__file__).parents[2] / "migrations/core/versions/0051_candidate_application_profile.py"
    )
    spec = importlib.util.spec_from_file_location("candidate_profile_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("candidate_preferences", "candidate_target_profiles"):
            connection.exec_driver_sql(
                f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, min_salary NUMERIC, remote_preference VARCHAR(20), employment_preference VARCHAR(20))"
            )
            connection.exec_driver_sql(
                f"INSERT INTO {table} VALUES (1, 8500.75, 'remote', 'full_time')"
            )
        connection.exec_driver_sql(
            "CREATE TABLE candidate_application_data (id INTEGER PRIMARY KEY, gender VARCHAR(50), disability_status VARCHAR(50))"
        )
        connection.exec_driver_sql(
            "INSERT INTO candidate_application_data VALUES (1, 'Mulher', NULL)"
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        for table in ("candidate_preferences", "candidate_target_profiles"):
            row = connection.exec_driver_sql(f"SELECT * FROM {table}").mappings().one()
            assert row["remote_preference"] == "remote"
            assert row["employment_preference"] == "full_time"
            assert row["min_salary"] == 8500.75
            assert row["remote_preferences"] is None
        connection.exec_driver_sql(
            "UPDATE candidate_application_data SET cpf='52998224725', race_color='prefer_not_to_answer'"
        )
        row = (
            connection.exec_driver_sql("SELECT * FROM candidate_application_data").mappings().one()
        )
        assert row["gender"] == "Mulher"
        assert row["cpf"] == "52998224725"
        assert row["race_color"] == "prefer_not_to_answer"
