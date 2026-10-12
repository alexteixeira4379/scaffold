import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from scaffold.models.application.answers_logs import AnswersLog


def test_migration_matches_the_writer_model_and_preserves_indexes():
    path = Path(__file__).resolve().parents[2] / "migrations/core/versions/0060_answers_logs.py"
    spec = importlib.util.spec_from_file_location("answers_logs_migration", path.resolve())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "0059"
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        inspector = inspect(connection)
        columns = inspector.get_columns("answers_logs")
        assert {column["name"] for column in columns} == set(AnswersLog.__table__.columns.keys())
        assert {index["name"] for index in inspector.get_indexes("answers_logs")} == {
            index.name for index in AnswersLog.__table__.indexes
        }
        assert all(not column["nullable"] for column in columns if column["name"] != "correlation_id")
    engine.dispose()
