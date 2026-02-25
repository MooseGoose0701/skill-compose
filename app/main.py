"""
Skill Composer API

A Python REST API service that provides autonomous AI agents
with composable, evolvable skills using Claude LLM.

Usage:
    uvicorn app.main:app --reload

API Docs:
    http://localhost:8000/docs
"""
import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.api.v1.router import api_router
from app.db.database import init_db, AsyncSessionLocal

logger = logging.getLogger("skills_api")


def _cleanup_old_workspaces():
    """Remove workspace directories older than 24 hours on startup.

    After the cleanup() change that preserves workspace_dir for output file
    downloads, this reaper prevents unbounded disk growth.
    """
    import shutil
    import time
    from pathlib import Path

    workspaces_dir = Path(os.environ.get("WORKSPACES_DIR", "/app/workspaces"))
    if not workspaces_dir.exists():
        return

    cutoff = time.time() - 24 * 3600
    removed = 0
    for entry in workspaces_dir.iterdir():
        if entry.is_dir():
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"Cleaned up {removed} old workspace(s) from {workspaces_dir}")


async def _cleanup_stale_traces():
    """Mark orphaned 'running' traces as failed on startup.

    When the API container is killed mid-stream, the event_generator's finally
    block never executes, leaving traces stuck in 'running' status forever.
    """
    from sqlalchemy import update
    from app.db.models import AgentTraceDB

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(AgentTraceDB)
            .where(AgentTraceDB.status == "running")
            .values(
                status="failed",
                success=False,
                error="Server restarted while agent was running",
            )
            .returning(AgentTraceDB.id)
        )
        stale_ids = [row[0] for row in result.fetchall()]
        await session.commit()
        if stale_ids:
            logger.info(f"Cleaned up {len(stale_ids)} stale running traces: {stale_ids}")


async def _warmup_worker():
    """Warmup this worker by executing common database queries.

    This ensures the database connection pool is established and
    SQLAlchemy query compilation is done before user requests arrive.
    Covers all main pages: skills, agents, tools, mcp, traces, executors, files, environment.
    """
    from sqlalchemy import text

    try:
        async with AsyncSessionLocal() as session:
            # Skills page queries
            await session.execute(text("SELECT id, name, description, skill_type, tags FROM skills LIMIT 1"))
            await session.execute(text("SELECT DISTINCT jsonb_array_elements_text(tags) FROM skills WHERE tags IS NOT NULL LIMIT 1"))

            # Agents page query
            await session.execute(text("SELECT id, name, description, is_system, is_published FROM agent_presets LIMIT 1"))

            # Traces page query
            await session.execute(text("SELECT id, skills_used, status, created_at FROM agent_traces ORDER BY created_at DESC LIMIT 1"))

            # Executors page query
            await session.execute(text("SELECT id, name, is_builtin FROM executors LIMIT 1"))

            logger.info("Worker warmup completed - DB connections established")
    except Exception as e:
        logger.warning(f"Worker warmup query failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup: Initialize database (normally done by entrypoint.sh before workers start)
    try:
        await init_db()
    except Exception as e:
        # Log error but don't fail - entrypoint.sh should have initialized already
        logger.error(f"Database init failed (entrypoint.sh should have initialized): {e}")
    await _cleanup_stale_traces()
    _cleanup_old_workspaces()

    # Warmup this worker's database connections
    await _warmup_worker()

    yield
    # Shutdown: Nothing to clean up for now


# Public path prefixes that bypass auth
_PUBLIC_PATHS = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/status",
    "/api/v1/published/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Global JWT authentication middleware.

    Skips authentication for:
    - OPTIONS requests (CORS preflight)
    - Public paths (login, refresh, status, published agents, docs)
    - When AUTH_ENABLED=false
    """

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # Skip if auth disabled
        if not settings.auth_enabled:
            return await call_next(request)

        # Skip CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip public paths
        path = request.url.path
        if path == "/" or any(path.startswith(p) for p in _PUBLIC_PATHS):
            return await call_next(request)

        # Validate JWT
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        token = auth_header[7:]  # Strip "Bearer "
        try:
            from app.services.auth_service import decode_token
            payload = decode_token(token, settings.effective_jwt_secret)
            if payload.get("type") != "access":
                raise ValueError("Invalid token type")
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # Store user info in request state
        request.state.user_id = payload.get("sub")
        request.state.username = payload.get("username")
        request.state.role = payload.get("role")

        return await call_next(request)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Skills API",
        description="Skill Composer - Build autonomous AI agents with composable skills",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth middleware (applied after CORS so preflight works)
    app.add_middleware(AuthMiddleware)

    # Global exception handler for debugging
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.method} {request.url.path}:\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    # Routes
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


app = create_app()
