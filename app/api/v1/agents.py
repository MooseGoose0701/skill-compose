"""
Agent Presets API endpoints.

Provides endpoints for:
- Listing agent presets
- Getting preset details
- Creating new presets
- Updating presets
- Deleting presets
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import AgentPresetDB


router = APIRouter(prefix="/agents", tags=["agents"])


# Request/Response models
class AgentPresetBase(BaseModel):
    """Base model for agent preset."""
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    skill_ids: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    builtin_tools: Optional[List[str]] = None
    max_turns: int = Field(default=60, ge=1, le=60000)
    model_provider: Optional[str] = Field(None, description="LLM provider: anthropic, openrouter, openai, google")
    model_name: Optional[str] = Field(None, description="Model name/ID for the provider")
    executor_name: Optional[str] = Field(None, description="Executor name for code execution environment")


class AgentPresetCreate(AgentPresetBase):
    """Request model for creating agent preset."""
    pass


class AgentPresetUpdate(BaseModel):
    """Request model for updating agent preset."""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    skill_ids: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    builtin_tools: Optional[List[str]] = None
    max_turns: Optional[int] = Field(None, ge=1, le=60000)
    model_provider: Optional[str] = Field(None, description="LLM provider: anthropic, openrouter, openai, google")
    model_name: Optional[str] = Field(None, description="Model name/ID for the provider")
    executor_name: Optional[str] = Field(None, description="Executor name for code execution environment")
    is_published: Optional[bool] = None


class PublishAgentRequest(BaseModel):
    """Request model for publishing an agent."""
    api_response_mode: str = Field(
        ...,
        description="API response mode: 'streaming' or 'non_streaming'",
        pattern="^(streaming|non_streaming)$"
    )


class AgentPresetResponse(BaseModel):
    """Response model for agent preset."""
    id: str
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    skill_ids: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    builtin_tools: Optional[List[str]] = None
    max_turns: int
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    executor_name: Optional[str] = None
    is_system: bool
    is_published: bool
    api_response_mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AgentPresetListResponse(BaseModel):
    """Response for listing agent presets."""
    presets: List[AgentPresetResponse]
    total: int


@router.get("", response_model=AgentPresetListResponse)
async def list_agent_presets(
    is_system: Optional[bool] = Query(None, description="Filter by system preset"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all agent presets.

    Returns presets ordered by: system presets first, then by name.
    """
    query = select(AgentPresetDB)

    if is_system is not None:
        query = query.where(AgentPresetDB.is_system == is_system)

    # Order by is_system desc (system first), then by name
    query = query.order_by(desc(AgentPresetDB.is_system), AgentPresetDB.name)

    result = await db.execute(query)
    presets = result.scalars().all()

    return AgentPresetListResponse(
        presets=[
            AgentPresetResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                system_prompt=p.system_prompt,
                skill_ids=p.skill_ids,
                mcp_servers=p.mcp_servers,
                builtin_tools=p.builtin_tools,
                max_turns=p.max_turns,
                model_provider=p.model_provider,
                model_name=p.model_name,
                executor_name=p.executor_name,
                is_system=p.is_system,
                is_published=p.is_published,
                api_response_mode=p.api_response_mode,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in presets
        ],
        total=len(presets),
    )


@router.get("/{preset_id}", response_model=AgentPresetResponse)
async def get_agent_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent preset by ID.
    """
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == preset_id)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Agent preset not found")

    return AgentPresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        system_prompt=preset.system_prompt,
        skill_ids=preset.skill_ids,
        mcp_servers=preset.mcp_servers,
        builtin_tools=preset.builtin_tools,
        max_turns=preset.max_turns,
        model_provider=preset.model_provider,
        model_name=preset.model_name,
        executor_name=preset.executor_name,
        is_system=preset.is_system,
        is_published=preset.is_published,
        api_response_mode=preset.api_response_mode,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.get("/by-name/{name}", response_model=AgentPresetResponse)
async def get_agent_preset_by_name(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent preset by name.
    """
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.name == name)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Agent preset not found")

    return AgentPresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        system_prompt=preset.system_prompt,
        skill_ids=preset.skill_ids,
        mcp_servers=preset.mcp_servers,
        builtin_tools=preset.builtin_tools,
        max_turns=preset.max_turns,
        model_provider=preset.model_provider,
        model_name=preset.model_name,
        executor_name=preset.executor_name,
        is_system=preset.is_system,
        is_published=preset.is_published,
        api_response_mode=preset.api_response_mode,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.post("", response_model=AgentPresetResponse)
async def create_agent_preset(
    data: AgentPresetCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new agent preset.
    """
    # Check if name already exists
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.name == data.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Agent preset with this name already exists")

    preset = AgentPresetDB(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        skill_ids=data.skill_ids,
        mcp_servers=data.mcp_servers,
        builtin_tools=data.builtin_tools,
        max_turns=data.max_turns,
        model_provider=data.model_provider,
        model_name=data.model_name,
        executor_name=data.executor_name,
        is_system=False,  # User-created presets are never system presets
    )

    db.add(preset)
    await db.commit()
    await db.refresh(preset)

    return AgentPresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        system_prompt=preset.system_prompt,
        skill_ids=preset.skill_ids,
        mcp_servers=preset.mcp_servers,
        builtin_tools=preset.builtin_tools,
        max_turns=preset.max_turns,
        model_provider=preset.model_provider,
        model_name=preset.model_name,
        executor_name=preset.executor_name,
        is_system=preset.is_system,
        is_published=preset.is_published,
        api_response_mode=preset.api_response_mode,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.put("/{preset_id}", response_model=AgentPresetResponse)
async def update_agent_preset(
    preset_id: str,
    data: AgentPresetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an agent preset.

    System presets cannot be modified.
    """
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == preset_id)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Agent preset not found")

    # Check name uniqueness if changing name
    if data.name is not None and data.name != preset.name:
        result = await db.execute(
            select(AgentPresetDB).where(AgentPresetDB.name == data.name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Agent preset with this name already exists")
        preset.name = data.name

    # Update fields if provided (use model_fields_set to detect explicitly set fields)
    # This allows setting fields to null explicitly
    fields_set = data.model_fields_set

    if 'description' in fields_set:
        preset.description = data.description
    if 'system_prompt' in fields_set:
        preset.system_prompt = data.system_prompt
    if 'skill_ids' in fields_set:
        preset.skill_ids = data.skill_ids
    if 'mcp_servers' in fields_set:
        preset.mcp_servers = data.mcp_servers
    if 'builtin_tools' in fields_set:
        preset.builtin_tools = data.builtin_tools
    if 'max_turns' in fields_set:
        preset.max_turns = data.max_turns
    if 'model_provider' in fields_set:
        preset.model_provider = data.model_provider
    if 'model_name' in fields_set:
        preset.model_name = data.model_name
    if 'executor_name' in fields_set:
        preset.executor_name = data.executor_name
    if 'is_published' in fields_set:
        preset.is_published = data.is_published

    await db.commit()
    await db.refresh(preset)

    return AgentPresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        system_prompt=preset.system_prompt,
        skill_ids=preset.skill_ids,
        mcp_servers=preset.mcp_servers,
        builtin_tools=preset.builtin_tools,
        max_turns=preset.max_turns,
        model_provider=preset.model_provider,
        model_name=preset.model_name,
        executor_name=preset.executor_name,
        is_system=preset.is_system,
        is_published=preset.is_published,
        api_response_mode=preset.api_response_mode,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.post("/{preset_id}/publish", response_model=AgentPresetResponse)
async def publish_agent_preset(
    preset_id: str,
    request: PublishAgentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish an agent preset, making it publicly accessible.

    System presets cannot be published.
    Once published with a specific mode, the mode cannot be changed without unpublishing first.
    """
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == preset_id)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Agent preset not found")

    if preset.is_system:
        raise HTTPException(status_code=403, detail="Cannot publish system preset")

    if preset.is_published:
        raise HTTPException(
            status_code=400,
            detail="Agent is already published. Unpublish first to change the response mode."
        )

    # Validate executor is online before publishing
    if preset.executor_name:
        from app.api.v1.executors import _get_executor_status
        status = await _get_executor_status(preset.executor_name)
        if status != "online":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot publish: executor '{preset.executor_name}' is offline. Start the executor first."
            )

    preset.is_published = True
    preset.api_response_mode = request.api_response_mode
    await db.commit()
    await db.refresh(preset)

    return AgentPresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        system_prompt=preset.system_prompt,
        skill_ids=preset.skill_ids,
        mcp_servers=preset.mcp_servers,
        builtin_tools=preset.builtin_tools,
        max_turns=preset.max_turns,
        model_provider=preset.model_provider,
        model_name=preset.model_name,
        executor_name=preset.executor_name,
        is_system=preset.is_system,
        is_published=preset.is_published,
        api_response_mode=preset.api_response_mode,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.post("/{preset_id}/unpublish", response_model=AgentPresetResponse)
async def unpublish_agent_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Unpublish an agent preset, removing public access.
    This also resets the api_response_mode, allowing a different mode to be selected on re-publish.
    """
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == preset_id)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Agent preset not found")

    preset.is_published = False
    preset.api_response_mode = None
    await db.commit()
    await db.refresh(preset)

    return AgentPresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        system_prompt=preset.system_prompt,
        skill_ids=preset.skill_ids,
        mcp_servers=preset.mcp_servers,
        builtin_tools=preset.builtin_tools,
        max_turns=preset.max_turns,
        model_provider=preset.model_provider,
        model_name=preset.model_name,
        executor_name=preset.executor_name,
        is_system=preset.is_system,
        is_published=preset.is_published,
        api_response_mode=preset.api_response_mode,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.delete("/{preset_id}")
async def delete_agent_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an agent preset.

    System presets cannot be deleted.
    """
    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == preset_id)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Agent preset not found")

    if preset.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system preset")

    await db.delete(preset)
    await db.commit()

    return {"message": "Agent preset deleted successfully"}
