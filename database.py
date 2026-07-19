import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine_instance: AsyncEngine | None = None
_session_factory_instance: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine_instance, _session_factory_instance
    if _engine_instance is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL environment variable must be set")
        _engine_instance = create_async_engine(url, echo=False)
        _session_factory_instance = async_sessionmaker(
            _engine_instance, expire_on_commit=False
        )
    return _engine_instance


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _get_engine()
    assert _session_factory_instance is not None
    async with _session_factory_instance() as session:
        yield session


async def engine_health_check() -> bool:
    try:
        eng = _get_engine()
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def close_engine() -> None:
    global _engine_instance, _session_factory_instance
    if _engine_instance is not None:
        await _engine_instance.dispose()
        _engine_instance = None
        _session_factory_instance = None
