"""Shared fixtures for API/DB tests using in-memory SQLite."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from starlette.testclient import TestClient

from tests.helpers import BOT_SECRET

JWT_SECRET = "test-jwt-secret-32-characters-min!!"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)


@compiles(PGUUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("INTERNAL_BOT_SECRET", BOT_SECRET)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings

    get_settings.cache_clear()
    from app.services import security as security_mod

    security_mod._encryption = None
    yield
    get_settings.cache_clear()


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from app.database import Base
    import app.models  # noqa: F401 — register models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(auth_env, db_engine):
    from app.database import get_db
    from app.main import create_app

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
