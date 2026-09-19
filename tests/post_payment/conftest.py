"""Local, real SQL transactions. No external service or production credentials."""

import importlib
from pathlib import Path
import sys

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from scaffold.base import CoreBase
import scaffold.models  # noqa: F401 - registers metadata


@compiles(ENUM, "sqlite")
def enum_sqlite(type_, compiler, **kw):
    return "VARCHAR(255)"


@compiles(BigInteger, "sqlite")
def bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


ROOT = Path(__file__).resolve().parents[3]


def service(repo, module):
    for name in list(sys.modules):
        if name == "src" or name.startswith("src."):
            del sys.modules[name]
    sys.path.insert(0, str(ROOT / repo))
    try:
        return importlib.import_module(module)
    finally:
        sys.path.pop(0)


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(CoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def load_service():
    return service
