"""
Root test configuration.

Sets up:
- PostgreSQL test database (skills_api_test)
- AsyncClient for FastAPI testing
- Database session fixtures with per-test table creation/teardown
- Lifespan is skipped in tests (no init_db / filesystem sync)
"""
import os

# Set env vars before any app imports
os.environ["DATABASE_URL"] = "postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test"
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["AUTH_ENABLED"] = "false"

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Auto-create test database if it doesn't exist (runs once per session)
# ---------------------------------------------------------------------------
def _ensure_test_database():
    """Create skills_api_test database if missing.

    Uses psycopg2 (sync) to connect to the default 'postgres' database and
    create the test DB.  This runs before any async engine is created.
    """
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    conn = psycopg2.connect(
        host="localhost", port=62620, user="skills", password="skills123", dbname="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'skills_api_test'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE skills_api_test OWNER skills")
    cur.close()
    conn.close()


# Run at import time (before any fixture or test)
_ensure_test_database()

# NOW safe to import app modules
from contextlib import asynccontextmanager

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from app.db.database import Base, get_db

# We import create_app components instead of using create_app() directly,
# because create_app() attaches lifespan that calls init_db() which does
# PostgreSQL migrations and filesystem scanning we don't want in tests.
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import api_router

TEST_DATABASE_URL = "postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test"


def _create_test_app() -> FastAPI:
    """Create a FastAPI app for testing WITHOUT lifespan (no init_db)."""

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        # No-op lifespan for tests - tables are managed by fixtures
        yield

    app = FastAPI(
        title="Skills API",
        version="1.0.0",
        lifespan=test_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/")
    async def root():
        return {
            "name": "Skills API",
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": {
                "skills": "/api/v1/skills",
                "execute": "/api/v1/execute",
                "files": "/api/v1/files",
                "registry": "/api/v1/registry",
            },
        }

    return app


@pytest_asyncio.fixture()
async def db_session():
    """Provide a database session with fresh tables per test.

    Creates a new engine per test to avoid event loop conflicts
    with pytest-asyncio's per-test event loop.
    """
    from app.db import models  # noqa: F401 - register models with Base

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )()
    try:
        yield session
    finally:
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture(autouse=True)
def _bypass_api_key_validation():
    """Skip API key validation in all tests (keys are not on disk)."""
    from unittest.mock import patch
    with patch("app.api.v1.agent._validate_api_key"):
        yield


@pytest_asyncio.fixture()
async def app(db_session: AsyncSession):
    """Create a test FastAPI app with database override."""
    application = _create_test_app()

    async def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest_asyncio.fixture()
async def client(app):
    """Provide an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
