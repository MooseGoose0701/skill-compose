"""
Backup & Restore API - Full system backup and restore.

Backup scope: All DB tables (except ExecutorDB, BackgroundTaskDB) + disk files (skills/, config/) + .env
Restore mode: Clear all existing data first, auto-snapshot before restore for safety.
"""

import base64
import io
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select as sa_select, delete as sa_delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import (
    SkillDB,
    SkillVersionDB,
    SkillFileDB,
    SkillTestDB,
    SkillChangelogDB,
    AgentPresetDB,
    AgentTraceDB,
    PublishedSessionDB,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["backup"])

# ============ Constants ============

BACKUP_VERSION = "1.0"
TRACE_BATCH_SIZE = 500

# File filtering (reuse logic from system.py)
SKIP_PATTERNS = {"__pycache__", ".pyc", ".backup", "UPDATE_REPORT"}
MAX_FILE_SIZE = 1024 * 1024  # 1MB


def _should_skip_file(path: Path) -> bool:
    """Check if a file should be skipped during backup."""
    name = path.name
    path_str = str(path)
    if name.startswith("."):
        return True
    for pattern in SKIP_PATTERNS:
        if pattern in path_str or name.endswith(pattern):
            return True
    return False


def _get_backups_dir() -> Path:
    """Get and ensure backups directory exists."""
    backups_dir = Path(settings.backups_dir).resolve()
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


# ============ Response Models ============


class BackupStats(BaseModel):
    skills: int = 0
    skill_versions: int = 0
    skill_files: int = 0
    skill_tests: int = 0
    skill_changelogs: int = 0
    agent_presets: int = 0
    agent_traces: int = 0
    published_sessions: int = 0


class BackupListItem(BaseModel):
    filename: str
    size_bytes: int
    created_at: str
    backup_version: Optional[str] = None
    stats: Optional[BackupStats] = None


class BackupListResponse(BaseModel):
    backups: List[BackupListItem]
    total: int


class RestoreResponse(BaseModel):
    success: bool
    message: str
    snapshot_filename: Optional[str] = None
    restored: BackupStats
    errors: List[str]


# ============ Internal Helpers ============


def _serialize_datetime(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


async def _create_backup_zip(
    db: AsyncSession,
    include_env: bool = True,
    filename_prefix: str = "backup",
) -> tuple[io.BytesIO, BackupStats, str]:
    """Create a backup ZIP archive. Returns (zip_buffer, stats, filename)."""

    stats = BackupStats()

    # 1. Query all DB tables

    # Skills
    result = await db.execute(sa_select(SkillDB).order_by(SkillDB.name))
    skills = result.scalars().all()
    skills_data = []
    for s in skills:
        skills_data.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "owner_id": s.owner_id,
            "current_version": s.current_version,
            "status": s.status,
            "skill_type": s.skill_type,
            "tags": s.tags,
            "icon_url": s.icon_url,
            "source": s.source,
            "author": s.author,
            "category": s.category,
            "is_pinned": s.is_pinned,
            "created_at": _serialize_datetime(s.created_at),
            "updated_at": _serialize_datetime(s.updated_at),
        })
    stats.skills = len(skills_data)

    # Skill Versions
    result = await db.execute(sa_select(SkillVersionDB).order_by(SkillVersionDB.created_at))
    versions = result.scalars().all()
    versions_data = []
    for v in versions:
        versions_data.append({
            "id": v.id,
            "skill_id": v.skill_id,
            "version": v.version,
            "parent_version": v.parent_version,
            "skill_md": v.skill_md,
            "schema_json": v.schema_json,
            "manifest_json": v.manifest_json,
            "extra_metadata": v.extra_metadata,
            "commit_message": v.commit_message,
            "created_by": v.created_by,
            "created_at": _serialize_datetime(v.created_at),
        })
    stats.skill_versions = len(versions_data)

    # Skill Files (with base64 content)
    result = await db.execute(sa_select(SkillFileDB).order_by(SkillFileDB.created_at))
    files = result.scalars().all()
    files_data = []
    for f in files:
        content_b64 = ""
        if f.content:
            content_b64 = base64.b64encode(f.content).decode("utf-8")
        files_data.append({
            "id": f.id,
            "version_id": f.version_id,
            "file_path": f.file_path,
            "file_type": f.file_type,
            "content_hash": f.content_hash,
            "content_base64": content_b64,
            "storage_path": f.storage_path,
            "size_bytes": f.size_bytes,
            "created_at": _serialize_datetime(f.created_at),
        })
    stats.skill_files = len(files_data)

    # Skill Tests
    result = await db.execute(sa_select(SkillTestDB).order_by(SkillTestDB.created_at))
    tests = result.scalars().all()
    tests_data = []
    for t in tests:
        tests_data.append({
            "id": t.id,
            "version_id": t.version_id,
            "name": t.name,
            "description": t.description,
            "input_data": t.input_data,
            "expected_output": t.expected_output,
            "is_golden": t.is_golden,
            "created_at": _serialize_datetime(t.created_at),
        })
    stats.skill_tests = len(tests_data)

    # Skill Changelogs
    result = await db.execute(sa_select(SkillChangelogDB).order_by(SkillChangelogDB.changed_at))
    changelogs = result.scalars().all()
    changelogs_data = []
    for c in changelogs:
        changelogs_data.append({
            "id": c.id,
            "skill_id": c.skill_id,
            "version_from": c.version_from,
            "version_to": c.version_to,
            "change_type": c.change_type,
            "diff_content": c.diff_content,
            "changed_by": c.changed_by,
            "changed_at": _serialize_datetime(c.changed_at),
            "comment": c.comment,
        })
    stats.skill_changelogs = len(changelogs_data)

    # Agent Presets (ALL, including system)
    result = await db.execute(sa_select(AgentPresetDB).order_by(AgentPresetDB.name))
    presets = result.scalars().all()
    presets_data = []
    for p in presets:
        presets_data.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "system_prompt": p.system_prompt,
            "skill_ids": p.skill_ids,
            "mcp_servers": p.mcp_servers,
            "builtin_tools": p.builtin_tools,
            "max_turns": p.max_turns,
            "model_provider": p.model_provider,
            "model_name": p.model_name,
            "is_system": p.is_system,
            "is_published": p.is_published,
            "api_response_mode": p.api_response_mode,
            "executor_id": p.executor_id,
            "created_at": _serialize_datetime(p.created_at),
            "updated_at": _serialize_datetime(p.updated_at),
        })
    stats.agent_presets = len(presets_data)

    # Agent Traces (batched)
    traces_data = []
    offset = 0
    while True:
        result = await db.execute(
            sa_select(AgentTraceDB)
            .order_by(AgentTraceDB.created_at)
            .offset(offset)
            .limit(TRACE_BATCH_SIZE)
        )
        batch = result.scalars().all()
        if not batch:
            break
        for tr in batch:
            traces_data.append({
                "id": tr.id,
                "request": tr.request,
                "skills_used": tr.skills_used,
                "model_provider": tr.model_provider,
                "model": tr.model,
                "status": tr.status,
                "success": tr.success,
                "answer": tr.answer,
                "error": tr.error,
                "total_turns": tr.total_turns,
                "total_input_tokens": tr.total_input_tokens,
                "total_output_tokens": tr.total_output_tokens,
                "steps": tr.steps,
                "llm_calls": tr.llm_calls,
                "created_at": _serialize_datetime(tr.created_at),
                "duration_ms": tr.duration_ms,
                "session_id": tr.session_id,
            })
        offset += TRACE_BATCH_SIZE
    stats.agent_traces = len(traces_data)

    # Published Sessions
    result = await db.execute(sa_select(PublishedSessionDB).order_by(PublishedSessionDB.created_at))
    sessions = result.scalars().all()
    sessions_data = []
    for sess in sessions:
        sessions_data.append({
            "id": sess.id,
            "agent_id": sess.agent_id,
            "messages": sess.messages,
            "agent_context": sess.agent_context,
            "created_at": _serialize_datetime(sess.created_at),
            "updated_at": _serialize_datetime(sess.updated_at),
        })
    stats.published_sessions = len(sessions_data)

    # 2. Build manifest
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.zip"

    manifest = {
        "backup_version": BACKUP_VERSION,
        "created_at": datetime.utcnow().isoformat(),
        "stats": stats.model_dump(),
    }

    # 3. Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        # DB tables
        zf.writestr("db/skills.json", json.dumps(skills_data, ensure_ascii=False))
        zf.writestr("db/skill_versions.json", json.dumps(versions_data, ensure_ascii=False))
        zf.writestr("db/skill_files.json", json.dumps(files_data, ensure_ascii=False))
        zf.writestr("db/skill_tests.json", json.dumps(tests_data, ensure_ascii=False))
        zf.writestr("db/skill_changelogs.json", json.dumps(changelogs_data, ensure_ascii=False))
        zf.writestr("db/agent_presets.json", json.dumps(presets_data, ensure_ascii=False))
        zf.writestr("db/agent_traces.json", json.dumps(traces_data, ensure_ascii=False))
        zf.writestr("db/published_sessions.json", json.dumps(sessions_data, ensure_ascii=False))

        # Config files
        config_dir = Path(settings.config_dir).resolve()
        if config_dir.exists():
            for fp in config_dir.rglob("*"):
                if fp.is_file() and not _should_skip_file(fp):
                    try:
                        rel = fp.relative_to(config_dir)
                        zf.writestr(f"config/{rel}", fp.read_bytes())
                    except Exception:
                        pass

        # .env file
        if include_env:
            env_path = Path(".env").resolve()
            if env_path.exists():
                try:
                    zf.writestr("env/.env", env_path.read_bytes())
                except Exception:
                    pass

        # Skill files from disk
        skills_dir = Path(settings.effective_skills_dir).resolve()
        if skills_dir.exists():
            for fp in skills_dir.rglob("*"):
                if not fp.is_file():
                    continue
                if _should_skip_file(fp):
                    continue
                try:
                    if fp.stat().st_size > MAX_FILE_SIZE:
                        continue
                    rel = fp.relative_to(skills_dir)
                    zf.writestr(f"files/skills/{rel}", fp.read_bytes())
                except Exception:
                    pass

    zip_buffer.seek(0)
    return zip_buffer, stats, filename


async def _restore_from_zip(
    db: AsyncSession,
    zip_bytes: bytes,
) -> RestoreResponse:
    """Restore system from a backup ZIP. Creates auto-snapshot first."""
    errors: List[str] = []

    # Validate ZIP
    try:
        zip_buffer = io.BytesIO(zip_bytes)
        zf = zipfile.ZipFile(zip_buffer, "r")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")

    file_list = zf.namelist()
    if "manifest.json" not in file_list:
        zf.close()
        raise HTTPException(status_code=400, detail="Invalid backup: missing manifest.json")

    # Read manifest
    try:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    except Exception as e:
        zf.close()
        raise HTTPException(status_code=400, detail=f"Invalid manifest.json: {e}")

    backup_version = manifest.get("backup_version", "1.0")
    if backup_version not in ["1.0"]:
        zf.close()
        raise HTTPException(status_code=400, detail=f"Unsupported backup version: {backup_version}")

    # Auto-snapshot before restore
    snapshot_filename = None
    try:
        snap_buf, snap_stats, snap_fname = await _create_backup_zip(
            db, include_env=True, filename_prefix="pre_restore"
        )
        backups_dir = _get_backups_dir()
        snap_path = backups_dir / snap_fname
        snap_path.write_bytes(snap_buf.getvalue())
        snapshot_filename = snap_fname
        logger.info(f"Pre-restore snapshot saved: {snap_fname}")
    except Exception as e:
        errors.append(f"Warning: Failed to create pre-restore snapshot: {e}")
        logger.warning(f"Pre-restore snapshot failed: {e}")

    # Read all DB JSON files
    def _read_json(name: str) -> list:
        path = f"db/{name}"
        if path in file_list:
            try:
                return json.loads(zf.read(path).decode("utf-8"))
            except Exception as e:
                errors.append(f"Failed to read {path}: {e}")
        return []

    skills_data = _read_json("skills.json")
    versions_data = _read_json("skill_versions.json")
    files_data = _read_json("skill_files.json")
    tests_data = _read_json("skill_tests.json")
    changelogs_data = _read_json("skill_changelogs.json")
    presets_data = _read_json("agent_presets.json")
    traces_data = _read_json("agent_traces.json")
    sessions_data = _read_json("published_sessions.json")

    # Clear DB tables (children first due to FK constraints)
    try:
        await db.execute(sa_delete(PublishedSessionDB))
        await db.execute(sa_delete(AgentTraceDB))
        # SkillFileDB, SkillTestDB cascade from SkillVersionDB, which cascades from SkillDB
        # But SkillChangelogDB also has FK to SkillDB
        # Delete children explicitly for safety
        await db.execute(sa_delete(SkillFileDB))
        await db.execute(sa_delete(SkillTestDB))
        await db.execute(sa_delete(SkillChangelogDB))
        await db.execute(sa_delete(SkillVersionDB))
        # Nullify executor_id on presets before deleting presets
        await db.execute(
            sa_update(AgentPresetDB).values(executor_id=None)
        )
        await db.execute(sa_delete(AgentPresetDB))
        await db.execute(sa_delete(SkillDB))
        await db.flush()
    except Exception as e:
        await db.rollback()
        zf.close()
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {e}")

    # Insert DB records (parents first)
    restored = BackupStats()

    # Skills
    for s in skills_data:
        try:
            skill = SkillDB(
                id=s["id"],
                name=s["name"],
                description=s.get("description"),
                owner_id=s.get("owner_id"),
                current_version=s.get("current_version"),
                status=s.get("status", "draft"),
                skill_type=s.get("skill_type", "user"),
                tags=s.get("tags"),
                icon_url=s.get("icon_url"),
                source=s.get("source"),
                author=s.get("author"),
                category=s.get("category"),
                is_pinned=s.get("is_pinned", False),
                created_at=datetime.fromisoformat(s["created_at"]) if s.get("created_at") else datetime.utcnow(),
                updated_at=datetime.fromisoformat(s["updated_at"]) if s.get("updated_at") else datetime.utcnow(),
            )
            db.add(skill)
            restored.skills += 1
        except Exception as e:
            errors.append(f"Failed to restore skill '{s.get('name')}': {e}")

    await db.flush()

    # Skill Versions
    for v in versions_data:
        try:
            ver = SkillVersionDB(
                id=v["id"],
                skill_id=v["skill_id"],
                version=v["version"],
                parent_version=v.get("parent_version"),
                skill_md=v.get("skill_md"),
                schema_json=v.get("schema_json"),
                manifest_json=v.get("manifest_json"),
                extra_metadata=v.get("extra_metadata"),
                commit_message=v.get("commit_message"),
                created_by=v.get("created_by"),
                created_at=datetime.fromisoformat(v["created_at"]) if v.get("created_at") else datetime.utcnow(),
            )
            db.add(ver)
            restored.skill_versions += 1
        except Exception as e:
            errors.append(f"Failed to restore version '{v.get('id')}': {e}")

    await db.flush()

    # Skill Files
    for f in files_data:
        try:
            content = b""
            if f.get("content_base64"):
                content = base64.b64decode(f["content_base64"])
            file_record = SkillFileDB(
                id=f["id"],
                version_id=f["version_id"],
                file_path=f["file_path"],
                file_type=f.get("file_type", "other"),
                content_hash=f.get("content_hash"),
                content=content if content else None,
                storage_path=f.get("storage_path"),
                size_bytes=f.get("size_bytes"),
                created_at=datetime.fromisoformat(f["created_at"]) if f.get("created_at") else datetime.utcnow(),
            )
            db.add(file_record)
            restored.skill_files += 1
        except Exception as e:
            errors.append(f"Failed to restore file '{f.get('file_path')}': {e}")

    await db.flush()

    # Skill Tests
    for t in tests_data:
        try:
            test = SkillTestDB(
                id=t["id"],
                version_id=t["version_id"],
                name=t["name"],
                description=t.get("description"),
                input_data=t.get("input_data"),
                expected_output=t.get("expected_output"),
                is_golden=t.get("is_golden", False),
                created_at=datetime.fromisoformat(t["created_at"]) if t.get("created_at") else datetime.utcnow(),
            )
            db.add(test)
            restored.skill_tests += 1
        except Exception as e:
            errors.append(f"Failed to restore test '{t.get('name')}': {e}")

    await db.flush()

    # Skill Changelogs
    for c in changelogs_data:
        try:
            changelog = SkillChangelogDB(
                id=c["id"],
                skill_id=c["skill_id"],
                version_from=c.get("version_from"),
                version_to=c.get("version_to"),
                change_type=c["change_type"],
                diff_content=c.get("diff_content"),
                changed_by=c.get("changed_by"),
                changed_at=datetime.fromisoformat(c["changed_at"]) if c.get("changed_at") else datetime.utcnow(),
                comment=c.get("comment"),
            )
            db.add(changelog)
            restored.skill_changelogs += 1
        except Exception as e:
            errors.append(f"Failed to restore changelog '{c.get('id')}': {e}")

    await db.flush()

    # Agent Presets (executor_id set to None)
    for p in presets_data:
        try:
            preset = AgentPresetDB(
                id=p["id"],
                name=p["name"],
                description=p.get("description"),
                system_prompt=p.get("system_prompt"),
                skill_ids=p.get("skill_ids"),
                mcp_servers=p.get("mcp_servers"),
                builtin_tools=p.get("builtin_tools"),
                max_turns=p.get("max_turns", 60),
                model_provider=p.get("model_provider"),
                model_name=p.get("model_name"),
                is_system=p.get("is_system", False),
                is_published=p.get("is_published", False),
                api_response_mode=p.get("api_response_mode"),
                executor_id=None,
                created_at=datetime.fromisoformat(p["created_at"]) if p.get("created_at") else datetime.utcnow(),
                updated_at=datetime.fromisoformat(p["updated_at"]) if p.get("updated_at") else datetime.utcnow(),
            )
            db.add(preset)
            restored.agent_presets += 1
        except Exception as e:
            errors.append(f"Failed to restore preset '{p.get('name')}': {e}")

    await db.flush()

    # Agent Traces (batched inserts)
    for i, tr in enumerate(traces_data):
        try:
            trace = AgentTraceDB(
                id=tr["id"],
                request=tr["request"],
                skills_used=tr.get("skills_used"),
                model_provider=tr.get("model_provider"),
                model=tr["model"],
                status=tr.get("status", "completed"),
                success=tr["success"],
                answer=tr.get("answer"),
                error=tr.get("error"),
                total_turns=tr.get("total_turns", 0),
                total_input_tokens=tr.get("total_input_tokens", 0),
                total_output_tokens=tr.get("total_output_tokens", 0),
                steps=tr.get("steps"),
                llm_calls=tr.get("llm_calls"),
                created_at=datetime.fromisoformat(tr["created_at"]) if tr.get("created_at") else datetime.utcnow(),
                duration_ms=tr.get("duration_ms"),
                session_id=tr.get("session_id"),
            )
            db.add(trace)
            restored.agent_traces += 1
            if (i + 1) % TRACE_BATCH_SIZE == 0:
                await db.flush()
        except Exception as e:
            errors.append(f"Failed to restore trace '{tr.get('id')}': {e}")

    await db.flush()

    # Published Sessions
    for sess in sessions_data:
        try:
            session = PublishedSessionDB(
                id=sess["id"],
                agent_id=sess["agent_id"],
                messages=sess.get("messages"),
                agent_context=sess.get("agent_context"),
                created_at=datetime.fromisoformat(sess["created_at"]) if sess.get("created_at") else datetime.utcnow(),
                updated_at=datetime.fromisoformat(sess["updated_at"]) if sess.get("updated_at") else datetime.utcnow(),
            )
            db.add(session)
            restored.published_sessions += 1
        except Exception as e:
            errors.append(f"Failed to restore session '{sess.get('id')}': {e}")

    await db.commit()

    # Restore disk files
    # Clear skills directory
    skills_dir = Path(settings.effective_skills_dir).resolve()
    if skills_dir.exists():
        for child in skills_dir.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except Exception as e:
                errors.append(f"Failed to clear skill dir '{child.name}': {e}")

    # Extract files from ZIP
    for zip_path in file_list:
        if zip_path.endswith("/"):
            continue

        try:
            content = zf.read(zip_path)
        except Exception:
            continue

        if zip_path.startswith("files/skills/"):
            # Extract to skills directory
            rel = zip_path[len("files/skills/"):]
            if not rel:
                continue
            out_path = skills_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_bytes(content)
            except Exception as e:
                errors.append(f"Failed to write {zip_path}: {e}")

        elif zip_path.startswith("config/"):
            # Extract to config directory
            rel = zip_path[len("config/"):]
            if not rel:
                continue
            config_dir = Path(settings.config_dir).resolve()
            out_path = config_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_bytes(content)
            except Exception as e:
                errors.append(f"Failed to write {zip_path}: {e}")

        elif zip_path == "env/.env":
            # Restore .env file (may fail in Docker where .env is a read-only bind mount)
            env_path = Path(".env").resolve()
            try:
                env_path.write_bytes(content)
            except PermissionError:
                # Expected in Docker: .env is bind-mounted from host, skip silently
                logger.info("Skipped .env restore (read-only mount, typical in Docker)")
            except Exception as e:
                errors.append(f"Failed to restore .env: {e}")

    zf.close()

    return RestoreResponse(
        success=True,
        message=f"Restore completed. Restored {restored.skills} skills, {restored.agent_presets} agents, {restored.agent_traces} traces.",
        snapshot_filename=snapshot_filename,
        restored=restored,
        errors=errors,
    )


# ============ Endpoints ============


@router.post("/create")
async def create_backup(
    include_env: bool = Query(True, description="Include .env file in backup"),
    db: AsyncSession = Depends(get_db),
):
    """Create a full system backup.

    Exports all DB data (skills, versions, files, tests, changelogs, agents, traces, sessions)
    plus disk files (skills/, config/, .env) into a ZIP archive.

    The backup is saved to the backups directory and returned for download.
    """
    zip_buffer, stats, filename = await _create_backup_zip(db, include_env=include_env)

    # Save a copy to backups directory
    backups_dir = _get_backups_dir()
    backup_path = backups_dir / filename
    backup_path.write_bytes(zip_buffer.getvalue())
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/list", response_model=BackupListResponse)
async def list_backups():
    """List all available backups from the backups directory."""
    backups_dir = _get_backups_dir()
    items: List[BackupListItem] = []

    for fp in sorted(backups_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            stat = fp.stat()
            backup_version = None
            stats = None

            # Try to read manifest from ZIP
            try:
                with zipfile.ZipFile(fp, "r") as zf:
                    if "manifest.json" in zf.namelist():
                        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                        backup_version = manifest.get("backup_version")
                        if "stats" in manifest:
                            stats = BackupStats(**manifest["stats"])
            except Exception:
                pass

            items.append(BackupListItem(
                filename=fp.name,
                size_bytes=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                backup_version=backup_version,
                stats=stats,
            ))
        except Exception:
            pass

    return BackupListResponse(backups=items, total=len(items))


@router.get("/download/{filename}")
async def download_backup(filename: str):
    """Download a backup file from the backups directory."""
    # Path traversal protection
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backups_dir = _get_backups_dir()
    backup_path = backups_dir / filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    # Verify the resolved path is within backups_dir
    try:
        backup_path.resolve().relative_to(backups_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    return StreamingResponse(
        open(backup_path, "rb"),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/restore", response_model=RestoreResponse)
async def restore_from_upload(
    file: UploadFile = File(..., description="Backup ZIP file to restore"),
    db: AsyncSession = Depends(get_db),
):
    """Restore system from an uploaded backup ZIP file.

    This will:
    1. Create an auto-snapshot of current state
    2. Clear all existing DB data
    3. Restore all data from the backup
    4. Restore disk files (skills/, config/, .env)
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    content = await file.read()
    return await _restore_from_zip(db, content)


@router.post("/restore/{filename}", response_model=RestoreResponse)
async def restore_from_server(
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    """Restore system from a backup file stored on the server."""
    # Path traversal protection
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backups_dir = _get_backups_dir()
    backup_path = backups_dir / filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    try:
        backup_path.resolve().relative_to(backups_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    content = backup_path.read_bytes()
    return await _restore_from_zip(db, content)
