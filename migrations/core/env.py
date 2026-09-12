from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import scaffold.models  # noqa: F401, E402
from scaffold.base import CoreBase  # noqa: E402

alembic_cfg = context.config
target_metadata = CoreBase.metadata

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url="mysql://offline",
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_name="mysql",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:
    from scaffold.config import get_settings

    settings = get_settings()
    url = str(settings.database_url_sync)
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations()
