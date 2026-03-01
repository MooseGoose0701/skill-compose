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

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ChannelBindingDB, ChannelMessageDB, AgentPresetDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

def _validate_regex(pattern: Optional[str]) -> Optional[str]:
    """Validate a regex pattern is compilable.

    NOTE: This only checks syntax, not complexity. Pathological patterns like
    ``(a+)+$`` will pass validation but could cause catastrophic backtracking.
    Full ReDoS mitigation would require a complexity checker or execution timeout,
    which is not available in Python's ``re`` module. The max_length=512 constraint
    on the field and the try/except at execution time provide partial mitigation.
    """
    if pattern is None:
        return None
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")
    return pattern


class ChannelBindingCreate(BaseModel):
    """Request model for creating a channel binding."""
    channel_type: str = Field(..., description="Channel type: feishu / telegram / webhook")
    external_id: str = Field(..., min_length=1, max_length=256, description="Platform-side group/chat ID")
    name: str = Field(..., min_length=1, max_length=128)
    agent_id: str = Field(..., description="Agent preset ID to bind")
    trigger_pattern: Optional[str] = Field(None, max_length=512, description="Regex pattern to trigger the agent")
    config: Optional[Dict[str, Any]] = Field(None, description="Adapter-specific configuration")

    @field_validator("trigger_pattern")
    @classmethod
    def validate_trigger_pattern(cls, v: Optional[str]) -> Optional[str]:
        return _validate_regex(v)


class ChannelBindingUpdate(BaseModel):
    """Request model for updating a channel binding."""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    agent_id: Optional[str] = Field(None, description="Agent preset ID to bind")
    trigger_pattern: Optional[str] = Field(None, max_length=512)
    config: Optional[Dict[str, Any]] = None

    @field_validator("trigger_pattern")
    @classmethod
    def validate_trigger_pattern(cls, v: Optional[str]) -> Optional[str]:
        return _validate_regex(v)


class ChannelBindingResponse(BaseModel):
    """Response model for a channel binding."""
    id: str
    channel_type: str
    external_id: str
    name: str
    agent_id: str
    agent_name: Optional[str] = None
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
# Helpers
# ---------------------------------------------------------------------------

def _mask_config(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Mask sensitive fields in the config dict.

    Currently masks ``app_secret`` showing only last 4 chars.
    """
    if not config:
        return config
    masked = dict(config)
    if "app_secret" in masked and masked["app_secret"]:
        secret = str(masked["app_secret"])
        if len(secret) > 4:
            masked["app_secret"] = "****" + secret[-4:]
        else:
            masked["app_secret"] = "****"
    return masked


def _build_binding_response(
    binding: ChannelBindingDB,
    agent_name: Optional[str] = None,
) -> ChannelBindingResponse:
    return ChannelBindingResponse(
        id=binding.id,
        channel_type=binding.channel_type,
        external_id=binding.external_id,
        name=binding.name,
        agent_id=binding.agent_id,
        agent_name=agent_name,
        trigger_pattern=binding.trigger_pattern,
        enabled=binding.enabled,
        config=_mask_config(binding.config),
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


async def _get_agent_name(db: AsyncSession, agent_id: str) -> Optional[str]:
    """Look up agent preset name by ID."""
    result = await db.execute(
        select(AgentPresetDB.name).where(AgentPresetDB.id == agent_id)
    )
    return result.scalar_one_or_none()


def _merge_config(existing: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Merge incoming config into existing, preserving masked secrets."""
    if incoming is None:
        return existing
    if not existing:
        # Strip masked secrets from brand-new config
        result = dict(incoming)
        if "app_secret" in result and isinstance(result["app_secret"], str) and result["app_secret"].startswith("****"):
            del result["app_secret"]
        return result or None

    merged = dict(existing)
    for key, value in incoming.items():
        # Skip masked secret values — preserve existing
        if key == "app_secret" and isinstance(value, str) and value.startswith("****"):
            continue
        merged[key] = value
    return merged


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

    # Batch-fetch agent names
    agent_ids = list({b.agent_id for b in bindings})
    agent_names: dict[str, str] = {}
    if agent_ids:
        agents_result = await db.execute(
            select(AgentPresetDB.id, AgentPresetDB.name).where(
                AgentPresetDB.id.in_(agent_ids)
            )
        )
        for row in agents_result:
            agent_names[row[0]] = row[1]

    return ChannelBindingListResponse(
        bindings=[_build_binding_response(b, agent_names.get(b.agent_id)) for b in bindings],
        total=len(bindings),
    )


@router.get("/adapters")
async def get_adapter_status(
    db: AsyncSession = Depends(get_db),
):
    """
    Get connection status of all channel adapters.

    With multiple uvicorn workers, only the leader worker holds live adapters.
    If this request hits a non-leader worker, adapter status is derived from
    DB bindings (connected status assumed ``True``).
    """
    try:
        from app.services.channel_manager import ChannelManager, adapter_key_for_binding
        manager = ChannelManager()

        # Leader worker: return real status
        if manager._is_leader:
            return {name: adapter.is_connected() for name, adapter in manager._adapters.items()}

        # Non-leader worker: derive expected adapters from enabled bindings
        result = await db.execute(
            select(ChannelBindingDB).where(ChannelBindingDB.enabled == True)
        )
        bindings = result.scalars().all()
        adapters: dict[str, bool] = {}
        for b in bindings:
            key = adapter_key_for_binding(b)
            if key and key not in adapters:
                adapters[key] = True
        return adapters
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

    Only works when the request hits the leader worker that holds live
    adapter connections. Non-leader workers cannot restart adapters.
    """
    try:
        from app.services.channel_manager import ChannelManager
        manager = ChannelManager()

        if adapter_type not in manager._adapters:
            # Could be a non-leader worker — don't 404
            if not manager._is_leader:
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": f"Restart request for '{adapter_type}' received. The adapter is managed by the service leader worker.",
                    },
                )
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

    agent_name = await _get_agent_name(db, binding.agent_id)
    return _build_binding_response(binding, agent_name)


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
    agent = agent_result.scalar_one_or_none()
    if not agent:
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

    # 4. Hot-reload: start adapter if needed
    try:
        from app.services.channel_manager import ChannelManager
        manager = ChannelManager()
        await manager.on_binding_created(binding.id)
    except Exception as e:
        logger.warning(f"Hot-reload on_binding_created failed: {e}")

    return _build_binding_response(binding, agent.name)


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

    # Save old config for hot-reload comparison
    old_config = dict(binding.config) if binding.config else None

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
        # Merge config instead of replacing — preserves masked secrets
        binding.config = _merge_config(binding.config, data.config)

    await db.commit()
    await db.refresh(binding)

    # Hot-reload: adjust adapters if config changed
    try:
        from app.services.channel_manager import ChannelManager
        manager = ChannelManager()
        await manager.on_binding_updated(binding.id, old_config)
    except Exception as e:
        logger.warning(f"Hot-reload on_binding_updated failed: {e}")

    agent_name = await _get_agent_name(db, binding.agent_id)
    return _build_binding_response(binding, agent_name)


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

    # Save config before deletion for hot-reload
    binding_config = dict(binding.config) if binding.config else None

    await db.delete(binding)
    await db.commit()

    # Hot-reload: stop adapter if no remaining bindings use this app_id
    try:
        from app.services.channel_manager import ChannelManager
        manager = ChannelManager()
        await manager.on_binding_deleted(binding_id, binding_config)
    except Exception as e:
        logger.warning(f"Hot-reload on_binding_deleted failed: {e}")

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

    agent_name = await _get_agent_name(db, binding.agent_id)
    return _build_binding_response(binding, agent_name)


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
