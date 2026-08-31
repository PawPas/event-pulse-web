import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import database as _db_module  # noqa: E402
from database import get_db  # noqa: E402
from main import app  # noqa: E402
from models import event, report, user  # noqa: E402, F401 — registers models on Base.metadata
from models.base import Base  # noqa: E402


@pytest.fixture(scope="module")
def test_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    # Pre-inject the test engine so both the app lifespan and background tasks
    # (which call get_session_factory() directly, bypassing Depends) use the
    # same StaticPool SQLite connection as request-scoped sessions.
    # See context/foundation/lessons.md: "Pre-inject test engine when background
    # tasks bypass FastAPI DI" for why this is required.
    _db_module._engine_instance = engine
    _db_module._session_factory_instance = session_factory

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

    # Lifespan shutdown already called close_engine() which disposed the engine
    # and reset _engine_instance/_session_factory_instance to None.
    # Dispose again is a safe no-op.
    async def _teardown():
        await engine.dispose()

    asyncio.run(_teardown())
