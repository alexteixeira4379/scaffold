from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from scaffold.config import get_settings
from scaffold.db.mysql_url import ensure_mysql_utf8mb4_charset

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _async_database_url(url: str) -> str:
    raw = url.strip()
    if raw.startswith("mysql+asyncmy://") or raw.startswith("mysql+aiomysql://"):
        out = raw
    elif raw.startswith("mysql+pymysql://"):
        out = "mysql+asyncmy://" + raw.removeprefix("mysql+pymysql://")
    elif raw.startswith("mysql://"):
        out = "mysql+asyncmy://" + raw.removeprefix("mysql://")
    else:
        return raw
    return ensure_mysql_utf8mb4_charset(out)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = _async_database_url(str(settings.database_url))
        _engine = create_async_engine(
            db_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=settings.db_pool_pre_ping,
            echo=settings.db_echo,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def close_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
