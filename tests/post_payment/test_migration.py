import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def test_domain_migration_is_reversible_and_contains_deduplication_keys():
    path = Path(__file__).parents[2] / "migrations/core/versions/0036_domain_delivery.py"
    spec = importlib.util.spec_from_file_location("domain_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = inspect(connection)
        assert len(inspector.get_table_names()) == 5
        assert inspector.get_pk_constraint("domain_inbox")["constrained_columns"] == [
            "consumer",
            "event_id",
        ]
        assert inspector.get_pk_constraint("application_authorizations")["constrained_columns"] == [
            "candidate_id",
            "job_id",
        ]
        migration.downgrade()
        assert inspect(connection).get_table_names() == []
    engine.dispose()
