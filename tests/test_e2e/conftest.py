"""
E2E test fixtures.

Provides:
- Class-scoped DB session and HTTP client (state persists across tests within a class)
- SSE event parser utility
- qdrant.zip loader
- Real LLM API key detection and skip marker
"""
import json
import os
from contextlib import asynccontextmanager
from typing import List

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.database import Base, get_db

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import api_router

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_sse_events(text: str) -> List[dict]:
    """Parse SSE text into a list of JSON event dicts.

    Each SSE line looks like ``data: {...}\\n`` with blank lines between events.
    """
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ---------------------------------------------------------------------------
# Skip marker for tests that require a real Anthropic API key
# ---------------------------------------------------------------------------

_REAL_API_KEY = os.environ.get("ANTHROPIC_API_KEY_REAL", "")

skip_no_api_key = pytest.mark.skipif(
    not _REAL_API_KEY,
    reason="ANTHROPIC_API_KEY_REAL not set",
)


# ---------------------------------------------------------------------------
# Test app factory (same as root conftest but extracted for clarity)
# ---------------------------------------------------------------------------

def _create_test_app() -> FastAPI:
    """Create a FastAPI app for testing WITHOUT lifespan."""

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        yield

    app = FastAPI(title="Skills API", version="1.0.0", lifespan=test_lifespan)

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


# ---------------------------------------------------------------------------
# Class-scoped database session — shared across all tests in a class
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def e2e_db_session():
    """Provide a single DB session for an entire test class.

    Tables are created once at class start and dropped at class end,
    allowing tests within the class to share state.
    """
    from app.db import models  # noqa: F401 — register models with Base

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def e2e_client(e2e_db_session: AsyncSession):
    """Provide an AsyncClient bound to a class-scoped DB session."""
    application = _create_test_app()

    async def override_get_db():
        yield e2e_db_session

    application.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Real-LLM client (uses actual Anthropic API key)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def real_client(e2e_db_session: AsyncSession):
    """Provide an AsyncClient that patches ANTHROPIC_API_KEY with the real key."""
    application = _create_test_app()

    async def override_get_db():
        yield e2e_db_session

    application.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# qdrant.zip fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qdrant_zip_bytes():
    """Load the qdrant.zip test fixture."""
    zip_path = os.path.join(
        os.path.dirname(__file__), "..", "test_files", "qdrant.zip"
    )
    with open(zip_path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Session factories for background tasks (evolve) — point to test DB
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="class", loop_scope="class")
async def e2e_session_factories(e2e_db_session):
    """Sync + async session factories pointing to the TEST database.

    Used by real-LLM tests that trigger background tasks (evolve)
    which internally use SyncSessionLocal/AsyncSessionLocal.
    """
    TEST_SYNC_URL = TEST_DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )

    sync_engine = create_engine(TEST_SYNC_URL, pool_size=5)
    sync_factory = sessionmaker(
        sync_engine, class_=Session, expire_on_commit=False
    )

    async_engine2 = create_async_engine(TEST_DATABASE_URL, pool_size=5)
    async_factory = async_sessionmaker(
        async_engine2, class_=AsyncSession, expire_on_commit=False
    )

    yield {"sync": sync_factory, "async": async_factory}

    sync_engine.dispose()
    await async_engine2.dispose()
