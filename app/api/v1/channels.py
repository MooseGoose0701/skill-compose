"""
Channel Bindings API endpoints.

Provides endpoints for:
- Listing channel bindings
- Getting binding details
- Creating new bindings
- Updating bindings
- Deleting bindings
- Toggling enabled/disabled
- Viewing message history
- Adapter connection status
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ChannelBindingDB, ChannelMessageDB, AgentPresetDB


router = APIRouter(prefix="/channels", tags=["channels"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChannelBindingCreate(BaseModel):
    """Request model for creating a channel binding."""
    channel_type: str = Field(..., description="Channel type: feishu / telegram / webhook")
    external_id: str = Field(..., min_length=1, max_length=256, description="Platform-side group/chat ID")
    name: str = Field(..., min_length=1, max_length=128)
    agent_id: str = Field(..., description="Agent preset ID to bind")
    trigger_pattern: Optional[str] = Field(None, max_length=512, description="Regex pattern to trigger the agent")
    config: Optional[Dict[str, Any]] = Field(None, description="Adapter-specific configuration")


class ChannelBindingUpdate(BaseModel):
    """Request model for updating a channel binding."""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    agent_id: Optional[str] = Field(None, description="Agent preset ID to bind")
    trigger_pattern: Optional[str] = Field(None, max_length=512)
    config: Optional[Dict[str, Any]] = None


class ChannelBindingResponse(BaseModel):
    """Response model for a channel binding."""
    id: str
    channel_type: str
    external_id: str
    name: str
    agent_id: str
    trigger_pattern: Optional[str] = None
    enabled: bool
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class ChannelBindingListResponse(BaseModel):
    """Response for listing channel bindings."""
    bindings: List[ChannelBindingResponse]
    total: int


class ChannelMessageResponse(BaseModel):
    """Response model for a channel message."""
    id: str
    channel_binding_id: str
    direction: str
    external_message_id: Optional[str] = None
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    content: str
    message_type: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ChannelMessageListResponse(BaseModel):
    """Response for listing channel messages."""
    messages: List[ChannelMessageResponse]
    total: int


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_binding_response(binding: ChannelBindingDB) -> ChannelBindingResponse:
    return ChannelBindingResponse(
        id=binding.id,
        channel_type=binding.channel_type,
        external_id=binding.external_id,
        name=binding.name,
        agent_id=binding.agent_id,
        trigger_pattern=binding.trigger_pattern,
        enabled=binding.enabled,
        config=binding.config,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def _build_message_response(msg: ChannelMessageDB) -> ChannelMessageResponse:
    return ChannelMessageResponse(
        id=msg.id,
        channel_binding_id=msg.channel_binding_id,
        direction=msg.direction,
        external_message_id=msg.external_message_id,
        sender_id=msg.sender_id,
        sender_name=msg.sender_name,
        content=msg.content,
        message_type=msg.message_type,
        metadata=msg.msg_metadata,
        created_at=msg.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=ChannelBindingListResponse)
async def list_channel_bindings(
    channel_type: Optional[str] = Query(None, description="Filter by channel type"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all channel bindings.

    Optionally filter by channel_type.  Results are ordered by created_at descending.
    """
    query = select(ChannelBindingDB)

    if channel_type is not None:
        query = query.where(ChannelBindingDB.channel_type == channel_type)

    query = query.order_by(desc(ChannelBindingDB.created_at))

    result = await db.execute(query)
    bindings = result.scalars().all()

    return ChannelBindingListResponse(
        bindings=[_build_binding_response(b) for b in bindings],
        total=len(bindings),
    )


@router.get("/adapters")
async def get_adapter_status():
    """
    Get connection status of all channel adapters.

    Returns a mapping of adapter name to its connected status.
    """
    try:
        from app.services.channel_manager import ChannelManager
        manager = ChannelManager()
        return {name: adapter.is_connected() for name, adapter in manager._adapters.items()}
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Channel manager not available",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get adapter status: {str(e)}",
        )


@router.post("/adapters/{adapter_type}/restart")
async def restart_adapter(adapter_type: str):
    """
    Restart a specific channel adapter.
    """
    try:
        from app.services.channel_manager import ChannelManager
        manager = ChannelManager()

        if adapter_type not in manager._adapters:
            raise HTTPException(
                status_code=404,
                detail=f"Adapter '{adapter_type}' not found",
            )

        success = await manager.restart_adapter(adapter_type)
        adapter = manager._adapters.get(adapter_type)

        return {
            "message": f"Adapter '{adapter_type}' restarted successfully" if success else f"Failed to restart '{adapter_type}'",
            "connected": adapter.is_connected() if adapter else False,
        }
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Channel manager not available",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart adapter: {str(e)}",
        )


@router.get("/{binding_id}", response_model=ChannelBindingResponse)
async def get_channel_binding(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a channel binding by ID.
    """
    result = await db.execute(
        select(ChannelBindingDB).where(ChannelBindingDB.id == binding_id)
    )
    binding = result.scalar_one_or_none()

    if not binding:
        raise HTTPException(status_code=404, detail="Channel binding not found")

    return _build_binding_response(binding)


@router.post("", response_model=ChannelBindingResponse)
async def create_channel_binding(
    data: ChannelBindingCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new channel binding.

    Validates that the referenced agent_id exists and that the
    (channel_type, external_id) pair is unique.
    """
    # 1. Validate agent_id exists
    agent_result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == data.agent_id)
    )
    if not agent_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent preset not found for the given agent_id")

    # 2. Check unique constraint (channel_type + external_id)
    existing_result = await db.execute(
        select(ChannelBindingDB).where(
            and_(
                ChannelBindingDB.channel_type == data.channel_type,
                ChannelBindingDB.external_id == data.external_id,
            )
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A binding for channel_type='{data.channel_type}' and external_id='{data.external_id}' already exists",
        )

    # 3. Create record
    binding = ChannelBindingDB(
        channel_type=data.channel_type,
        external_id=data.external_id,
        name=data.name,
        agent_id=data.agent_id,
        trigger_pattern=data.trigger_pattern,
        config=data.config,
        enabled=True,
    )

    db.add(binding)
    await db.commit()
    await db.refresh(binding)

    return _build_binding_response(binding)


@router.put("/{binding_id}", response_model=ChannelBindingResponse)
async def update_channel_binding(
    binding_id: str,
    data: ChannelBindingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a channel binding.
    """
    result = await db.execute(
        select(ChannelBindingDB).where(ChannelBindingDB.id == binding_id)
    )
    binding = result.scalar_one_or_none()

    if not binding:
        raise HTTPException(status_code=404, detail="Channel binding not found")

    fields_set = data.model_fields_set

    if "name" in fields_set and data.name is not None:
        binding.name = data.name

    if "agent_id" in fields_set and data.agent_id is not None:
        # Validate new agent_id exists
        agent_result = await db.execute(
            select(AgentPresetDB).where(AgentPresetDB.id == data.agent_id)
        )
        if not agent_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Agent preset not found for the given agent_id")
        binding.agent_id = data.agent_id

    if "trigger_pattern" in fields_set:
        binding.trigger_pattern = data.trigger_pattern

    if "config" in fields_set:
        binding.config = data.config

    await db.commit()
    await db.refresh(binding)

    return _build_binding_response(binding)


@router.delete("/{binding_id}")
async def delete_channel_binding(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a channel binding and its associated messages (CASCADE).
    """
    result = await db.execute(
        select(ChannelBindingDB).where(ChannelBindingDB.id == binding_id)
    )
    binding = result.scalar_one_or_none()

    if not binding:
        raise HTTPException(status_code=404, detail="Channel binding not found")

    await db.delete(binding)
    await db.commit()

    return {"message": "Channel binding deleted successfully"}


@router.post("/{binding_id}/toggle", response_model=ChannelBindingResponse)
async def toggle_channel_binding(
    binding_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Toggle the enabled/disabled state of a channel binding.
    """
    result = await db.execute(
        select(ChannelBindingDB).where(ChannelBindingDB.id == binding_id)
    )
    binding = result.scalar_one_or_none()

    if not binding:
        raise HTTPException(status_code=404, detail="Channel binding not found")

    binding.enabled = not binding.enabled
    await db.commit()
    await db.refresh(binding)

    return _build_binding_response(binding)


@router.get("/{binding_id}/messages", response_model=ChannelMessageListResponse)
async def list_channel_messages(
    binding_id: str,
    limit: int = Query(50, ge=1, le=500, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get message history for a channel binding.

    Messages are ordered by created_at descending (newest first).
    Supports pagination via limit and offset.
    """
    # Verify binding exists
    binding_result = await db.execute(
        select(ChannelBindingDB).where(ChannelBindingDB.id == binding_id)
    )
    if not binding_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Channel binding not found")

    # Count total messages
    count_query = select(func.count()).select_from(ChannelMessageDB).where(
        ChannelMessageDB.channel_binding_id == binding_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch paginated messages
    messages_query = (
        select(ChannelMessageDB)
        .where(ChannelMessageDB.channel_binding_id == binding_id)
        .order_by(desc(ChannelMessageDB.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(messages_query)
    messages = result.scalars().all()

    return ChannelMessageListResponse(
        messages=[_build_message_response(m) for m in messages],
        total=total,
    )
