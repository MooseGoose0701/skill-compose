"""
Database connection management for Skill Registry.

Uses SQLAlchemy 2.0 async API with asyncpg for PostgreSQL.
"""

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _get_database_url() -> str:
    """Get the effective database URL from settings."""
    return settings.effective_database_url


def _get_sync_database_url() -> str:
    """Convert async database URL to sync (psycopg2) URL."""
    url = _get_database_url()
    # postgresql+asyncpg://... -> postgresql+psycopg2://...
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


# Get database URL
_db_url = _get_database_url()

# Create async engine with PostgreSQL connection pool settings
engine = create_async_engine(
    _db_url,
    echo=settings.database_echo,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,  # Verify connections before use (prevents stale connection errors after restart)
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine and session factory (for agent tools running in threads)
_sync_db_url = _get_sync_database_url()
sync_engine = create_engine(
    _sync_db_url,
    echo=settings.database_echo,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.

    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables.

    This creates all tables defined in the ORM models.
    Should be called on application startup.
    """
    # Import models to ensure they are registered with Base
    from app.db import models  # noqa: F401
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Run migrations for existing databases
    await _run_migrations()


async def _run_migrations():
    """
    Run simple migrations for PostgreSQL databases.
    Adds new columns that may be missing from older database versions.

    Uses PostgreSQL's DO block with exception handling to safely add columns
    (handles 'column already exists' gracefully).
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Safely add columns using DO blocks (ignores duplicate_column errors)
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE skills ADD COLUMN skill_type VARCHAR(32) DEFAULT 'user' NOT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE skills ADD COLUMN tools JSONB DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE skills ADD COLUMN tags JSONB DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE skills ADD COLUMN icon_url VARCHAR(512) DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        # Migrate existing 'system' skill_type to 'meta'
        await conn.execute(
            text("UPDATE skills SET skill_type = 'meta' WHERE skill_type = 'system'")
        )

        # Update meta skills based on config
        meta_skills = settings.meta_skills
        if meta_skills:
            placeholders = ", ".join(f"'{s}'" for s in meta_skills)
            await conn.execute(
                text(f"UPDATE skills SET skill_type = 'meta' WHERE name IN ({placeholders})")
            )

    # Migrate agent_presets table
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE agent_presets ADD COLUMN is_published BOOLEAN DEFAULT FALSE NOT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE agent_presets ADD COLUMN api_response_mode VARCHAR(32) DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        # Backward compatibility: set existing published agents to streaming
        await conn.execute(
            text("UPDATE agent_presets SET api_response_mode = 'streaming' WHERE is_published = TRUE AND api_response_mode IS NULL")
        )

    # Create published_sessions table if not exists
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS published_sessions (
                id VARCHAR(36) PRIMARY KEY,
                agent_id VARCHAR(36) NOT NULL,
                messages JSONB DEFAULT '[]',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_published_sessions_agent_id ON published_sessions (agent_id)"
        ))

    # Add agent_context column to published_sessions table
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE published_sessions ADD COLUMN agent_context JSONB DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

    # Add category and is_pinned columns to skills table
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE skills ADD COLUMN category VARCHAR(64) DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE skills ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE NOT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))

    # Add session_id column to agent_traces table
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE agent_traces ADD COLUMN session_id VARCHAR(36) DEFAULT NULL;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_agent_traces_session_id ON agent_traces (session_id)"
        ))

    # Ensure meta skills from filesystem are registered in the database
    await _ensure_meta_skills_registered()

    # Ensure seed agents are created
    await _ensure_seed_agents_exist()


async def _ensure_meta_skills_registered():
    """
    Ensure all skills from filesystem are registered in the database.
    This syncs filesystem-based skills to the registry on startup.

    - Meta skills (from config.meta_skills) are marked as 'meta' type
    - Other skills are marked as 'user' type
    - Creates skill_versions records with SKILL.md content for skills without versions
    - Applies seed metadata (category, source, author, is_pinned) from seed_skills.json
    """
    from sqlalchemy import text
    from datetime import datetime
    from pathlib import Path
    from app.core.skill_manager import find_all_skills
    import uuid

    meta_skill_names = set(settings.meta_skills)

    # Load seed skill metadata (category, source, author, is_pinned)
    seed_skills = _load_seed_skills()

    # Get ALL filesystem skills
    filesystem_skills = find_all_skills()

    if not filesystem_skills:
        return

    async with AsyncSessionLocal() as session:
        async with session.begin():
            for skill in filesystem_skills:
                # Determine skill type
                is_meta = skill.name in meta_skill_names
                skill_type = "meta" if is_meta else "user"
                skill_id = f"meta-{skill.name}" if is_meta else str(uuid.uuid4())

                # Get seed metadata for this skill
                seed = seed_skills.get(skill.name, {})

                # Check if skill exists in database
                result = await session.execute(
                    text("SELECT id, skill_type, current_version FROM skills WHERE name = :name"),
                    {"name": skill.name}
                )
                existing = result.fetchone()

                if not existing:
                    # Insert new skill with seed metadata
                    now = datetime.utcnow()
                    await session.execute(
                        text("""
                            INSERT INTO skills (id, name, description, status, skill_type, is_pinned, category, source, author, created_at, updated_at)
                            VALUES (:id, :name, :description, 'active', :skill_type, :is_pinned, :category, :source, :author, :created_at, :updated_at)
                        """),
                        {
                            "id": skill_id,
                            "name": skill.name,
                            "description": skill.description or f"Skill: {skill.name}",
                            "skill_type": skill_type,
                            "is_pinned": seed.get("is_pinned", False),
                            "category": seed.get("category"),
                            "source": seed.get("source"),
                            "author": seed.get("author"),
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                    # Create initial version with SKILL.md content
                    await _create_version_from_filesystem(session, skill_id, skill.path, now)
                else:
                    existing_id, existing_type, existing_version = existing
                    # Update skill_type if it changed (e.g., user -> meta)
                    if existing_type != skill_type:
                        await session.execute(
                            text("UPDATE skills SET skill_type = :skill_type WHERE name = :name"),
                            {"skill_type": skill_type, "name": skill.name}
                        )
                    # If skill has no version, create one from filesystem
                    if not existing_version:
                        await _create_version_from_filesystem(session, existing_id, skill.path, datetime.utcnow())


def _load_seed_skills() -> dict:
    """Load seed skill metadata from config/seed_skills.json."""
    from pathlib import Path
    import json

    for path in [
        Path(settings.config_dir) / "seed_skills.json",
        Path("config/seed_skills.json"),
    ]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("skills", {})
            except Exception as e:
                print(f"Warning: Failed to load seed_skills.json: {e}")
                return {}
    return {}


async def _create_version_from_filesystem(session, skill_id: str, skill_dir_path: str, now):
    """Create a skill_versions record from filesystem with all files (SKILL.md + scripts/ + references/ + assets/)."""
    from sqlalchemy import text
    from pathlib import Path
    import uuid
    import hashlib

    skill_dir = Path(skill_dir_path)
    skill_md_path = skill_dir / "SKILL.md"

    if not skill_md_path.exists():
        return

    try:
        skill_md_content = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return

    version = "0.0.1"
    version_id = str(uuid.uuid4())

    # Insert version record
    await session.execute(
        text("""
            INSERT INTO skill_versions (id, skill_id, version, skill_md, created_at, commit_message)
            VALUES (:id, :skill_id, :version, :skill_md, :created_at, :commit_message)
        """),
        {
            "id": version_id,
            "skill_id": skill_id,
            "version": version,
            "skill_md": skill_md_content,
            "created_at": now,
            "commit_message": "Initial version synced from filesystem",
        }
    )

    # Read and save all other files from skill directory
    skill_files = _read_skill_files_for_init(skill_dir)
    for file_path, (content, file_type, size) in skill_files.items():
        content_hash = hashlib.sha256(content).hexdigest()
        file_id = str(uuid.uuid4())
        await session.execute(
            text("""
                INSERT INTO skill_files (id, version_id, file_path, file_type, content, content_hash, size_bytes, created_at)
                VALUES (:id, :version_id, :file_path, :file_type, :content, :content_hash, :size_bytes, NOW())
            """),
            {
                "id": file_id,
                "version_id": version_id,
                "file_path": file_path,
                "file_type": file_type,
                "content": content,
                "content_hash": content_hash,
                "size_bytes": size,
            }
        )

    # Update skill's current_version
    await session.execute(
        text("UPDATE skills SET current_version = :version WHERE id = :id"),
        {"version": version, "id": skill_id}
    )


def _read_skill_files_for_init(skill_dir: Path) -> dict:
    """Read all files from a skill directory for initial registration.

    Returns dict of {relative_path: (content_bytes, file_type, size)}
    Skips SKILL.md (stored separately), binary artifacts, and files larger than 1MB.
    """
    files = {}
    max_size = 1024 * 1024  # 1MB limit

    # File type mapping based on directory
    type_mapping = {
        "scripts": "script",
        "references": "reference",
        "assets": "asset",
    }

    # Skip compiled/build artifacts only (not resource files like images, fonts, etc.)
    skip_extensions = {
        # Python compiled
        ".pyc", ".pyo", ".pyd",
        # Java compiled
        ".class",
        # C/C++ compiled
        ".o", ".a", ".so", ".dylib", ".dll", ".exe",
        # Other build artifacts
        ".wasm",
    }

    for file_path in skill_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip hidden files and common non-essential files
        if file_path.name.startswith(".") or file_path.name.endswith(".pyc"):
            continue
        if "__pycache__" in str(file_path):
            continue
        if file_path.name in ["SKILL.md"]:  # SKILL.md is stored separately
            continue
        if ".backup" in file_path.name or "UPDATE_REPORT" in file_path.name:
            continue

        # Skip compiled/build artifacts
        suffix = file_path.suffix.lower()
        if suffix in skip_extensions:
            continue

        # Skip large files
        try:
            size = file_path.stat().st_size
            if size > max_size:
                continue
        except OSError:
            continue

        # Determine file type
        rel_path = file_path.relative_to(skill_dir)
        parts = rel_path.parts
        file_type = "other"
        if parts and parts[0] in type_mapping:
            file_type = type_mapping[parts[0]]

        # Read file content (binary)
        try:
            content = file_path.read_bytes()
            files[str(rel_path)] = (content, file_type, size)
        except OSError:
            # Skip files that can't be read
            continue

    return files


async def _ensure_seed_agents_exist():
    """
    Ensure seed agents from config/seed_agents.json are registered in the database.
    This creates predefined system agents on startup if they don't exist.

    - Agents are matched by name (idempotent - skips if already exists)
    - Seed agents are marked as is_system=True to prevent user deletion
    """
    from sqlalchemy import text
    from datetime import datetime
    from pathlib import Path
    import json
    import uuid

    # Find seed_agents.json (check both local and Docker paths)
    seed_file = None
    for path in [
        Path("config/seed_agents.json"),
        Path("/app/config/seed_agents.json"),
    ]:
        if path.exists():
            seed_file = path
            break

    if not seed_file:
        return

    try:
        with open(seed_file, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load seed_agents.json: {e}")
        return

    agents = seed_data.get("agents", [])
    if not agents:
        return

    async with AsyncSessionLocal() as session:
        async with session.begin():
            for agent in agents:
                name = agent.get("name")
                if not name:
                    continue

                # Check if agent already exists
                result = await session.execute(
                    text("SELECT id FROM agent_presets WHERE name = :name"),
                    {"name": name}
                )
                existing = result.fetchone()

                if existing:
                    # Already exists, skip
                    continue

                # Insert new agent preset
                now = datetime.utcnow()
                agent_id = str(uuid.uuid4())

                # Convert lists to JSON strings for JSONB columns
                skill_ids = json.dumps(agent.get("skill_ids")) if agent.get("skill_ids") else None
                mcp_servers = json.dumps(agent.get("mcp_servers")) if agent.get("mcp_servers") else None
                builtin_tools = json.dumps(agent.get("builtin_tools")) if agent.get("builtin_tools") else None

                await session.execute(
                    text("""
                        INSERT INTO agent_presets (
                            id, name, description, system_prompt,
                            skill_ids, mcp_servers, builtin_tools,
                            max_turns, model_provider, model_name,
                            is_system, is_published, api_response_mode,
                            created_at, updated_at
                        ) VALUES (
                            :id, :name, :description, :system_prompt,
                            :skill_ids, :mcp_servers, :builtin_tools,
                            :max_turns, :model_provider, :model_name,
                            :is_system, :is_published, :api_response_mode,
                            :created_at, :updated_at
                        )
                    """),
                    {
                        "id": agent_id,
                        "name": name,
                        "description": agent.get("description"),
                        "system_prompt": agent.get("system_prompt"),
                        "skill_ids": skill_ids,
                        "mcp_servers": mcp_servers,
                        "builtin_tools": builtin_tools,
                        "max_turns": agent.get("max_turns", 60),
                        "model_provider": agent.get("model_provider"),
                        "model_name": agent.get("model_name"),
                        "is_system": agent.get("is_system", True),
                        "is_published": agent.get("is_published", False),
                        "api_response_mode": agent.get("api_response_mode"),
                        "created_at": now,
                        "updated_at": now,
                    }
                )


async def drop_db():
    """
    Drop all database tables.

    WARNING: This is destructive. Use only for testing.
    """
    from app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
