"""
Registry API - Skill Registry endpoints for Phase 1.

Provides REST API for:
- Skill CRUD operations
- Version management
- Changelog access
- Skill validation
"""

import base64
import hashlib
import io
import os
import re
import zipfile
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, SyncSessionLocal
from app.db.models import SkillDB, AgentTraceDB
from app.config import settings
from app.services.skill_service import (
    SkillService,
    SkillNotFoundError,
    SkillAlreadyExistsError,
    VersionNotFoundError,
    VersionAlreadyExistsError,
    ValidationError,
)
from app.services.task_manager import task_manager, TaskStatus
from app.models.package import (
    CreateSkillRequest,
    UpdateSkillRequest,
    CreateVersionRequest,
    RollbackRequest,
    SkillResponse,
    SkillListResponse,
    VersionResponse,
    VersionListResponse,
    ChangelogListResponse,
)


# Evolve request/response models
class EvolveViaTracesRequest(BaseModel):
    trace_ids: Optional[List[str]] = None
    feedback: Optional[str] = None


class EvolveTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
from app.core.schema_validator import ValidationResult, SchemaValidator
from app.core.skill_manager import find_all_skills, find_skill

router = APIRouter(prefix="/registry", tags=["registry"])


# Task response models
class CreateSkillTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    skill_name: Optional[str] = None
    new_version: Optional[str] = None
    trace_id: Optional[str] = None
    error: Optional[str] = None


# Exception handlers
def handle_service_error(error: Exception) -> HTTPException:
    """Convert service errors to HTTP exceptions."""
    if isinstance(error, SkillNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, SkillAlreadyExistsError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, VersionNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, VersionAlreadyExistsError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ValidationError):
        return HTTPException(status_code=400, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


# Skill endpoints

@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    status: Optional[str] = Query(None, description="Filter by status (draft, active, deprecated)"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by (OR match)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query("updated_at", description="Sort field: name, updated_at, created_at"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
):
    """List all skills with optional filtering and sorting."""
    # Parse comma-separated tags
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else None
    # Validate sort_by
    if sort_by not in ("name", "updated_at", "created_at"):
        sort_by = "updated_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    service = SkillService(db)
    return await service.list_skills(
        status=status, tags=tag_list, category=category,
        sort_by=sort_by, sort_order=sort_order,
        offset=offset, limit=limit,
    )


@router.get("/tags", response_model=List[str])
async def list_tags(
    db: AsyncSession = Depends(get_db),
):
    """Get all unique tags across all skills."""
    from app.repositories.skill_repo import SkillRepository
    repo = SkillRepository(db)
    return await repo.get_all_tags()


@router.get("/categories", response_model=List[str])
async def list_categories(
    db: AsyncSession = Depends(get_db),
):
    """Get all unique categories across all skills."""
    from app.repositories.skill_repo import SkillRepository
    repo = SkillRepository(db)
    return await repo.get_all_categories()


class TogglePinResponse(BaseModel):
    name: str
    is_pinned: bool


@router.post("/skills/{name}/toggle-pin", response_model=TogglePinResponse)
async def toggle_pin(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Toggle the pinned state of a skill."""
    from app.repositories.skill_repo import SkillRepository
    repo = SkillRepository(db)
    skill = await repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    new_pinned = not skill.is_pinned
    await repo.update(skill.id, is_pinned=new_pinned)
    await db.commit()
    return TogglePinResponse(name=name, is_pinned=new_pinned)


# Unregistered skills detection and import

class UnregisteredSkillInfo(BaseModel):
    name: str
    description: Optional[str] = None
    path: str
    skill_type: str


class UnregisteredSkillsResponse(BaseModel):
    skills: List[UnregisteredSkillInfo]
    total: int


class ImportLocalRequest(BaseModel):
    skill_names: List[str]


class ImportLocalResultItem(BaseModel):
    name: str
    success: bool
    version: Optional[str] = None
    error: Optional[str] = None


class ImportLocalResponse(BaseModel):
    results: List[ImportLocalResultItem]
    total_imported: int
    total_failed: int


@router.get("/unregistered-skills", response_model=UnregisteredSkillsResponse)
async def list_unregistered_skills(
    db: AsyncSession = Depends(get_db),
):
    """Detect skills on disk that are not registered in the database."""
    # Get all skills from disk
    disk_skills = find_all_skills()

    # Get all registered skill names from DB
    result = await db.execute(sa_select(SkillDB.name))
    registered_names = {row[0] for row in result.all()}

    # Find unregistered skills
    unregistered = []
    for skill in disk_skills:
        if skill.name not in registered_names:
            unregistered.append(UnregisteredSkillInfo(
                name=skill.name,
                description=skill.description or None,
                path=skill.path,
                skill_type=skill.skill_type,
            ))

    return UnregisteredSkillsResponse(skills=unregistered, total=len(unregistered))


@router.post("/import-local", response_model=ImportLocalResponse)
async def import_local_skills(
    request: ImportLocalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import local skills from disk into the database."""
    results: List[ImportLocalResultItem] = []
    total_imported = 0
    total_failed = 0

    service = SkillService(db)

    for skill_name in request.skill_names:
        try:
            # Check if already registered
            if await service.skill_repo.exists(skill_name):
                results.append(ImportLocalResultItem(
                    name=skill_name, success=False, error="Already registered"
                ))
                total_failed += 1
                continue

            # Find skill on disk
            location = find_skill(skill_name)
            if not location:
                results.append(ImportLocalResultItem(
                    name=skill_name, success=False, error="Not found on disk"
                ))
                total_failed += 1
                continue

            skill_dir = Path(location.base_dir)
            skill_md_path = skill_dir / "SKILL.md"
            if not skill_md_path.exists():
                results.append(ImportLocalResultItem(
                    name=skill_name, success=False, error="SKILL.md not found"
                ))
                total_failed += 1
                continue

            skill_md_content = skill_md_path.read_text(encoding="utf-8")

            # Extract description from frontmatter
            description = None
            match = re.search(r'^description:\s*(.+)$', skill_md_content, re.MULTILINE)
            if match:
                description = match.group(1).strip()

            # Determine skill type
            settings_obj = settings
            skill_type = "meta" if skill_name in settings_obj.meta_skills else "user"

            # Read other files
            skill_files, _ = _read_skill_files(skill_dir)

            # Create skill in DB
            skill = await service.skill_repo.create(
                name=skill_name,
                description=description,
                owner_id=None,
                status="draft",
                skill_type=skill_type,
            )

            # Add changelog
            await service.skill_repo.add_changelog(
                skill_id=skill.id,
                change_type="import",
                version_to=None,
                changed_by=None,
                comment=f"Imported from local disk",
            )

            # Create initial version
            initial_version = "0.0.1"
            ver = await service.version_repo.create(
                skill_id=skill.id,
                version=initial_version,
                skill_md=skill_md_content,
                schema_json=None,
                manifest_json=None,
                parent_version=None,
                created_by=None,
                commit_message="Imported from local disk",
            )

            # Save files
            for file_path, (content, file_type, size) in skill_files.items():
                content_hash = hashlib.sha256(content).hexdigest()
                await service.version_repo.add_file(
                    version_id=ver.id,
                    file_path=file_path,
                    file_type=file_type,
                    content=content,
                    content_hash=content_hash,
                    size_bytes=size,
                )

            await service.skill_repo.set_current_version(skill.id, initial_version)

            results.append(ImportLocalResultItem(
                name=skill_name, success=True, version=initial_version
            ))
            total_imported += 1

        except Exception as e:
            results.append(ImportLocalResultItem(
                name=skill_name, success=False, error=str(e)
            ))
            total_failed += 1

    await db.commit()

    return ImportLocalResponse(
        results=results,
        total_imported=total_imported,
        total_failed=total_failed,
    )


def _run_skill_creation_with_agent(task_id: str, name: str, description: Optional[str], skill_type: str = "user", tags: Optional[List[str]] = None, trace_id: Optional[str] = None):
    """Background function to create skill using Agent."""
    import time
    import hashlib
    from app.agent import SkillsAgent
    from sqlalchemy import update as sa_update

    skills_dir = Path(settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / name
    start_time = time.time()

    try:
        # Run Agent to create skill
        agent = SkillsAgent(max_turns=60, verbose=True)

        agent_request = f"""Use the skill-creator skill to create a new skill.

Skill name: {name}
Skill description: {description or '(No description provided, please infer from the name)'}

Follow the skill-creator guidance:
1. First read the skill-creator skill documentation
2. Run init_skill.py to initialize this skill in the skills directory
3. Based on the description, write appropriate SKILL.md content (replace the TODO placeholders in the template)
4. If needed, create related scripts or references files

Important constraints:
- Must use the exact name "{name}", do not modify or "correct" this name
- Skill directory must be created at {skills_dir}/{name}
- The SKILL.md description field should clearly describe the skill's purpose and trigger conditions
- Delete unnecessary example files
"""

        agent_result = agent.run_sync(agent_request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Update trace in database (sync)
        if trace_id:
            _update_trace_sync(
                trace_id=trace_id,
                agent_request=agent_request,
                agent_result=agent_result,
                skills_used=["skill-creator"],
                duration_ms=duration_ms,
            )

        if not agent_result.success:
            raise Exception(f"Agent failed: {agent_result.error or agent_result.answer}")

        # Verify skill directory was created
        if not skill_dir.exists():
            raise Exception(f"Skill directory was not created at {skill_dir}")

        # Read SKILL.md content
        skill_md_content = None
        skill_md_path = skill_dir / "SKILL.md"
        if skill_md_path.exists():
            skill_md_content = skill_md_path.read_text()

        # Read all other files from the skill directory
        skill_files, _ = _read_skill_files(skill_dir)

        # Extract description from SKILL.md if not provided
        final_description = description
        if skill_md_content and not final_description:
            match = re.search(r'^description:\s*(.+)$', skill_md_content, re.MULTILINE)
            if match:
                final_description = match.group(1).strip()

        # Save to database using sync session
        _save_created_skill_to_db(
            name=name,
            description=final_description,
            skill_type=skill_type,
            tags=tags,
            skill_md_content=skill_md_content,
            skill_files=skill_files,
        )

        return {"skill_name": name, "trace_id": trace_id}

    except Exception as e:
        # Update trace to failed if we have a trace_id and haven't updated yet
        if trace_id:
            try:
                _fail_trace_sync(trace_id, str(e))
            except Exception:
                pass
        raise


@router.post("/skills", response_model=CreateSkillTaskResponse, status_code=202)
async def create_skill(
    request: CreateSkillRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new skill asynchronously using AI agent."""
    # Validate name
    validator = SchemaValidator()
    result = validator.validate_skill_name(request.name)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors[0])

    # Check if already exists
    service = SkillService(db)
    if await service.skill_repo.exists(request.name):
        raise HTTPException(status_code=409, detail=f"Skill '{request.name}' already exists")

    # Check if skill directory already exists
    skills_dir = Path(settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / request.name
    if skill_dir.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Skill directory '{request.name}' already exists.\nHint: If this skill is not visible in the list, it may be a leftover from a failed creation. Please manually delete '{skill_dir}' and try again."
        )

    # Create trace upfront (so frontend can show trace_id immediately)
    trace = AgentTraceDB(
        request=f"[create_skill] {request.name}",
        skills_used=["skill-creator"],
        model=settings.default_model_name,
        status="running",
        success=False,
        answer="", error=None,
        total_turns=0, total_input_tokens=0, total_output_tokens=0,
        steps=[], llm_calls=[], duration_ms=0,
    )
    db.add(trace)
    await db.flush()
    trace_id = trace.id
    await db.commit()

    # Create task and run in background
    task = await task_manager.create_task_async(
        task_type="create_skill",
        metadata={"skill_name": request.name, "trace_id": trace_id}
    )
    # Normalize tags
    tags = None
    if request.tags:
        tags = list(dict.fromkeys(t.strip().lower() for t in request.tags if t.strip()))

    task_manager.run_in_background(
        task.id,
        _run_skill_creation_with_agent,
        task.id,
        request.name,
        request.description,
        request.skill_type,
        tags,
        trace_id,
    )

    return CreateSkillTaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Skill creation started. Poll /api/v1/registry/tasks/{task.id} for status.",
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a task (skill creation or evolution)."""
    task = await task_manager.get_task_async(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    skill_name = task.metadata.get("skill_name")
    new_version = None

    # trace_id: prefer metadata (available immediately), fallback to result (old tasks)
    trace_id = task.metadata.get("trace_id")

    # Extract new_version (and fallback trace_id) from result
    if task.status == TaskStatus.COMPLETED and task.result:
        if isinstance(task.result, dict):
            new_version = task.result.get("new_version")
            if not trace_id:
                trace_id = task.result.get("trace_id")

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        skill_name=skill_name if task.status == TaskStatus.COMPLETED else None,
        new_version=new_version,
        trace_id=trace_id,
        error=task.error,
    )


@router.get("/skills/search", response_model=SkillListResponse)
async def search_skills(
    q: str = Query(..., min_length=1, description="Search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Search skills by name or description."""
    service = SkillService(db)
    return await service.search_skills(query=q, offset=offset, limit=limit)


@router.get("/skills/{name}", response_model=SkillResponse)
async def get_skill(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a skill by name."""
    service = SkillService(db)
    try:
        return await service.get_skill(name)
    except SkillNotFoundError as e:
        raise handle_service_error(e)


@router.put("/skills/{name}", response_model=SkillResponse)
async def update_skill(
    name: str,
    request: UpdateSkillRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a skill."""
    service = SkillService(db)
    try:
        return await service.update_skill(
            name=name,
            description=request.description,
            status=request.status,
            tags=request.tags,
            icon_url=request.icon_url,
            category=request.category,
            source=request.source,
            author=request.author,
        )
    except (SkillNotFoundError, ValidationError) as e:
        raise handle_service_error(e)


@router.delete("/skills/{name}", status_code=204)
async def delete_skill(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a skill and all its versions.

    Note: Meta skills cannot be deleted.
    """
    import shutil
    import logging
    logger = logging.getLogger(__name__)

    # Check if skill exists and is a meta skill
    from sqlalchemy import select
    from app.db.models import SkillDB
    result = await db.execute(select(SkillDB).where(SkillDB.name == name))
    skill = result.scalar_one_or_none()

    if skill and skill.skill_type == "meta":
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete meta skill '{name}'. Meta skills are protected."
        )

    service = SkillService(db)
    try:
        await service.delete_skill(name)
    except SkillNotFoundError as e:
        raise handle_service_error(e)

    # Clean up disk directory
    skills_dir = Path(settings.effective_skills_dir).resolve()
    skill_dir = skills_dir / name
    if skill_dir.exists():
        try:
            shutil.rmtree(skill_dir)
            logger.info(f"Deleted skill directory: {skill_dir}")
        except Exception as e:
            logger.error(f"Failed to delete skill directory {skill_dir}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Skill deleted from database but failed to remove disk files: {e}"
            )


# Version endpoints

@router.get("/skills/{name}/versions", response_model=VersionListResponse)
async def list_versions(
    name: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a skill."""
    service = SkillService(db)
    try:
        return await service.list_versions(name, offset=offset, limit=limit)
    except SkillNotFoundError as e:
        raise handle_service_error(e)


@router.post("/skills/{name}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    name: str,
    request: CreateVersionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of a skill."""
    service = SkillService(db)
    try:
        return await service.create_version(
            skill_name=name,
            version=request.version,
            skill_md=request.skill_md,
            schema_json=request.schema_json,
            manifest_json=request.manifest_json,
            commit_message=request.commit_message,
            files_content=request.files_content,
        )
    except (SkillNotFoundError, VersionAlreadyExistsError, ValidationError) as e:
        raise handle_service_error(e)


@router.get("/skills/{name}/versions/{version}", response_model=VersionResponse)
async def get_version(
    name: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific version of a skill."""
    service = SkillService(db)
    try:
        return await service.get_version(name, version)
    except (SkillNotFoundError, VersionNotFoundError) as e:
        raise handle_service_error(e)


@router.delete("/skills/{name}/versions/{version}")
async def delete_version(
    name: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific version of a skill."""
    service = SkillService(db)
    try:
        await service.delete_version(name, version)
        return {"message": f"Version {version} deleted"}
    except (SkillNotFoundError, VersionNotFoundError, ValidationError) as e:
        raise handle_service_error(e)


@router.post("/skills/{name}/rollback", response_model=VersionResponse)
async def rollback_version(
    name: str,
    request: RollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rollback a skill to a previous version."""
    service = SkillService(db)
    try:
        return await service.rollback_version(
            skill_name=name,
            to_version=request.version,
            comment=request.comment,
        )
    except (SkillNotFoundError, VersionNotFoundError) as e:
        raise handle_service_error(e)


# File and Diff response models
class FileInfo(BaseModel):
    file_path: str
    file_type: str
    size_bytes: Optional[int] = None
    content_hash: Optional[str] = None


class VersionFilesResponse(BaseModel):
    version: str
    files: List[FileInfo]


class FileContentResponse(BaseModel):
    file_path: str
    content: str


class DiffResponse(BaseModel):
    from_version: str
    to_version: str
    file_path: str
    diff: str
    old_content: str
    new_content: str


class FullDiffResponse(BaseModel):
    from_version: str
    to_version: str
    files: List[DiffResponse]


@router.get("/skills/{name}/versions/{version}/files", response_model=VersionFilesResponse)
async def get_version_files(
    name: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Get list of files in a version."""
    service = SkillService(db)
    try:
        skill = await service.skill_repo.get_by_name(name)
        if not skill:
            raise SkillNotFoundError(name)

        ver = await service.version_repo.get_by_skill_and_version(skill.id, version)
        if not ver:
            raise VersionNotFoundError(name, version)

        files = await service.version_repo.get_files(ver.id)

        return VersionFilesResponse(
            version=version,
            files=[
                FileInfo(
                    file_path=f.file_path,
                    file_type=f.file_type,
                    size_bytes=f.size_bytes,
                    content_hash=f.content_hash,
                )
                for f in files
            ]
        )
    except (SkillNotFoundError, VersionNotFoundError) as e:
        raise handle_service_error(e)


@router.get("/skills/{name}/versions/{version}/files/{file_path:path}", response_model=FileContentResponse)
async def get_file_content(
    name: str,
    version: str,
    file_path: str,
    db: AsyncSession = Depends(get_db),
):
    """Get content of a specific file in a version."""
    service = SkillService(db)
    try:
        skill = await service.skill_repo.get_by_name(name)
        if not skill:
            raise SkillNotFoundError(name)

        ver = await service.version_repo.get_by_skill_and_version(skill.id, version)
        if not ver:
            raise VersionNotFoundError(name, version)

        file = await service.version_repo.get_file(ver.id, file_path)
        if not file:
            raise HTTPException(status_code=404, detail=f"File '{file_path}' not found in version {version}")

        content = file.content.decode("utf-8") if file.content else ""

        return FileContentResponse(
            file_path=file_path,
            content=content,
        )
    except (SkillNotFoundError, VersionNotFoundError) as e:
        raise handle_service_error(e)


@router.get("/skills/{name}/diff")
async def get_version_diff(
    name: str,
    from_version: str = Query(..., alias="from", description="Source version"),
    to_version: str = Query(..., alias="to", description="Target version"),
    file_path: Optional[str] = Query(None, description="Specific file to diff (default: SKILL.md)"),
    db: AsyncSession = Depends(get_db),
) -> DiffResponse:
    """Get diff between two versions of a skill for a specific file."""
    import difflib

    service = SkillService(db)
    try:
        skill = await service.skill_repo.get_by_name(name)
        if not skill:
            raise SkillNotFoundError(name)

        from_ver = await service.version_repo.get_by_skill_and_version(skill.id, from_version)
        to_ver = await service.version_repo.get_by_skill_and_version(skill.id, to_version)

        if not from_ver:
            raise VersionNotFoundError(name, from_version)
        if not to_ver:
            raise VersionNotFoundError(name, to_version)

        # Default to SKILL.md
        target_file = file_path or "SKILL.md"

        if target_file == "SKILL.md":
            from_content = from_ver.skill_md or ""
            to_content = to_ver.skill_md or ""
        else:
            from_file = await service.version_repo.get_file(from_ver.id, target_file)
            to_file = await service.version_repo.get_file(to_ver.id, target_file)
            from_content = from_file.content.decode("utf-8") if from_file and from_file.content else ""
            to_content = to_file.content.decode("utf-8") if to_file and to_file.content else ""

        # Compute unified diff
        from_lines = from_content.splitlines(keepends=True)
        to_lines = to_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            from_lines,
            to_lines,
            fromfile=f"{target_file} (v{from_version})",
            tofile=f"{target_file} (v{to_version})",
            lineterm=""
        )

        return {
            "from_version": from_version,
            "to_version": to_version,
            "file_path": target_file,
            "diff": "".join(diff),
            "old_content": from_content,
            "new_content": to_content,
        }
    except (SkillNotFoundError, VersionNotFoundError) as e:
        raise handle_service_error(e)


# Evolve endpoint

def _read_skill_files(skill_dir: Path) -> tuple[dict, list[str]]:
    """Read all files from a skill directory.

    Returns tuple of (files_dict, skipped_list):
    - files_dict: {relative_path: (content_bytes, file_type, size)}
    - skipped_list: list of relative paths that were skipped due to filtering rules
    """
    import hashlib

    files = {}
    skipped = []
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
            rel = str(file_path.relative_to(skill_dir))
            skipped.append(rel)
            continue

        # Skip large files (size limit, not reported as unsupported type)
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

        # Read file content (binary or text)
        try:
            content = file_path.read_bytes()
            files[str(rel_path)] = (content, file_type, size)
        except OSError:
            # Skip files that can't be read
            continue

    return files, skipped


def _increment_version(version: str) -> str:
    """Increment patch version: 0.0.1 -> 0.0.2"""
    parts = version.split(".")
    if len(parts) == 3:
        parts[2] = str(int(parts[2]) + 1)
        return ".".join(parts)
    return version


def _update_trace_sync(trace_id: str, agent_request: str, agent_result, skills_used: list, duration_ms: int):
    """Update a pre-created trace record with agent execution results (sync, safe for background threads)."""
    from sqlalchemy import update as sa_update

    with SyncSessionLocal() as session:
        session.execute(
            sa_update(AgentTraceDB)
            .where(AgentTraceDB.id == trace_id)
            .values(
                request=agent_request,
                skills_used=skills_used,
                status="completed" if agent_result.success else "failed",
                success=agent_result.success,
                answer=agent_result.answer,
                error=agent_result.error,
                total_turns=agent_result.total_turns,
                total_input_tokens=agent_result.total_input_tokens,
                total_output_tokens=agent_result.total_output_tokens,
                steps=[
                    {
                        "role": step.role,
                        "content": step.content[:1000] if step.content else "",
                        "tool_name": step.tool_name,
                        "tool_input": step.tool_input,
                    }
                    for step in agent_result.steps
                ],
                llm_calls=[call.__dict__ for call in agent_result.llm_calls] if agent_result.llm_calls else [],
                duration_ms=duration_ms,
            )
        )
        session.commit()


def _fail_trace_sync(trace_id: str, error: str):
    """Mark a pre-created trace as failed (sync, safe for background threads)."""
    from sqlalchemy import update as sa_update

    with SyncSessionLocal() as session:
        session.execute(
            sa_update(AgentTraceDB)
            .where(AgentTraceDB.id == trace_id)
            .values(
                status="failed",
                success=False,
                error=error,
            )
        )
        session.commit()


def _save_created_skill_to_db(name: str, description: Optional[str], skill_type: str, tags: Optional[List[str]], skill_md_content: Optional[str], skill_files: dict):
    """Save a newly created skill to the database using sync session."""
    import hashlib
    import uuid
    from datetime import datetime
    from sqlalchemy import insert as sa_insert, text
    from app.db.models import SkillDB, SkillVersionDB, SkillFileDB, SkillChangelogDB

    with SyncSessionLocal() as session:
        now = datetime.utcnow()
        skill_id = str(uuid.uuid4())

        # Create skill
        session.execute(
            sa_insert(SkillDB).values(
                id=skill_id,
                name=name,
                description=description,
                owner_id=None,
                status="draft",
                skill_type=skill_type,
                tags=tags,
                created_at=now,
                updated_at=now,
            )
        )

        # Add changelog
        session.execute(
            sa_insert(SkillChangelogDB).values(
                id=str(uuid.uuid4()),
                skill_id=skill_id,
                change_type="create",
                version_to=None,
                changed_by=None,
                changed_at=now,
                comment=f"Created skill '{name}' using skill-creator",
            )
        )

        # Create initial version
        if skill_md_content:
            initial_version = "0.0.1"
            ver_id = str(uuid.uuid4())
            session.execute(
                sa_insert(SkillVersionDB).values(
                    id=ver_id,
                    skill_id=skill_id,
                    version=initial_version,
                    skill_md=skill_md_content,
                    schema_json=None,
                    manifest_json=None,
                    parent_version=None,
                    created_by=None,
                    created_at=now,
                    commit_message="Initial version created by skill-creator",
                )
            )

            # Save all files to the version
            for file_path, (content, file_type, size) in skill_files.items():
                content_hash = hashlib.sha256(content).hexdigest()
                session.execute(
                    sa_insert(SkillFileDB).values(
                        id=str(uuid.uuid4()),
                        version_id=ver_id,
                        file_path=file_path,
                        file_type=file_type,
                        content=content,
                        content_hash=content_hash,
                        size_bytes=size,
                        created_at=now,
                    )
                )

            # Set current version
            session.execute(
                text("UPDATE skills SET current_version = :version, updated_at = :now WHERE id = :id"),
                {"version": initial_version, "now": now, "id": skill_id},
            )

        session.commit()


def _save_evolved_skill_to_db(skill_id: str, skill_name: str, new_version: str, current_version: str, skill_md_content: str, skill_files: dict, commit_message: str, changelog_comment: str) -> str:
    """Save an evolved skill version to the database using sync session. Returns the actual new_version used."""
    import hashlib
    import uuid
    from datetime import datetime
    from sqlalchemy import insert as sa_insert, text

    from app.db.models import SkillVersionDB, SkillFileDB, SkillChangelogDB

    with SyncSessionLocal() as session:
        now = datetime.utcnow()

        # Find the max existing version and increment from that (not from current_version)
        result = session.execute(
            text("SELECT version FROM skill_versions WHERE skill_id = :skill_id"),
            {"skill_id": skill_id},
        )
        existing_versions = [row[0] for row in result.all()]

        if existing_versions:
            def _ver_key(v: str):
                try:
                    return tuple(int(p) for p in v.split(".")[:3])
                except (ValueError, IndexError):
                    return (0, 0, 0)
            max_ver = max(existing_versions, key=_ver_key)
            new_version = _increment_version(max_ver)
            # Safety: ensure uniqueness
            while new_version in existing_versions:
                new_version = _increment_version(new_version)

        # Create new version
        ver_id = str(uuid.uuid4())
        session.execute(
            sa_insert(SkillVersionDB).values(
                id=ver_id,
                skill_id=skill_id,
                version=new_version,
                skill_md=skill_md_content,
                schema_json=None,
                manifest_json=None,
                parent_version=current_version,
                created_by=None,
                created_at=now,
                commit_message=commit_message,
            )
        )

        # Save all files to the version
        for file_path, (content, file_type, size) in skill_files.items():
            content_hash = hashlib.sha256(content).hexdigest()
            session.execute(
                sa_insert(SkillFileDB).values(
                    id=str(uuid.uuid4()),
                    version_id=ver_id,
                    file_path=file_path,
                    file_type=file_type,
                    content=content,
                    content_hash=content_hash,
                    size_bytes=size,
                    created_at=now,
                )
            )

        # Update skill's current version
        session.execute(
            text("UPDATE skills SET current_version = :version, updated_at = :now WHERE id = :id"),
            {"version": new_version, "now": now, "id": skill_id},
        )

        # Add changelog
        session.execute(
            sa_insert(SkillChangelogDB).values(
                id=str(uuid.uuid4()),
                skill_id=skill_id,
                change_type="update",
                version_from=current_version,
                version_to=new_version,
                changed_by=None,
                changed_at=now,
                comment=changelog_comment,
            )
        )

        session.commit()

    return new_version


def _run_skill_evolution_with_agent(task_id: str, skill_name: str, skill_id: int, current_version: str, feedback: str, skill_dir: Path, trace_id: Optional[str] = None):
    """Background function to evolve skill using Agent."""
    import time
    import hashlib
    from app.agent import SkillsAgent
    from sqlalchemy import update as sa_update

    start_time = time.time()

    try:
        # Run Agent to update skill
        agent = SkillsAgent(max_turns=60, verbose=True)

        agent_request = f"""Use the skill-updater skill to update an existing skill.

Skill name: {skill_name}
User feedback: {feedback}

Follow the skill-updater guidance:
1. First read the skill-updater skill documentation
2. Read the current SKILL.md content of the target skill ({skill_name})
3. Based on user feedback, update the SKILL.md content
4. If needed, update related scripts or references files

Important constraints:
- Skill directory is located at {skill_dir}
- Make targeted improvements based on user feedback
- Maintain the SKILL.md format specification
"""

        agent_result = agent.run_sync(agent_request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Update trace in database (sync)
        if trace_id:
            _update_trace_sync(
                trace_id=trace_id,
                agent_request=agent_request,
                agent_result=agent_result,
                skills_used=["skill-updater", skill_name],
                duration_ms=duration_ms,
            )

        if not agent_result.success:
            raise Exception(f"Agent failed: {agent_result.error or agent_result.answer}")

        # Read updated SKILL.md content
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            raise Exception(f"SKILL.md not found at {skill_md_path}")

        skill_md_content = skill_md_path.read_text()

        # Read all other files from the skill directory
        skill_files, _ = _read_skill_files(skill_dir)

        # Calculate new version
        new_version = _increment_version(current_version)

        # Save to database using sync session
        new_version = _save_evolved_skill_to_db(
            skill_id=skill_id,
            skill_name=skill_name,
            new_version=new_version,
            current_version=current_version,
            skill_md_content=skill_md_content,
            skill_files=skill_files,
            commit_message=f"Evolved from feedback: {feedback[:100]}",
            changelog_comment=f"Evolved via agent feedback: {feedback[:200]}",
        )

        return {"skill_name": skill_name, "new_version": new_version, "trace_id": trace_id}

    except Exception as e:
        if trace_id:
            try:
                _fail_trace_sync(trace_id, str(e))
            except Exception:
                pass
        raise



def _run_skill_evolution_via_traces(task_id: str, skill_name: str, skill_id: int, current_version: str, traces_json: str, skill_dir: Path, feedback: Optional[str] = None, trace_id: Optional[str] = None):
    """Background function to evolve skill based on traces (and optional feedback) using skill-evolver."""
    import json
    import tempfile
    import time
    import hashlib
    from app.agent import SkillsAgent
    from sqlalchemy import update as sa_update

    start_time = time.time()

    try:
        # Write traces to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(traces_json)
            traces_file = f.name

        # Run Agent with skill-evolver
        agent = SkillsAgent(max_turns=60, verbose=True)

        # Build feedback section if provided
        feedback_section = ""
        if feedback:
            feedback_section = f"""
User feedback: {feedback}

Please combine trace data analysis and user feedback to improve the skill. User feedback provides improvement direction, trace data provides evidence of issues.
"""

        agent_request = f"""Use the skill-evolver skill to analyze execution traces and improve the skill.

Target Skill: {skill_name}
Skill directory: {skill_dir}
Traces file: {traces_file}
{feedback_section}
Follow the skill-evolver guidance:
1. First read the skill-evolver skill documentation
2. Run scripts/analyze_traces.py to analyze the traces file
3. If issues are found, run scripts/extract_issue_context.py to get detailed information
4. Read the current content of the target skill ({skill_name})
5. Based on the analysis results{'and user feedback' if feedback else ''}, improve SKILL.md and related scripts

Important constraints:
- Skill directory is located at {skill_dir}
- Trace data is in {traces_file}
- Make targeted improvements based on real execution data
- Maintain the SKILL.md format specification
"""

        agent_result = agent.run_sync(agent_request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Update trace in database (sync)
        if trace_id:
            _update_trace_sync(
                trace_id=trace_id,
                agent_request=agent_request,
                agent_result=agent_result,
                skills_used=["skill-evolver", skill_name],
                duration_ms=duration_ms,
            )

        # Clean up temp file
        import os
        try:
            os.unlink(traces_file)
        except Exception:
            pass

        if not agent_result.success:
            raise Exception(f"Agent failed: {agent_result.error or agent_result.answer}")

        # Read updated SKILL.md content
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            raise Exception(f"SKILL.md not found at {skill_md_path}")

        skill_md_content = skill_md_path.read_text()

        # Read all other files from the skill directory
        skill_files, _ = _read_skill_files(skill_dir)

        # Calculate new version
        new_version = _increment_version(current_version)

        # Save to database using sync session
        new_version = _save_evolved_skill_to_db(
            skill_id=skill_id,
            skill_name=skill_name,
            new_version=new_version,
            current_version=current_version,
            skill_md_content=skill_md_content,
            skill_files=skill_files,
            commit_message=f"Evolved via trace analysis" + (f" with feedback: {feedback[:80]}" if feedback else ""),
            changelog_comment=f"Evolved via trace analysis (skill-evolver)" + (f" — feedback: {feedback[:150]}" if feedback else ""),
        )

        return {"skill_name": skill_name, "new_version": new_version, "trace_id": trace_id}

    except Exception as e:
        if trace_id:
            try:
                _fail_trace_sync(trace_id, str(e))
            except Exception:
                pass
        raise


@router.post("/skills/{name}/evolve-via-traces", response_model=EvolveTaskResponse, status_code=202)
async def evolve_skill_via_traces(
    name: str,
    request: EvolveViaTracesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Evolve a skill using traces and/or feedback.

    - traces only → skill-evolver analyzes traces
    - traces + feedback → skill-evolver uses both
    - feedback only → skill-updater applies feedback
    At least one of trace_ids or feedback must be provided.
    """
    import json
    from sqlalchemy import select

    has_traces = bool(request.trace_ids)
    has_feedback = bool(request.feedback and request.feedback.strip())

    if not has_traces and not has_feedback:
        raise HTTPException(status_code=400, detail="At least one of trace_ids or feedback is required")

    # Verify skill exists
    service = SkillService(db)
    try:
        skill = await service.skill_repo.get_by_name(name)
        if not skill:
            raise SkillNotFoundError(name)
    except SkillNotFoundError as e:
        raise handle_service_error(e)

    # Verify skill directory exists
    skills_dir = Path(settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / name
    if not skill_dir.exists():
        raise HTTPException(status_code=404, detail=f"Skill directory '{name}' not found")

    current_version = skill.current_version or "0.0.0"

    if has_traces:
        # Route: skill-evolver (traces, optionally with feedback)
        result = await db.execute(
            select(AgentTraceDB).where(AgentTraceDB.id.in_(request.trace_ids))
        )
        traces = result.scalars().all()

        if not traces:
            raise HTTPException(status_code=404, detail="No traces found for the given IDs")

        traces_data = []
        for t in traces:
            traces_data.append({
                "id": t.id,
                "request": t.request,
                "skills_used": t.skills_used,
                "model": t.model,
                "success": t.success,
                "answer": t.answer,
                "error": t.error,
                "total_turns": t.total_turns,
                "total_input_tokens": t.total_input_tokens,
                "total_output_tokens": t.total_output_tokens,
                "duration_ms": t.duration_ms,
                "steps": t.steps or [],
                "llm_calls": t.llm_calls or [],
            })

        traces_json = json.dumps(traces_data, ensure_ascii=False, indent=2)

        # Create trace upfront
        trace = AgentTraceDB(
            request=f"[evolve_skill_via_traces] {name}",
            skills_used=["skill-evolver", name],
            model=settings.default_model_name,
            status="running",
            success=False,
            answer="", error=None,
            total_turns=0, total_input_tokens=0, total_output_tokens=0,
            steps=[], llm_calls=[], duration_ms=0,
        )
        db.add(trace)
        await db.flush()
        trace_id = trace.id
        await db.commit()

        task = await task_manager.create_task_async(
            task_type="evolve_skill_via_traces",
            metadata={"skill_name": name, "trace_count": len(traces), "trace_id": trace_id}
        )
        task_manager.run_in_background(
            task.id,
            _run_skill_evolution_via_traces,
            task.id,
            name,
            skill.id,
            current_version,
            traces_json,
            skill_dir,
            request.feedback.strip() if has_feedback else None,
            trace_id,
        )

        msg = f"Skill evolution via traces started ({len(traces)} traces"
        if has_feedback:
            msg += " + feedback"
        msg += f"). Poll /api/v1/registry/tasks/{task.id} for status."
    else:
        # Route: skill-updater (feedback only, no traces)

        # Create trace upfront
        trace = AgentTraceDB(
            request=f"[evolve_skill] {name}",
            skills_used=["skill-updater", name],
            model=settings.default_model_name,
            status="running",
            success=False,
            answer="", error=None,
            total_turns=0, total_input_tokens=0, total_output_tokens=0,
            steps=[], llm_calls=[], duration_ms=0,
        )
        db.add(trace)
        await db.flush()
        trace_id = trace.id
        await db.commit()

        task = await task_manager.create_task_async(
            task_type="evolve_skill",
            metadata={"skill_name": name, "trace_id": trace_id}
        )
        task_manager.run_in_background(
            task.id,
            _run_skill_evolution_with_agent,
            task.id,
            name,
            skill.id,
            current_version,
            request.feedback.strip(),
            skill_dir,
            trace_id,
        )
        msg = f"Skill evolution via feedback started. Poll /api/v1/registry/tasks/{task.id} for status."

    return EvolveTaskResponse(
        task_id=task.id,
        status="pending",
        message=msg,
    )


# Filesystem sync endpoint

class FilesystemSyncResponse(BaseModel):
    synced: bool
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    changes_summary: Optional[str] = None


@router.post("/skills/{name}/sync-filesystem", response_model=FilesystemSyncResponse)
async def sync_filesystem(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if disk files differ from latest DB version, and create a new version if so."""
    service = SkillService(db)

    # 1. Get skill from DB
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    current_version = skill.current_version
    if not current_version:
        return FilesystemSyncResponse(synced=False)

    # 2. Check if skill directory exists on disk
    skills_dir = Path(settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / name
    if not skill_dir.exists():
        return FilesystemSyncResponse(synced=False)

    # 3. Read disk SKILL.md
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        return FilesystemSyncResponse(synced=False)

    disk_skill_md = skill_md_path.read_text()

    # 4. Get DB version
    db_version = await service.version_repo.get_by_skill_and_version(skill.id, current_version)
    if not db_version:
        return FilesystemSyncResponse(synced=False)

    db_skill_md = db_version.skill_md or ""

    # 5. Read disk files (non-SKILL.md)
    disk_files, _ = _read_skill_files(skill_dir)

    # 6. Get DB files for current version
    db_files_list = await service.version_repo.get_files(db_version.id)
    db_file_hashes = {}
    for f in db_files_list:
        if f.content:
            db_file_hashes[f.file_path] = hashlib.sha256(f.content).hexdigest()
        else:
            db_file_hashes[f.file_path] = hashlib.sha256(b"").hexdigest()

    # 7. Compare SKILL.md
    skill_md_changed = disk_skill_md != db_skill_md

    # 8. Compare other files by hash
    disk_file_hashes = {}
    for file_path, (content, file_type, size) in disk_files.items():
        disk_file_hashes[file_path] = hashlib.sha256(content).hexdigest()

    files_changed = disk_file_hashes != db_file_hashes

    if not skill_md_changed and not files_changed:
        return FilesystemSyncResponse(synced=False)

    # 9. Build changes summary
    changes = []
    if skill_md_changed:
        changes.append("SKILL.md modified")

    # Detect added / removed / modified files
    disk_paths = set(disk_file_hashes.keys())
    db_paths = set(db_file_hashes.keys())
    added = disk_paths - db_paths
    removed = db_paths - disk_paths
    common = disk_paths & db_paths
    modified = {p for p in common if disk_file_hashes[p] != db_file_hashes[p]}

    if added:
        changes.append(f"Added: {', '.join(sorted(added))}")
    if removed:
        changes.append(f"Removed: {', '.join(sorted(removed))}")
    if modified:
        changes.append(f"Modified: {', '.join(sorted(modified))}")

    changes_summary = "; ".join(changes)

    # 10. Create new version (based on max existing version, not current_version)
    max_version = await service.version_repo.get_max_version(skill.id)
    new_version = _increment_version(max_version or current_version)
    # Ensure version doesn't already exist
    if await service.version_repo.exists(skill.id, new_version):
        for _ in range(100):
            new_version = _increment_version(new_version)
            if not await service.version_repo.exists(skill.id, new_version):
                break

    ver = await service.version_repo.create(
        skill_id=skill.id,
        version=new_version,
        skill_md=disk_skill_md,
        schema_json=None,
        manifest_json=None,
        parent_version=current_version,
        created_by=None,
        commit_message=f"Synced from filesystem: {changes_summary}",
    )

    # Save files
    for file_path, (content, file_type, size) in disk_files.items():
        content_hash = hashlib.sha256(content).hexdigest()
        await service.version_repo.add_file(
            version_id=ver.id,
            file_path=file_path,
            file_type=file_type,
            content=content,
            content_hash=content_hash,
            size_bytes=size,
        )

    # Update current version
    await service.skill_repo.set_current_version(skill.id, new_version)

    # Add changelog
    await service.skill_repo.add_changelog(
        skill_id=skill.id,
        change_type="update",
        version_from=current_version,
        version_to=new_version,
        changed_by=None,
        comment=f"Auto-synced from filesystem: {changes_summary}",
    )

    await db.commit()

    return FilesystemSyncResponse(
        synced=True,
        old_version=current_version,
        new_version=new_version,
        changes_summary=changes_summary,
    )


# Changelog endpoints

@router.get("/skills/{name}/changelog", response_model=ChangelogListResponse)
async def get_changelog(
    name: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get changelog entries for a skill."""
    service = SkillService(db)
    try:
        return await service.get_changelogs(name, offset=offset, limit=limit)
    except SkillNotFoundError as e:
        raise handle_service_error(e)


# Import/Export endpoints

class ImportSkillResponse(BaseModel):
    success: bool
    skill_name: str
    version: str
    message: str
    conflict: bool = False
    existing_skill: Optional[str] = None
    existing_version: Optional[str] = None
    skipped_files: List[str] = []


async def _do_skill_import(
    original_skill_name: str,
    skill_md_content: str,
    other_files: dict[str, tuple[bytes, str]],
    schema_json: Optional[dict],
    manifest_json: Optional[dict],
    check_only: bool,
    conflict_action: Optional[str],
    source: str,
    db: AsyncSession,
    source_url: Optional[str] = None,
    author: Optional[str] = None,
    skipped_files: Optional[List[str]] = None,
) -> ImportSkillResponse:
    """
    Shared import logic for both zip file and GitHub imports.

    Args:
        original_skill_name: Skill name extracted from SKILL.md or path
        skill_md_content: Content of SKILL.md
        other_files: Dict mapping relative paths to (content_bytes, file_type)
        schema_json: Optional schema.json content
        manifest_json: Optional manifest.json content
        check_only: If True, only check for conflicts without importing
        conflict_action: 'copy' to create a copy on conflict
        source: Description of import source (for commit message)
        db: Database session
        source_url: Optional URL of the import source (e.g., GitHub URL)
        author: Optional author or organization name
    """
    # Validate skill name
    validator = SchemaValidator()
    result = validator.validate_skill_name(original_skill_name)
    if not result.valid:
        raise HTTPException(status_code=400, detail=f"Invalid skill name: {result.errors[0]}")

    # Check if skill already exists
    service = SkillService(db)
    existing = await service.skill_repo.get_by_name(original_skill_name)

    # Handle check_only mode
    if check_only:
        if existing:
            return ImportSkillResponse(
                success=False,
                skill_name=original_skill_name,
                version="",
                message=f"Skill '{original_skill_name}' already exists",
                conflict=True,
                existing_skill=original_skill_name,
                existing_version=existing.current_version,
            )
        else:
            return ImportSkillResponse(
                success=True,
                skill_name=original_skill_name,
                version="0.0.1",
                message=f"No conflict. Ready to import '{original_skill_name}'",
                conflict=False,
            )

    # Handle conflict
    if existing:
        if conflict_action == 'copy':
            # Generate a unique copy name
            copy_name = f"{original_skill_name}-copy"
            counter = 2
            while await service.skill_repo.get_by_name(copy_name):
                copy_name = f"{original_skill_name}-copy-{counter}"
                counter += 1

            # Update skill_md to reflect the new name (update frontmatter if present)
            skill_md_content = re.sub(
                r'^name:\s*' + re.escape(original_skill_name) + r'\s*$',
                f'name: {copy_name}',
                skill_md_content,
                flags=re.MULTILINE
            )

            skill_name = copy_name
        else:
            # No conflict_action specified - return 409 Conflict
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Skill '{original_skill_name}' already exists",
                    "existing_skill": original_skill_name,
                    "existing_version": existing.current_version,
                }
            )
    else:
        skill_name = original_skill_name

    # Create new skill
    # Extract description from SKILL.md frontmatter
    description = None
    match = re.search(r'^description:\s*(.+)$', skill_md_content, re.MULTILINE)
    if match:
        description = match.group(1).strip()

    skill = await service.skill_repo.create(
        name=skill_name,
        description=description,
        owner_id=None,
        status="draft",
        skill_type="user",
        source=source_url,
        author=author,
    )

    # Create initial version
    initial_version = "0.0.1"
    ver = await service.version_repo.create(
        skill_id=skill.id,
        version=initial_version,
        skill_md=skill_md_content,
        schema_json=schema_json,
        manifest_json=manifest_json,
        parent_version=None,
        created_by=None,
        commit_message=f"Imported from {source}",
    )

    # Add files
    for rel_path, (file_content, file_type) in other_files.items():
        content_hash = hashlib.sha256(file_content).hexdigest()
        await service.version_repo.add_file(
            version_id=ver.id,
            file_path=rel_path,
            file_type=file_type,
            content=file_content,
            content_hash=content_hash,
            size_bytes=len(file_content),
        )

    # Set current version
    await service.skill_repo.set_current_version(skill.id, initial_version)

    # Add changelog
    await service.skill_repo.add_changelog(
        skill_id=skill.id,
        change_type="import",
        version_to=initial_version,
        changed_by=None,
        comment=f"Created via import from {source}" + (f" (copy of {original_skill_name})" if skill_name != original_skill_name else ""),
    )

    # Write files to disk so Agent can use them at runtime
    skills_dir = Path(settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Write SKILL.md
    (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    # Write other files (scripts/, references/, assets/, etc.)
    for rel_path, (file_content, file_type) in other_files.items():
        out_path = skill_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(file_content)

    await db.commit()

    message = f"Created new skill '{skill_name}' with version {initial_version}"
    if skill_name != original_skill_name:
        message = f"Created copy '{skill_name}' (from '{original_skill_name}') with version {initial_version}"

    return ImportSkillResponse(
        success=True,
        skill_name=skill_name,
        version=initial_version,
        message=message,
        skipped_files=skipped_files or [],
    )


@router.get("/skills/{name}/export")
async def export_skill(
    name: str,
    version: Optional[str] = Query(None, description="Version to export (default: current)"),
    db: AsyncSession = Depends(get_db),
):
    """Export a skill as a .skill file (zip archive)."""
    service = SkillService(db)

    try:
        skill = await service.skill_repo.get_by_name(name)
        if not skill:
            raise SkillNotFoundError(name)

        # Get version to export
        target_version = version or skill.current_version
        if not target_version:
            raise HTTPException(status_code=400, detail="Skill has no versions to export")

        ver = await service.version_repo.get_by_skill_and_version(skill.id, target_version)
        if not ver:
            raise VersionNotFoundError(name, target_version)

        # Get all files for this version
        files = await service.version_repo.get_files(ver.id)

        # Create zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add SKILL.md
            if ver.skill_md:
                zf.writestr(f"{name}/SKILL.md", ver.skill_md)

            # Add schema.json if exists
            if ver.schema_json:
                import json
                zf.writestr(f"{name}/schema.json", json.dumps(ver.schema_json, indent=2))

            # Add manifest.json if exists
            if ver.manifest_json:
                import json
                zf.writestr(f"{name}/manifest.json", json.dumps(ver.manifest_json, indent=2))

            # Add all other files (skip non-essential files)
            for f in files:
                if not f.content:
                    continue
                if '__pycache__' in f.file_path or f.file_path.endswith('.pyc'):
                    continue
                zf.writestr(f"{name}/{f.file_path}", f.content)

        zip_buffer.seek(0)

        # Return as downloadable file
        filename = f"{name}.skill"
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except (SkillNotFoundError, VersionNotFoundError) as e:
        raise handle_service_error(e)


@router.post("/import", response_model=ImportSkillResponse)
async def import_skill(
    file: UploadFile = File(..., description="The .skill or .zip file to import"),
    check_only: bool = Query(False, description="Only check for conflicts, don't import"),
    conflict_action: Optional[str] = Query(None, description="Action on conflict: 'copy' to create a copy with new name"),
    db: AsyncSession = Depends(get_db),
):
    """Import a skill from a .skill or .zip file (zip archive).

    If a skill with the same name exists:
    - With check_only=true: returns conflict info without importing
    - With conflict_action='copy': creates a copy with a new name (e.g., skill-name-copy)
    - Without conflict_action: returns error (409 Conflict)
    """
    import hashlib
    import json

    # Validate file extension
    if not file.filename or not (file.filename.endswith('.skill') or file.filename.endswith('.zip')):
        raise HTTPException(status_code=400, detail="File must have .skill or .zip extension")

    # Read file content
    content = await file.read()

    # Validate it's a valid zip
    try:
        zip_buffer = io.BytesIO(content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # List all files
            file_list = zf.namelist()

            if not file_list:
                raise HTTPException(status_code=400, detail="Empty .skill file")

            # Determine skill name and path prefix from directory structure
            # Two supported layouts:
            #   1. skill-name/SKILL.md, skill-name/scripts/..., etc. (wrapper dir)
            #   2. SKILL.md, references/..., etc. (flat, no wrapper dir)
            flat_layout = 'SKILL.md' in file_list
            if flat_layout:
                # Flat layout: derive skill name from zip filename
                original_skill_name = Path(file.filename).stem if file.filename else 'imported-skill'
                prefix = ''
            else:
                first_file = file_list[0]
                original_skill_name = first_file.split('/')[0]

                if not original_skill_name:
                    raise HTTPException(status_code=400, detail="Invalid .skill file structure")

                prefix = f"{original_skill_name}/"

            # Find SKILL.md
            skill_md_path = f"{prefix}SKILL.md"
            if skill_md_path not in file_list:
                raise HTTPException(status_code=400, detail=f"SKILL.md not found in archive")

            # Read SKILL.md
            skill_md_content = zf.read(skill_md_path).decode('utf-8')

            # Try to extract skill name from frontmatter if flat layout
            if flat_layout:
                name_match = re.search(r'^name:\s*(.+)$', skill_md_content, re.MULTILINE)
                if name_match:
                    original_skill_name = name_match.group(1).strip()

            # Read optional schema.json
            schema_json = None
            schema_path = f"{prefix}schema.json"
            if schema_path in file_list:
                try:
                    schema_json = json.loads(zf.read(schema_path).decode('utf-8'))
                except json.JSONDecodeError:
                    pass

            # Read optional manifest.json
            manifest_json = None
            manifest_path = f"{prefix}manifest.json"
            if manifest_path in file_list:
                try:
                    manifest_json = json.loads(zf.read(manifest_path).decode('utf-8'))
                except json.JSONDecodeError:
                    pass

            # Skip compiled/build artifacts (consistent with _read_skill_files)
            _zip_skip_extensions = {
                ".pyc", ".pyo", ".pyd", ".class",
                ".o", ".a", ".so", ".dylib", ".dll", ".exe", ".wasm",
            }

            # Read all other files
            other_files = {}
            skipped_files = []
            for file_path in file_list:
                if prefix and not file_path.startswith(prefix):
                    continue

                rel_path = file_path[len(prefix):]  # Remove prefix

                # Skip SKILL.md, schema.json, manifest.json (already handled)
                if rel_path in ['SKILL.md', 'schema.json', 'manifest.json', '']:
                    continue

                # Skip directories
                if file_path.endswith('/'):
                    continue

                # Skip non-essential files (consistent with _read_skill_files)
                basename = rel_path.rsplit('/', 1)[-1]
                if basename.startswith('.') or basename.endswith('.pyc'):
                    continue
                if '__pycache__' in rel_path:
                    continue
                if '.backup' in basename or 'UPDATE_REPORT' in basename:
                    continue

                # Skip compiled/build artifacts and track them
                suffix = ('.' + basename.rsplit('.', 1)[-1]).lower() if '.' in basename else ''
                if suffix in _zip_skip_extensions:
                    skipped_files.append(rel_path)
                    continue

                try:
                    file_content = zf.read(file_path)
                    # Determine file type based on path
                    file_type = 'other'
                    if rel_path.startswith('scripts/'):
                        file_type = 'script'
                    elif rel_path.startswith('references/'):
                        file_type = 'reference'
                    elif rel_path.startswith('assets/'):
                        file_type = 'asset'

                    other_files[rel_path] = (file_content, file_type)
                except Exception:
                    continue

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")

    # Use shared import logic
    return await _do_skill_import(
        original_skill_name=original_skill_name,
        skill_md_content=skill_md_content,
        other_files=other_files,
        schema_json=schema_json,
        manifest_json=manifest_json,
        check_only=check_only,
        conflict_action=conflict_action,
        source=file.filename or "uploaded file",
        db=db,
        skipped_files=skipped_files,
    )


@router.post("/import-folder", response_model=ImportSkillResponse)
async def import_skill_from_folder(
    files: List[UploadFile] = File(..., description="Files from a folder (must include SKILL.md)"),
    check_only: bool = Query(False, description="Only check for conflicts, don't import"),
    conflict_action: Optional[str] = Query(None, description="Action on conflict: 'copy' to create a copy with new name"),
    db: AsyncSession = Depends(get_db),
):
    """Import a skill from a folder upload (multiple files with relative paths).

    The folder must contain a SKILL.md file at the root level.
    File paths are preserved from the webkitRelativePath attribute.

    If a skill with the same name exists:
    - With check_only=true: returns conflict info without importing
    - With conflict_action='copy': creates a copy with a new name (e.g., skill-name-copy)
    - Without conflict_action: returns error (409 Conflict)
    """
    import json

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Build file map from uploaded files
    # The filename should contain the relative path (from webkitRelativePath)
    file_map: dict[str, bytes] = {}
    folder_name: Optional[str] = None

    for f in files:
        if not f.filename:
            continue

        content = await f.read()

        # The filename from webkitRelativePath is like "folder-name/subdir/file.txt"
        # We need to extract the folder name and relative path
        parts = f.filename.replace("\\", "/").split("/")

        if len(parts) >= 1:
            if folder_name is None:
                folder_name = parts[0]

            # Get the relative path within the folder
            if len(parts) > 1:
                rel_path = "/".join(parts[1:])
            else:
                rel_path = parts[0]

            file_map[rel_path] = content

    if not file_map:
        raise HTTPException(status_code=400, detail="No valid files found in folder")

    # Check for SKILL.md at root level
    skill_md_content: Optional[str] = None
    skill_md_key: Optional[str] = None

    # Try to find SKILL.md (case-insensitive check)
    for key in file_map:
        if key.upper() == "SKILL.MD":
            skill_md_key = key
            try:
                skill_md_content = file_map[key].decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="SKILL.md is not a valid UTF-8 text file")
            break

    if not skill_md_content:
        raise HTTPException(
            status_code=400,
            detail="Folder must contain a SKILL.md file at the root level"
        )

    # Determine skill name from folder name or SKILL.md frontmatter
    original_skill_name = folder_name or "imported-skill"

    # Try to extract skill name from SKILL.md frontmatter
    name_match = re.search(r'^name:\s*(.+)$', skill_md_content, re.MULTILINE)
    if name_match:
        original_skill_name = name_match.group(1).strip()

    # Read optional schema.json
    schema_json = None
    if "schema.json" in file_map:
        try:
            schema_json = json.loads(file_map["schema.json"].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Read optional manifest.json
    manifest_json = None
    if "manifest.json" in file_map:
        try:
            manifest_json = json.loads(file_map["manifest.json"].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Skip compiled/build artifacts (consistent with _read_skill_files)
    _folder_skip_extensions = {
        ".pyc", ".pyo", ".pyd", ".class",
        ".o", ".a", ".so", ".dylib", ".dll", ".exe", ".wasm",
    }

    # Build other_files dict (excluding SKILL.md, schema.json, manifest.json)
    other_files: dict[str, tuple[bytes, str]] = {}
    skipped_files: list[str] = []
    excluded_files = {skill_md_key, "schema.json", "manifest.json"}

    for rel_path, content in file_map.items():
        if rel_path in excluded_files:
            continue

        # Skip hidden files and non-essential files
        basename = rel_path.rsplit("/", 1)[-1]
        if basename.startswith(".") or basename.endswith(".pyc"):
            continue
        if "__pycache__" in rel_path:
            continue
        if ".backup" in basename or "UPDATE_REPORT" in basename:
            continue

        # Skip compiled/build artifacts and track them
        suffix = ('.' + basename.rsplit('.', 1)[-1]).lower() if '.' in basename else ''
        if suffix in _folder_skip_extensions:
            skipped_files.append(rel_path)
            continue

        # Determine file type based on path
        file_type = "other"
        if rel_path.startswith("scripts/"):
            file_type = "script"
        elif rel_path.startswith("references/"):
            file_type = "reference"
        elif rel_path.startswith("assets/"):
            file_type = "asset"

        other_files[rel_path] = (content, file_type)

    # Use shared import logic
    return await _do_skill_import(
        original_skill_name=original_skill_name,
        skill_md_content=skill_md_content,
        other_files=other_files,
        schema_json=schema_json,
        manifest_json=manifest_json,
        check_only=check_only,
        conflict_action=conflict_action,
        source=f"folder: {folder_name or 'unknown'}",
        db=db,
        skipped_files=skipped_files,
    )


# GitHub import models and endpoint

class ImportGitHubRequest(BaseModel):
    url: str
    check_only: bool = False
    conflict_action: Optional[str] = None


def _parse_github_url(url: str) -> tuple[str, str, Optional[str], str]:
    """Parse GitHub URL and return (owner, repo, branch, path).

    Supports URLs like:
    - https://github.com/owner/repo (root of default branch)
    - https://github.com/owner/repo/tree/branch (root of specific branch)
    - https://github.com/owner/repo/tree/branch/path/to/skill (specific path)

    Returns: (owner, repo, branch, path)
        - branch is None when not specified (caller should fetch default branch)
    Raises: ValueError if URL format is invalid
    """
    parsed = urlparse(url)

    if parsed.netloc != "github.com":
        raise ValueError("URL must be from github.com")

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    # Minimum: owner/repo
    if len(path_parts) < 2:
        raise ValueError(
            "Invalid GitHub URL format. Expected at least: https://github.com/{owner}/{repo}"
        )

    owner = path_parts[0]
    repo = path_parts[1]

    # Case 1: https://github.com/owner/repo (just owner/repo, need to fetch default branch)
    if len(path_parts) == 2:
        return owner, repo, None, ""

    # Case 2: https://github.com/owner/repo/tree/branch[/path]
    if len(path_parts) >= 4 and path_parts[2] == "tree":
        branch = path_parts[3]
        skill_path = "/".join(path_parts[4:]) if len(path_parts) > 4 else ""
        return owner, repo, branch, skill_path

    # Case 3: Other formats (e.g., /blob/, /releases/, etc.) - not supported
    raise ValueError(
        "Invalid GitHub URL format. Supported formats:\n"
        "- https://github.com/owner/repo\n"
        "- https://github.com/owner/repo/tree/branch\n"
        "- https://github.com/owner/repo/tree/branch/path"
    )



def _get_github_token() -> Optional[str]:
    """Get GitHub token from .env file (single source of truth).

    In multi-worker deployments, os.environ is per-process and may hold stale
    values from startup. The .env file is shared across all workers and always
    reflects the latest value set via the Settings API.
    """
    try:
        from app.api.v1.settings import _read_env_file
        return _read_env_file().get("GITHUB_TOKEN") or None
    except Exception:
        return None


async def _get_github_default_branch(owner: str, repo: str, token: Optional[str] = None) -> str:
    """Fetch the default branch of a GitHub repository."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Skills-API",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repository {owner}/{repo} not found")
        if response.status_code == 403:
            raise HTTPException(status_code=403, detail="GitHub API rate limit exceeded")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")

        data = response.json()
        return data.get("default_branch", "main")


async def _fetch_github_contents(
    owner: str,
    repo: str,
    branch: str,
    path: str,
    token: Optional[str] = None,
) -> list[dict]:
    """Fetch directory contents from GitHub API.

    Returns list of file/directory entries.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Skills-API",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Path not found: {path} in {owner}/{repo}@{branch}",
            )
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
            raise HTTPException(
                status_code=429,
                detail=f"GitHub API rate limit exceeded. Remaining: {remaining}. Set GITHUB_TOKEN env var for higher limits.",
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}",
            )

        return response.json()


async def _fetch_github_file(
    owner: str,
    repo: str,
    branch: str,
    path: str,
    token: Optional[str] = None,
) -> bytes:
    """Fetch file content from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Skills-API",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if response.status_code == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded")
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}",
            )

        data = response.json()

        # Handle file content (base64 encoded)
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"])
        else:
            raise HTTPException(status_code=400, detail=f"Unexpected file format for {path}")


async def _fetch_github_directory_recursive(
    owner: str,
    repo: str,
    branch: str,
    base_path: str,
    rel_path: str = "",
    token: Optional[str] = None,
) -> dict[str, tuple[bytes, str]]:
    """Recursively fetch all files in a directory.

    Returns dict mapping relative paths to (content, file_type) tuples.
    """
    files = {}
    full_path = f"{base_path}/{rel_path}".rstrip("/")

    contents = await _fetch_github_contents(owner, repo, branch, full_path, token)

    # Contents API returns a single object for files, list for directories
    if isinstance(contents, dict):
        contents = [contents]

    for item in contents:
        item_name = item["name"]
        item_path = f"{rel_path}/{item_name}".lstrip("/") if rel_path else item_name

        # Skip hidden files, __pycache__, .pyc, etc.
        if item_name.startswith("."):
            continue
        if "__pycache__" in item_path or item_name.endswith(".pyc"):
            continue
        if ".backup" in item_name or "UPDATE_REPORT" in item_name:
            continue

        if item["type"] == "file":
            # Skip large files (>1MB)
            if item.get("size", 0) > 1024 * 1024:
                continue

            content = await _fetch_github_file(owner, repo, branch, item["path"], token)

            # Determine file type
            file_type = "other"
            if item_path.startswith("scripts/"):
                file_type = "script"
            elif item_path.startswith("references/"):
                file_type = "reference"
            elif item_path.startswith("assets/"):
                file_type = "asset"

            files[item_path] = (content, file_type)

        elif item["type"] == "dir":
            # Recursively fetch subdirectory
            sub_files = await _fetch_github_directory_recursive(
                owner, repo, branch, base_path, item_path, token
            )
            files.update(sub_files)

    return files


@router.post("/import-github", response_model=ImportSkillResponse)
async def import_skill_from_github(
    request: ImportGitHubRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import a skill from a GitHub repository URL.

    URL format: https://github.com/{owner}/{repo}/tree/{branch}/{path}

    Example: https://github.com/remotion-dev/skills/tree/main/skills/remotion

    If a skill with the same name exists:
    - With check_only=true: returns conflict info without importing
    - With conflict_action='copy': creates a copy with a new name
    - Without conflict_action: returns error (409 Conflict)
    """
    import json

    github_token = _get_github_token()

    # Parse URL
    try:
        owner, repo, branch, skill_path = _parse_github_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If branch is not specified, fetch the default branch from GitHub API
    if branch is None:
        branch = await _get_github_default_branch(owner, repo, github_token)

    # Derive skill name from path (last component) or repo name if path is empty
    if skill_path:
        original_skill_name = skill_path.rstrip("/").split("/")[-1]
    else:
        original_skill_name = repo

    # Fetch SKILL.md first to validate this is a skill directory
    try:
        skill_md_path = f"{skill_path}/SKILL.md" if skill_path else "SKILL.md"
        skill_md_content_bytes = await _fetch_github_file(
            owner, repo, branch, skill_md_path, github_token
        )
        skill_md_content = skill_md_content_bytes.decode("utf-8")
    except HTTPException as e:
        if e.status_code == 404:
            location = f"{skill_path}/SKILL.md" if skill_path else "SKILL.md (repository root)"
            raise HTTPException(
                status_code=400,
                detail=f"SKILL.md not found at {location}. Make sure the URL points to a valid skill directory.",
            )
        raise

    # Try to extract skill name from frontmatter
    name_match = re.search(r"^name:\s*(.+)$", skill_md_content, re.MULTILINE)
    if name_match:
        original_skill_name = name_match.group(1).strip().strip("\"'")

    # Fetch all files from GitHub
    try:
        other_files = await _fetch_github_directory_recursive(
            owner, repo, branch, skill_path, "", github_token
        )
        # Remove SKILL.md from other_files if present (we already have it)
        other_files.pop("SKILL.md", None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch files from GitHub: {str(e)}")

    # Read optional schema.json
    schema_json = None
    if "schema.json" in other_files:
        try:
            schema_json = json.loads(other_files.pop("schema.json")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Read optional manifest.json
    manifest_json = None
    if "manifest.json" in other_files:
        try:
            manifest_json = json.loads(other_files.pop("manifest.json")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Filter compiled/build artifacts from fetched files
    _gh_skip_extensions = {
        ".pyc", ".pyo", ".pyd", ".class",
        ".o", ".a", ".so", ".dylib", ".dll", ".exe", ".wasm",
    }
    skipped_files: list[str] = []
    filtered_files: dict[str, tuple[bytes, str]] = {}
    for rel_path, value in other_files.items():
        basename = rel_path.rsplit("/", 1)[-1]
        suffix = ('.' + basename.rsplit('.', 1)[-1]).lower() if '.' in basename else ''
        if suffix in _gh_skip_extensions:
            skipped_files.append(rel_path)
        else:
            filtered_files[rel_path] = value

    # Use shared import logic
    return await _do_skill_import(
        original_skill_name=original_skill_name,
        skill_md_content=skill_md_content,
        other_files=filtered_files,
        schema_json=schema_json,
        manifest_json=manifest_json,
        check_only=request.check_only,
        conflict_action=request.conflict_action,
        source=f"GitHub: {request.url}",
        db=db,
        source_url=request.url,
        author=owner,
        skipped_files=skipped_files,
    )


# Update from source — shared response model and helper

class UpdateFromSourceResponse(BaseModel):
    success: bool
    skill_name: str
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    message: str
    changes: Optional[List[str]] = None

# Backward-compatible alias
UpdateFromGitHubResponse = UpdateFromSourceResponse


async def _compare_and_create_version(
    skill,
    new_skill_md: str,
    new_files: dict[str, tuple[bytes, str]],
    new_schema_json: Optional[dict],
    new_manifest_json: Optional[dict],
    commit_message: str,
    db: AsyncSession,
) -> UpdateFromSourceResponse:
    """Compare new content against current version and create a new version if changes exist."""
    name = skill.name
    service = SkillService(db)

    current_version = skill.current_version
    if not current_version:
        raise HTTPException(status_code=400, detail=f"Skill '{name}' has no current version")

    current_ver = await service.version_repo.get_by_skill_and_version(skill.id, current_version)
    if not current_ver:
        raise HTTPException(status_code=500, detail=f"Current version {current_version} not found")

    current_skill_md = current_ver.skill_md or ""
    current_files = await service.version_repo.get_files(current_ver.id)
    current_files_dict = {f.file_path: f.content for f in current_files if f.content}

    # Compare to detect changes
    changes = []

    if new_skill_md != current_skill_md:
        changes.append("SKILL.md")

    for file_path, (new_content, _) in new_files.items():
        old_content = current_files_dict.get(file_path)
        if old_content is None:
            changes.append(f"+ {file_path}")
        elif old_content != new_content:
            changes.append(f"~ {file_path}")

    new_file_paths = set(new_files.keys())
    for old_path in current_files_dict.keys():
        if old_path not in new_file_paths:
            changes.append(f"- {old_path}")

    if not changes:
        return UpdateFromSourceResponse(
            success=True,
            skill_name=name,
            old_version=current_version,
            new_version=None,
            message="No changes detected. Skill is up to date.",
            changes=[],
        )

    # Increment version
    parts = current_version.split(".")
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split("-")[0])
        new_version = f"{major}.{minor}.{patch + 1}"
    except (IndexError, ValueError):
        new_version = "0.0.1"

    ver = await service.version_repo.create(
        skill_id=skill.id,
        version=new_version,
        skill_md=new_skill_md,
        schema_json=new_schema_json,
        manifest_json=new_manifest_json,
        parent_version=current_version,
        created_by=None,
        commit_message=commit_message,
    )

    for rel_path, (file_content, file_type) in new_files.items():
        content_hash = hashlib.sha256(file_content).hexdigest()
        await service.version_repo.add_file(
            version_id=ver.id,
            file_path=rel_path,
            file_type=file_type,
            content=file_content,
            content_hash=content_hash,
            size_bytes=len(file_content),
        )

    await service.skill_repo.set_current_version(skill.id, new_version)

    await service.skill_repo.add_changelog(
        skill_id=skill.id,
        change_type="update",
        version_from=current_version,
        version_to=new_version,
        changed_by=None,
        comment=commit_message,
    )

    # Update disk files — clear directory and rewrite from new version
    skills_dir = Path(settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / name
    if skill_dir.exists():
        import shutil
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "SKILL.md").write_text(new_skill_md, encoding="utf-8")

    for rel_path, (file_content, file_type) in new_files.items():
        out_path = skill_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(file_content)

    await db.commit()

    return UpdateFromSourceResponse(
        success=True,
        skill_name=name,
        old_version=current_version,
        new_version=new_version,
        message=f"Updated from v{current_version} to v{new_version}",
        changes=changes,
    )


class CheckGithubUpdatesResponse(BaseModel):
    results: dict[str, dict]  # skill_name -> { has_update: bool }


def _git_blob_sha(content: bytes) -> str:
    """Compute git blob SHA-1 hash (same algorithm git uses for blob objects)."""
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


async def _fetch_github_tree(
    owner: str,
    repo: str,
    branch: str,
    token: Optional[str] = None,
) -> Optional[list[dict]]:
    """Fetch full repo tree using Git Trees API (single API call).

    Returns list of tree entries with {path, sha, type, ...}, or None if truncated.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Skills-API",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        if response.status_code != 200:
            return None
        data = response.json()
        if data.get("truncated"):
            return None
        return data.get("tree", [])


@router.post("/skills/check-github-updates", response_model=CheckGithubUpdatesResponse)
async def check_github_updates(
    db: AsyncSession = Depends(get_db),
):
    """Batch check which GitHub-sourced skills have updates available.

    Groups skills by (owner, repo, branch) to minimize API calls.
    Uses Git Trees API for efficient SHA comparison.
    """
    from app.db.models import SkillDB, SkillVersionDB, SkillFileDB

    # 1. Get all skills with GitHub source
    stmt = sa_select(SkillDB).where(
        SkillDB.source.isnot(None),
        SkillDB.source.like("https://github.com%"),
    )
    result = await db.execute(stmt)
    github_skills = result.scalars().all()

    if not github_skills:
        return CheckGithubUpdatesResponse(results={})

    github_token = _get_github_token()
    results: dict[str, dict] = {}

    # 2. Group by (owner, repo, branch) to share API calls
    repo_groups: dict[tuple[str, str, str], list[tuple]] = {}
    for skill in github_skills:
        try:
            owner, repo, branch, skill_path = _parse_github_url(skill.source)
        except (ValueError, Exception):
            continue

        if branch is None:
            try:
                branch = await _get_github_default_branch(owner, repo, github_token)
            except Exception:
                continue

        key = (owner, repo, branch)
        if key not in repo_groups:
            repo_groups[key] = []
        repo_groups[key].append((skill, skill_path))

    # 3. For each repo group, fetch tree once
    for (owner, repo, branch), skill_list in repo_groups.items():
        try:
            tree_entries = await _fetch_github_tree(owner, repo, branch, github_token)
        except Exception:
            tree_entries = None

        if tree_entries is None:
            # Fallback: use contents API per skill (slower)
            for skill, skill_path in skill_list:
                try:
                    remote_shas = await _collect_remote_shas_via_contents(
                        owner, repo, branch, skill_path, github_token
                    )
                    has_update = await _compare_skill_shas(skill, remote_shas, db)
                    results[skill.name] = {"has_update": has_update}
                except Exception:
                    pass
            continue

        # Build path -> sha map from tree
        tree_map: dict[str, str] = {}
        for entry in tree_entries:
            if entry.get("type") == "blob":
                tree_map[entry["path"]] = entry["sha"]

        # 4. For each skill in this repo group, compare
        for skill, skill_path in skill_list:
            try:
                # Filter tree entries by skill's path prefix
                prefix = f"{skill_path}/" if skill_path else ""
                remote_shas: dict[str, str] = {}
                for path, sha in tree_map.items():
                    if prefix:
                        if path.startswith(prefix):
                            rel_path = path[len(prefix):]
                            remote_shas[rel_path] = sha
                    else:
                        remote_shas[path] = sha

                has_update = await _compare_skill_shas(skill, remote_shas, db)
                results[skill.name] = {"has_update": has_update}
            except Exception:
                pass

    return CheckGithubUpdatesResponse(results=results)


async def _collect_remote_shas_via_contents(
    owner: str,
    repo: str,
    branch: str,
    skill_path: str,
    token: Optional[str],
) -> dict[str, str]:
    """Fallback: collect file SHAs using Contents API (recursive directory listing)."""
    shas: dict[str, str] = {}

    async def _walk(rel_path: str):
        full_path = f"{skill_path}/{rel_path}".rstrip("/") if skill_path else rel_path.rstrip("/")
        if not full_path:
            full_path = skill_path or ""
        try:
            contents = await _fetch_github_contents(owner, repo, branch, full_path, token)
        except Exception:
            return
        if isinstance(contents, dict):
            contents = [contents]
        for item in contents:
            item_name = item.get("name", "")
            item_rel = f"{rel_path}/{item_name}".lstrip("/") if rel_path else item_name
            if item.get("type") == "file" and item.get("sha"):
                shas[item_rel] = item["sha"]
            elif item.get("type") == "dir":
                await _walk(item_rel)

    await _walk("")
    return shas


async def _compare_skill_shas(
    skill,
    remote_shas: dict[str, str],
    db: AsyncSession,
) -> bool:
    """Compare local skill files against remote SHAs. Returns True if there's an update."""
    from app.db.models import SkillVersionDB, SkillFileDB

    if not skill.current_version:
        return bool(remote_shas)

    # Get current version
    stmt = sa_select(SkillVersionDB).where(
        SkillVersionDB.skill_id == skill.id,
        SkillVersionDB.version == skill.current_version,
    )
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()
    if not version:
        return bool(remote_shas)

    # Build local SHA map
    local_shas: dict[str, str] = {}

    # SKILL.md
    if version.skill_md:
        local_shas["SKILL.md"] = _git_blob_sha(version.skill_md.encode("utf-8"))

    # Other files
    stmt = sa_select(SkillFileDB).where(SkillFileDB.version_id == version.id)
    result = await db.execute(stmt)
    files = result.scalars().all()
    for f in files:
        if f.content:
            local_shas[f.file_path] = _git_blob_sha(f.content)

    # Compare: filter remote to only files we care about (skip hidden, __pycache__, etc.)
    filtered_remote: dict[str, str] = {}
    for path, sha in remote_shas.items():
        # Skip hidden files/dirs
        parts = path.split("/")
        if any(p.startswith(".") for p in parts):
            continue
        if any(p == "__pycache__" for p in parts):
            continue
        # Skip compiled artifacts
        if path.endswith((".pyc", ".pyo", ".class", ".o", ".so", ".dll")):
            continue
        filtered_remote[path] = sha

    # Any difference in keys or SHA values means update available
    if set(local_shas.keys()) != set(filtered_remote.keys()):
        return True

    for path, local_sha in local_shas.items():
        if filtered_remote.get(path) != local_sha:
            return True

    return False


@router.post("/skills/{name}/update-from-github", response_model=UpdateFromSourceResponse)
async def update_skill_from_github(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Update a skill by fetching the latest version from its GitHub source.

    This endpoint only works for skills that were imported from GitHub
    (i.e., have a source field starting with https://github.com).

    Returns the new version if changes were detected, or a message if no changes.
    """
    import json

    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    if not skill.source or not skill.source.startswith("https://github.com"):
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{name}' was not imported from GitHub. Cannot update from source."
        )

    github_token = _get_github_token()

    try:
        owner, repo, branch, skill_path = _parse_github_url(skill.source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid source URL: {str(e)}")

    if branch is None:
        branch = await _get_github_default_branch(owner, repo, github_token)

    try:
        skill_md_path = f"{skill_path}/SKILL.md" if skill_path else "SKILL.md"
        new_skill_md_bytes = await _fetch_github_file(
            owner, repo, branch, skill_md_path, github_token
        )
        new_skill_md_content = new_skill_md_bytes.decode("utf-8")
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail=f"SKILL.md not found at GitHub source. The source repository may have changed."
            )
        raise

    try:
        new_files = await _fetch_github_directory_recursive(
            owner, repo, branch, skill_path, "", github_token
        )
        new_files.pop("SKILL.md", None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch files from GitHub: {str(e)}")

    new_schema_json = None
    if "schema.json" in new_files:
        try:
            new_schema_json = json.loads(new_files.pop("schema.json")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    new_manifest_json = None
    if "manifest.json" in new_files:
        try:
            new_manifest_json = json.loads(new_files.pop("manifest.json")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Update author from GitHub owner
    if skill.author != owner:
        skill.author = owner
        await db.commit()

    return await _compare_and_create_version(
        skill=skill,
        new_skill_md=new_skill_md_content,
        new_files=new_files,
        new_schema_json=new_schema_json,
        new_manifest_json=new_manifest_json,
        commit_message=f"Updated from GitHub: {skill.source}",
        db=db,
    )


# --- Update from external source endpoints ---

class UpdateFromSourceGitHubRequest(BaseModel):
    url: str


@router.post("/skills/{name}/update-from-source-github", response_model=UpdateFromSourceResponse)
async def update_skill_from_source_github(
    name: str,
    body: UpdateFromSourceGitHubRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing skill by fetching content from an arbitrary GitHub URL."""
    import json

    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    github_token = _get_github_token()

    try:
        owner, repo, branch, skill_path = _parse_github_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid GitHub URL: {str(e)}")

    if branch is None:
        branch = await _get_github_default_branch(owner, repo, github_token)

    try:
        skill_md_path = f"{skill_path}/SKILL.md" if skill_path else "SKILL.md"
        new_skill_md_bytes = await _fetch_github_file(
            owner, repo, branch, skill_md_path, github_token
        )
        new_skill_md_content = new_skill_md_bytes.decode("utf-8")
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail="SKILL.md not found at the specified GitHub URL."
            )
        raise

    try:
        new_files = await _fetch_github_directory_recursive(
            owner, repo, branch, skill_path, "", github_token
        )
        new_files.pop("SKILL.md", None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch files from GitHub: {str(e)}")

    new_schema_json = None
    if "schema.json" in new_files:
        try:
            new_schema_json = json.loads(new_files.pop("schema.json")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    new_manifest_json = None
    if "manifest.json" in new_files:
        try:
            new_manifest_json = json.loads(new_files.pop("manifest.json")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return await _compare_and_create_version(
        skill=skill,
        new_skill_md=new_skill_md_content,
        new_files=new_files,
        new_schema_json=new_schema_json,
        new_manifest_json=new_manifest_json,
        commit_message=f"Updated from GitHub: {body.url}",
        db=db,
    )


@router.post("/skills/{name}/update-from-source-file", response_model=UpdateFromSourceResponse)
async def update_skill_from_source_file(
    name: str,
    file: UploadFile = File(..., description="The .skill or .zip file"),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing skill by uploading a .skill or .zip file."""
    import json

    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    if not file.filename or not (file.filename.endswith('.skill') or file.filename.endswith('.zip')):
        raise HTTPException(status_code=400, detail="File must have .skill or .zip extension")

    content = await file.read()

    try:
        zip_buffer = io.BytesIO(content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            if not file_list:
                raise HTTPException(status_code=400, detail="Empty archive")

            flat_layout = 'SKILL.md' in file_list
            if flat_layout:
                prefix = ''
            else:
                first_file = file_list[0]
                wrapper_dir = first_file.split('/')[0]
                prefix = f"{wrapper_dir}/"

            skill_md_path = f"{prefix}SKILL.md"
            if skill_md_path not in file_list:
                raise HTTPException(status_code=400, detail="SKILL.md not found in archive")

            new_skill_md_content = zf.read(skill_md_path).decode('utf-8')

            schema_json = None
            schema_path = f"{prefix}schema.json"
            if schema_path in file_list:
                try:
                    schema_json = json.loads(zf.read(schema_path).decode('utf-8'))
                except json.JSONDecodeError:
                    pass

            manifest_json = None
            manifest_path = f"{prefix}manifest.json"
            if manifest_path in file_list:
                try:
                    manifest_json = json.loads(zf.read(manifest_path).decode('utf-8'))
                except json.JSONDecodeError:
                    pass

            _zip_skip_extensions = {
                ".pyc", ".pyo", ".pyd", ".class",
                ".o", ".a", ".so", ".dylib", ".dll", ".exe", ".wasm",
            }

            other_files: dict[str, tuple[bytes, str]] = {}
            for fp in file_list:
                if prefix and not fp.startswith(prefix):
                    continue
                rel_path = fp[len(prefix):]
                if rel_path in ['SKILL.md', 'schema.json', 'manifest.json', '']:
                    continue
                if fp.endswith('/'):
                    continue
                basename = rel_path.rsplit('/', 1)[-1]
                if basename.startswith('.') or basename.endswith('.pyc'):
                    continue
                if '__pycache__' in rel_path:
                    continue
                if '.backup' in basename or 'UPDATE_REPORT' in basename:
                    continue
                suffix = ('.' + basename.rsplit('.', 1)[-1]).lower() if '.' in basename else ''
                if suffix in _zip_skip_extensions:
                    continue
                try:
                    file_content = zf.read(fp)
                    file_type = 'other'
                    if rel_path.startswith('scripts/'):
                        file_type = 'script'
                    elif rel_path.startswith('references/'):
                        file_type = 'reference'
                    elif rel_path.startswith('assets/'):
                        file_type = 'asset'
                    other_files[rel_path] = (file_content, file_type)
                except Exception:
                    continue

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")

    return await _compare_and_create_version(
        skill=skill,
        new_skill_md=new_skill_md_content,
        new_files=other_files,
        new_schema_json=schema_json,
        new_manifest_json=manifest_json,
        commit_message=f"Updated from file: {file.filename or 'uploaded file'}",
        db=db,
    )


@router.post("/skills/{name}/update-from-source-folder", response_model=UpdateFromSourceResponse)
async def update_skill_from_source_folder(
    name: str,
    files: List[UploadFile] = File(..., description="Files from a folder (must include SKILL.md)"),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing skill by uploading a folder containing SKILL.md."""
    import json

    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    file_map: dict[str, bytes] = {}
    for f in files:
        if not f.filename:
            continue
        file_content = await f.read()
        parts = f.filename.replace("\\", "/").split("/")
        if len(parts) > 1:
            rel_path = "/".join(parts[1:])
        else:
            rel_path = parts[0]
        file_map[rel_path] = file_content

    if not file_map:
        raise HTTPException(status_code=400, detail="No valid files found in folder")

    skill_md_content: Optional[str] = None
    skill_md_key: Optional[str] = None
    for key in file_map:
        if key.upper() == "SKILL.MD":
            skill_md_key = key
            try:
                skill_md_content = file_map[key].decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="SKILL.md is not a valid UTF-8 text file")
            break

    if not skill_md_content:
        raise HTTPException(status_code=400, detail="Folder must contain a SKILL.md file at the root level")

    schema_json = None
    if "schema.json" in file_map:
        try:
            schema_json = json.loads(file_map["schema.json"].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    manifest_json = None
    if "manifest.json" in file_map:
        try:
            manifest_json = json.loads(file_map["manifest.json"].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    _folder_skip_extensions = {
        ".pyc", ".pyo", ".pyd", ".class",
        ".o", ".a", ".so", ".dylib", ".dll", ".exe", ".wasm",
    }

    other_files: dict[str, tuple[bytes, str]] = {}
    excluded_files = {skill_md_key, "schema.json", "manifest.json"}

    for rel_path, content in file_map.items():
        if rel_path in excluded_files:
            continue
        basename = rel_path.rsplit("/", 1)[-1]
        if basename.startswith(".") or basename.endswith(".pyc"):
            continue
        if "__pycache__" in rel_path:
            continue
        if ".backup" in basename or "UPDATE_REPORT" in basename:
            continue
        suffix = ('.' + basename.rsplit('.', 1)[-1]).lower() if '.' in basename else ''
        if suffix in _folder_skip_extensions:
            continue
        file_type = "other"
        if rel_path.startswith("scripts/"):
            file_type = "script"
        elif rel_path.startswith("references/"):
            file_type = "reference"
        elif rel_path.startswith("assets/"):
            file_type = "asset"
        other_files[rel_path] = (content, file_type)

    return await _compare_and_create_version(
        skill=skill,
        new_skill_md=skill_md_content,
        new_files=other_files,
        new_schema_json=schema_json,
        new_manifest_json=manifest_json,
        commit_message="Updated from folder upload",
        db=db,
    )


# Validation endpoint

@router.post("/validate")
async def validate_skill(
    skill_md: Optional[str] = None,
    schema_json: Optional[dict] = None,
    manifest_json: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
) -> ValidationResult:
    """Validate a skill package without saving."""
    service = SkillService(db)
    return await service.validate_skill(
        skill_md=skill_md,
        schema_json=schema_json,
        manifest_json=manifest_json,
    )


# ============ Skill Environment Config Endpoints ============

from typing import Dict, Any
from app.core.skill_config import (
    get_skill_config,
    get_skill_required_env,
    set_skill_config,
    delete_skill_config,
    list_skill_configs,
    get_skill_secret,
    set_skill_secret,
    delete_skill_secret,
    get_skill_secrets_status,
    get_all_skills_secrets_status,
    check_skill_env_ready,
    # Dependencies management
    check_skill_has_setup_script,
    get_skill_dependencies_status,
    set_skill_dependencies_installed,
    get_skill_dependencies_log,
)


class SkillEnvVar(BaseModel):
    name: str
    description: str = ""
    secret: bool = False
    default: Optional[str] = None


class SkillConfigRequest(BaseModel):
    required_env: List[SkillEnvVar]


class SkillConfigResponse(BaseModel):
    skill_name: str
    required_env: List[SkillEnvVar]


class SecretStatus(BaseModel):
    configured: bool
    source: str  # "secrets", "env", "default", or "none"
    secret: bool
    description: str


class SkillSecretsStatusResponse(BaseModel):
    skill_name: str
    ready: bool
    missing: List[str]
    status: Dict[str, SecretStatus]


class SetSecretRequest(BaseModel):
    value: str


@router.get("/skill-configs")
async def list_all_skill_configs() -> Dict[str, Any]:
    """List all skill configurations."""
    configs = list_skill_configs()
    return {"skills": configs}


@router.get("/skill-configs/{name}", response_model=SkillConfigResponse)
async def get_skill_config_endpoint(name: str):
    """Get configuration for a specific skill."""
    config = get_skill_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"No config found for skill '{name}'")

    required_env = config.get("required_env", [])
    return SkillConfigResponse(
        skill_name=name,
        required_env=[SkillEnvVar(**env) for env in required_env]
    )


@router.put("/skill-configs/{name}", response_model=SkillConfigResponse)
async def set_skill_config_endpoint(name: str, request: SkillConfigRequest):
    """Set configuration for a skill."""
    required_env = [env.model_dump() for env in request.required_env]
    set_skill_config(name, required_env)
    return SkillConfigResponse(
        skill_name=name,
        required_env=request.required_env
    )


@router.delete("/skill-configs/{name}")
async def delete_skill_config_endpoint(name: str):
    """Delete configuration for a skill."""
    if not delete_skill_config(name):
        raise HTTPException(status_code=404, detail=f"No config found for skill '{name}'")
    return {"message": f"Config for skill '{name}' deleted"}


@router.get("/skill-secrets")
async def get_all_secrets_status_endpoint() -> Dict[str, Any]:
    """Get secrets configuration status for all skills."""
    return {"skills": get_all_skills_secrets_status()}


@router.get("/skills/{name}/secrets", response_model=SkillSecretsStatusResponse)
async def get_skill_secrets_status_endpoint(name: str):
    """Get secrets configuration status for a specific skill."""
    required_env = get_skill_required_env(name)
    if not required_env:
        raise HTTPException(status_code=404, detail=f"No config found for skill '{name}'")

    ready, missing = check_skill_env_ready(name)
    status = get_skill_secrets_status(name)

    return SkillSecretsStatusResponse(
        skill_name=name,
        ready=ready,
        missing=missing,
        status={k: SecretStatus(**v) for k, v in status.items()}
    )


@router.put("/skills/{name}/secrets/{key_name}")
async def set_skill_secret_endpoint(name: str, key_name: str, request: SetSecretRequest):
    """Set a secret value for a skill."""
    required_env = get_skill_required_env(name)
    if not required_env:
        raise HTTPException(status_code=404, detail=f"No config found for skill '{name}'")

    # Verify key is in required_env
    valid_keys = [env.get("name") for env in required_env]
    if key_name not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Key '{key_name}' is not a required environment variable for skill '{name}'"
        )

    set_skill_secret(name, key_name, request.value)
    return {"message": f"Secret '{key_name}' for skill '{name}' saved", "source": "secrets"}


@router.delete("/skills/{name}/secrets/{key_name}")
async def delete_skill_secret_endpoint(name: str, key_name: str):
    """Delete a secret value for a skill."""
    if not delete_skill_secret(name, key_name):
        raise HTTPException(
            status_code=404,
            detail=f"Secret '{key_name}' for skill '{name}' not found in secrets file"
        )
    return {"message": f"Secret '{key_name}' for skill '{name}' deleted"}


# ============ Skill Dependencies Endpoints ============

class DependenciesStatusResponse(BaseModel):
    skill_name: str
    has_setup_script: bool
    setup_script_path: Optional[str] = None
    last_installed_at: Optional[str] = None
    last_install_success: Optional[bool] = None
    needs_install: bool


class InstallDependenciesTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class InstallTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    error: Optional[str] = None
    install_log: Optional[str] = None


@router.get("/skills/{name}/dependencies", response_model=DependenciesStatusResponse)
async def get_skill_dependencies(name: str):
    """Get the dependency installation status for a skill."""
    status = get_skill_dependencies_status(name)
    return DependenciesStatusResponse(**status)


def _run_dependency_installation(task_id: str, skill_name: str, setup_script_path: str):
    """Background function to run setup.sh for a skill."""
    import subprocess
    import os

    try:
        # Get the skill directory (parent of setup.sh)
        skill_dir = str(Path(setup_script_path).parent)

        # Run setup.sh with bash
        result = subprocess.run(
            ["bash", setup_script_path],
            cwd=skill_dir,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            env={**os.environ, "SKILL_DIR": skill_dir, "SKILL_NAME": skill_name},
        )

        # Combine stdout and stderr
        log = ""
        if result.stdout:
            log += result.stdout
        if result.stderr:
            if log:
                log += "\n--- stderr ---\n"
            log += result.stderr

        success = result.returncode == 0

        # Record result
        set_skill_dependencies_installed(skill_name, success, log)

        if not success:
            raise Exception(f"setup.sh exited with code {result.returncode}")

        return {"skill_name": skill_name, "success": True, "install_log": log}

    except subprocess.TimeoutExpired:
        error_log = "Installation timed out after 10 minutes"
        set_skill_dependencies_installed(skill_name, False, error_log)
        raise Exception(error_log)
    except Exception as e:
        # If we haven't already recorded the failure, record it now
        if "setup.sh exited with code" not in str(e):
            set_skill_dependencies_installed(skill_name, False, str(e))
        raise


@router.post("/skills/{name}/install-dependencies", response_model=InstallDependenciesTaskResponse, status_code=202)
async def install_skill_dependencies(name: str):
    """Install dependencies for a skill by running its setup.sh."""
    # Check if setup.sh exists
    has_script, script_path = check_skill_has_setup_script(name)
    if not has_script:
        raise HTTPException(
            status_code=404,
            detail=f"No setup.sh found for skill '{name}'"
        )

    # Create task and run in background
    task = await task_manager.create_task_async(
        task_type="install_dependencies",
        metadata={"skill_name": name}
    )

    task_manager.run_in_background(
        task.id,
        _run_dependency_installation,
        task.id,
        name,
        script_path,
    )

    return InstallDependenciesTaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Dependency installation started. Poll /api/v1/registry/tasks/{task.id} for status.",
    )


@router.post("/skills/{name}/install-dependencies/stream")
async def install_skill_dependencies_stream(name: str):
    """Install dependencies for a skill with streaming output."""
    import asyncio
    import subprocess
    import os
    from fastapi.responses import StreamingResponse

    # Check if setup.sh exists
    has_script, script_path = check_skill_has_setup_script(name)
    if not has_script:
        raise HTTPException(
            status_code=404,
            detail=f"No setup.sh found for skill '{name}'"
        )

    skill_dir = str(Path(script_path).parent)

    async def generate():
        import json

        process = None
        full_log = []
        success = False

        try:
            # Start the process
            process = subprocess.Popen(
                ["bash", script_path],
                cwd=skill_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ, "SKILL_DIR": skill_dir, "SKILL_NAME": name},
            )

            # Send start event
            yield f"data: {json.dumps({'event': 'start', 'skill_name': name})}\n\n"

            # Stream output line by line
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                full_log.append(line)
                yield f"data: {json.dumps({'event': 'log', 'line': line})}\n\n"
                await asyncio.sleep(0)  # Allow other tasks to run

            # Wait for process to complete
            process.wait()
            success = process.returncode == 0

            # Record result
            log_text = ''.join(full_log)
            set_skill_dependencies_installed(name, success, log_text)

            # Send complete event
            yield f"data: {json.dumps({'event': 'complete', 'success': success, 'return_code': process.returncode})}\n\n"

        except Exception as e:
            error_msg = str(e)
            full_log.append(f"\nError: {error_msg}")
            log_text = ''.join(full_log)
            set_skill_dependencies_installed(name, False, log_text)
            yield f"data: {json.dumps({'event': 'error', 'message': error_msg})}\n\n"

        finally:
            if process and process.poll() is None:
                process.terminate()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/skills/{name}/dependencies/log")
async def get_skill_dependencies_log_endpoint(name: str):
    """Get the last installation log for a skill."""
    log = get_skill_dependencies_log(name)
    if log is None:
        raise HTTPException(
            status_code=404,
            detail=f"No installation log found for skill '{name}'"
        )
    return {"skill_name": name, "install_log": log}


# ============ Skill Icon Endpoints ============

import mimetypes
import shutil


class IconUploadResponse(BaseModel):
    skill_name: str
    icon_url: str
    message: str


ALLOWED_ICON_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
MAX_ICON_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/skills/{name}/icon", response_model=IconUploadResponse)
async def upload_skill_icon(
    name: str,
    file: UploadFile = File(..., description="Icon image file (PNG, JPG, WebP, or SVG, max 2MB)"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a custom icon for a skill."""
    # Verify skill exists
    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_ICON_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_ICON_EXTENSIONS)}"
        )

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_ICON_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size: 2MB")

    # Create icons directory if needed
    icons_dir = Path(settings.upload_dir) / "skill-icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Remove old icon if exists (any extension)
    for old_ext in ALLOWED_ICON_EXTENSIONS:
        old_path = icons_dir / f"{name}{old_ext}"
        if old_path.exists():
            old_path.unlink()

    # Save new icon
    icon_filename = f"{name}{ext}"
    icon_path = icons_dir / icon_filename
    icon_path.write_bytes(content)

    # Update skill's icon_url in database
    icon_url = f"/api/v1/files/skill-icons/{icon_filename}"
    await service.skill_repo.update(skill.id, icon_url=icon_url)
    await db.commit()

    return IconUploadResponse(
        skill_name=name,
        icon_url=icon_url,
        message=f"Icon uploaded successfully"
    )


@router.delete("/skills/{name}/icon", status_code=204)
async def delete_skill_icon(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a skill's custom icon."""
    # Verify skill exists
    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    if not skill.icon_url:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' has no icon")

    # Delete icon file
    icons_dir = Path(settings.upload_dir) / "skill-icons"
    for ext in ALLOWED_ICON_EXTENSIONS:
        icon_path = icons_dir / f"{name}{ext}"
        if icon_path.exists():
            icon_path.unlink()

    # Clear icon_url in database
    await service.skill_repo.update(skill.id, icon_url=None)
    await db.commit()


class GenerateIconRequest(BaseModel):
    prompt: Optional[str] = None  # Optional custom prompt, will be auto-generated if not provided


class GenerateIconResponse(BaseModel):
    skill_name: str
    icon_url: str
    message: str


@router.post("/skills/{name}/generate-icon", response_model=GenerateIconResponse)
async def generate_skill_icon(
    name: str,
    request: GenerateIconRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate an icon for a skill using AI (Gemini Imagen 3).

    If no prompt is provided, automatically generates a prompt based on the skill name and description.
    """
    from app.tools.mcp_client import call_mcp_tool

    # Verify skill exists
    service = SkillService(db)
    skill = await service.skill_repo.get_by_name(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    # Build prompt
    if request and request.prompt:
        icon_prompt = request.prompt
    else:
        # Auto-generate prompt based on skill name and description
        skill_desc = skill.description or name.replace("-", " ")
        icon_prompt = (
            f"A clean, modern, minimalist icon representing '{skill_desc}'. "
            f"Flat design style, suitable as a software skill icon. "
            f"Simple shapes, vibrant colors, no text, white or transparent background."
        )

    # Create icons directory if needed
    icons_dir = Path(settings.upload_dir) / "skill-icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Remove old icon if exists
    for old_ext in ALLOWED_ICON_EXTENSIONS:
        old_path = icons_dir / f"{name}{old_ext}"
        if old_path.exists():
            old_path.unlink()

    # Output path for generated icon
    icon_filename = f"{name}.png"
    icon_path = icons_dir / icon_filename

    # Call Gemini MCP to generate image
    try:
        result = call_mcp_tool(
            server_name="gemini",
            tool_name="gemini_generate_image",
            arguments={
                "prompt": icon_prompt,
                "outputPath": str(icon_path),
                "aspectRatio": "1:1",
                "negativePrompt": "text, words, letters, numbers, watermark, signature, blurry, low quality",
            },
        )

        # Check if generation was successful
        if isinstance(result, dict) and result.get("success") is False:
            error_msg = result.get("error", "Unknown error")
            raise HTTPException(status_code=500, detail=f"Icon generation failed: {error_msg}")

        # Verify the file was created
        if not icon_path.exists():
            raise HTTPException(status_code=500, detail="Icon generation failed: File not created")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Icon generation failed: {str(e)}")

    # Update skill's icon_url in database
    icon_url = f"/api/v1/files/skill-icons/{icon_filename}"
    await service.skill_repo.update(skill.id, icon_url=icon_url)
    await db.commit()

    return GenerateIconResponse(
        skill_name=name,
        icon_url=icon_url,
        message="Icon generated successfully"
    )
