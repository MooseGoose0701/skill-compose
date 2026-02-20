"""Published Agent API - Public endpoints for published agent presets.

Provides public (no auth) endpoints for:
- Getting published agent info
- Streaming chat with published agents (server-side session management)
- Retrieving session history
"""
import asyncio
import json
import time
from typing import Dict, Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import SkillsAgent, EventStream, write_steering_message, poll_steering_messages, cleanup_steering_dir
from app.api.v1.agent import _finalize_trace
from app.api.v1.sessions import load_or_create_session, save_session_messages, save_session_checkpoint, save_session_checkpoint_sync, pre_compress_if_needed
from app.config import get_settings
from app.db.database import AsyncSessionLocal, get_db
from app.db.models import AgentPresetDB, AgentTraceDB, PublishedSessionDB, ExecutorDB

settings = get_settings()

router = APIRouter(prefix="/published", tags=["published"])

# Module-level registry of active streaming runs (trace_id → EventStream)
_active_streams: Dict[str, EventStream] = {}


class SteerRequest(BaseModel):
    """Request to inject a steering message into a running published agent."""
    message: str = Field(..., description="Steering message to inject", min_length=1)


class UploadedFile(BaseModel):
    file_id: str
    filename: str
    path: str
    content_type: str


class PublishedChatRequest(BaseModel):
    request: str
    session_id: Optional[str] = None  # None = create new session
    uploaded_files: Optional[List[UploadedFile]] = None


class PublishedAgentInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    api_response_mode: Optional[str] = None


class SessionMessages(BaseModel):
    session_id: str
    agent_id: str
    messages: List[dict]
    created_at: str
    updated_at: str


class PublishedChatResponse(BaseModel):
    """Non-streaming chat response."""
    success: bool
    answer: str
    total_turns: int
    steps: List[dict]
    error: Optional[str] = None
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    output_files: Optional[List[dict]] = None


class SessionListItem(BaseModel):
    id: str
    agent_id: str
    agent_name: Optional[str] = None
    message_count: int
    first_user_message: Optional[str] = None
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Session management endpoints (admin — no agent_id scoping)
# ---------------------------------------------------------------------------

@router.get("/sessions/list", response_model=SessionListResponse)
async def list_all_sessions(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all published agent sessions with pagination and optional agent filter."""
    # Base query
    base_filter = []
    if agent_id:
        base_filter.append(PublishedSessionDB.agent_id == agent_id)

    # Count
    count_q = select(func.count(PublishedSessionDB.id))
    if base_filter:
        count_q = count_q.where(*base_filter)
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch sessions with agent name via outerjoin
    q = (
        select(
            PublishedSessionDB,
            AgentPresetDB.name.label("agent_name"),
        )
        .outerjoin(AgentPresetDB, PublishedSessionDB.agent_id == AgentPresetDB.id)
    )
    if base_filter:
        q = q.where(*base_filter)
    q = q.order_by(desc(PublishedSessionDB.updated_at)).offset(offset).limit(limit)

    rows = (await db.execute(q)).all()

    items = []
    for row in rows:
        session = row[0]
        agent_name = row[1]
        messages = session.messages or []
        message_count = len(messages)

        # Extract first user message
        first_user_msg = None
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    first_user_msg = content[:100]
                elif isinstance(content, list):
                    # Extract text from content blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            first_user_msg = block.get("text", "")[:100]
                            break
                break

        items.append(SessionListItem(
            id=session.id,
            agent_id=session.agent_id,
            agent_name=agent_name,
            message_count=message_count,
            first_user_message=first_user_msg,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
        ))

    return SessionListResponse(
        sessions=items,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/sessions/{session_id}/detail", response_model=SessionMessages)
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single session's full messages (admin endpoint, no agent_id required)."""
    result = await db.execute(
        select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
    )
    session_record = result.scalar_one_or_none()
    if not session_record:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionMessages(
        session_id=session_record.id,
        agent_id=session_record.agent_id,
        messages=session_record.messages or [],
        created_at=session_record.created_at.isoformat(),
        updated_at=session_record.updated_at.isoformat(),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a single session."""
    result = await db.execute(
        select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
    )
    session_record = result.scalar_one_or_none()
    if not session_record:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.execute(
        delete(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
    )
    await db.commit()
    return {"message": "Session deleted"}


@router.delete("/{agent_id}/sessions")
async def delete_agent_sessions(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete all sessions for a specific agent."""
    result = await db.execute(
        select(func.count(PublishedSessionDB.id)).where(
            PublishedSessionDB.agent_id == agent_id
        )
    )
    count = result.scalar() or 0

    await db.execute(
        delete(PublishedSessionDB).where(
            PublishedSessionDB.agent_id == agent_id
        )
    )
    await db.commit()
    return {"message": f"Deleted {count} sessions", "deleted_count": count}


@router.get("/{agent_id}", response_model=PublishedAgentInfo)
async def get_published_agent(agent_id: str):
    """Get public info for a published agent."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentPresetDB).where(
                AgentPresetDB.id == agent_id,
                AgentPresetDB.is_published == True,
            )
        )
        preset = result.scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Published agent not found")

        return PublishedAgentInfo(
            id=preset.id,
            name=preset.name,
            description=preset.description,
            api_response_mode=preset.api_response_mode,
        )


@router.get("/{agent_id}/sessions/{session_id}", response_model=SessionMessages)
async def get_session(agent_id: str, session_id: str):
    """Get session messages for a published agent session."""
    async with AsyncSessionLocal() as db:
        # Verify agent is published
        result = await db.execute(
            select(AgentPresetDB).where(
                AgentPresetDB.id == agent_id,
                AgentPresetDB.is_published == True,
            )
        )
        preset = result.scalar_one_or_none()
        if not preset:
            raise HTTPException(status_code=404, detail="Published agent not found")

        # Load session
        result = await db.execute(
            select(PublishedSessionDB).where(
                PublishedSessionDB.id == session_id,
                PublishedSessionDB.agent_id == agent_id,
            )
        )
        session_record = result.scalar_one_or_none()
        if not session_record:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionMessages(
            session_id=session_record.id,
            agent_id=session_record.agent_id,
            messages=session_record.messages or [],
            created_at=session_record.created_at.isoformat(),
            updated_at=session_record.updated_at.isoformat(),
        )


@router.post("/{agent_id}/chat/{trace_id}/steer")
async def steer_published_agent(
    agent_id: str, trace_id: str, body: SteerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Inject a steering message into a running published agent stream.

    Hybrid approach for multi-worker support:
    1. Fast path: same worker direct inject
    2. Cross-worker: DB check + filesystem queue
    """
    # Fast path: same worker
    event_stream = _active_streams.get(trace_id)
    if event_stream:
        if event_stream.closed:
            raise HTTPException(status_code=409, detail="Agent has already completed")
        await event_stream.inject(body.message)
        return {"status": "injected", "trace_id": trace_id}

    # Cross-worker path
    result = await db.execute(
        select(AgentTraceDB).where(AgentTraceDB.id == trace_id)
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="No active run found for this trace_id")
    if trace.status != "running":
        raise HTTPException(status_code=409, detail="Agent has already completed")

    write_steering_message(trace_id, body.message)
    return {"status": "injected", "trace_id": trace_id}


async def _resolve_published_config(preset):
    """Resolve config from a published preset, including executor name."""
    executor_name = None
    if preset.executor_id:
        async with AsyncSessionLocal() as db:
            executor_result = await db.execute(
                select(ExecutorDB).where(ExecutorDB.id == preset.executor_id)
            )
            executor = executor_result.scalar_one_or_none()
            if executor:
                executor_name = executor.name

    return {
        "skills": preset.skill_ids,
        "allowed_tools": preset.builtin_tools,
        "max_turns": preset.max_turns,
        "equipped_mcp_servers": preset.mcp_servers,
        "system_prompt": preset.system_prompt,
        "model_provider": preset.model_provider,
        "model_name": preset.model_name,
        "executor_name": executor_name,
    }


@router.post("/{agent_id}/chat")
async def published_chat(agent_id: str, request: PublishedChatRequest):
    """SSE streaming chat with a published agent."""
    # Validate agent exists and is published
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentPresetDB).where(
                AgentPresetDB.id == agent_id,
                AgentPresetDB.is_published == True,
            )
        )
        preset = result.scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Published agent not found")

        if preset.api_response_mode == "non_streaming":
            raise HTTPException(
                status_code=400,
                detail="This agent is configured for non-streaming mode. Use /chat/sync endpoint."
            )

        config = await _resolve_published_config(preset)

    # Validate API key before proceeding
    from app.api.v1.agent import _validate_api_key
    _validate_api_key(config)

    # Session management — published agents may omit session_id for auto-creation
    if request.session_id:
        session_data = await load_or_create_session(request.session_id, agent_id)
    else:
        # Auto-generate a session for published agents
        from app.db.models import generate_uuid
        auto_sid = generate_uuid()
        session_data = await load_or_create_session(auto_sid, agent_id)

    session_id = session_data.session_id
    history = session_data.agent_context  # Use agent_context for the agent
    history_len = len(history) if history else 0

    # Pre-compress if context exceeds threshold
    pre_provider = config.get("model_provider") or settings.default_model_provider
    pre_model = config.get("model_name") or settings.default_model_name
    if history:
        history = await pre_compress_if_needed(history, pre_provider, pre_model)

    # Build actual request with file info and image blocks
    from app.api.v1.agent import _build_request_with_files
    actual_request, image_contents = _build_request_with_files(
        request.request,
        request.uploaded_files,
        model_provider=config.get("model_provider"),
        model_name=config.get("model_name"),
    )

    async def event_generator():
        start_time = time.time()

        # Create trace record
        trace_id = None
        async with AsyncSessionLocal() as trace_db:
            actual_model = config.get("model_name") or settings.default_model_name
            actual_provider = config.get("model_provider") or settings.default_model_provider
            trace = AgentTraceDB(
                request=request.request,
                skills_used=[],
                model=actual_model,
                model_provider=actual_provider,
                status="running",
                success=False,
                answer="",
                error=None,
                total_turns=0,
                total_input_tokens=0,
                total_output_tokens=0,
                steps=[],
                llm_calls=[],
                duration_ms=0,
                executor_name=config.get("executor_name"),
            )
            trace_db.add(trace)
            await trace_db.commit()
            trace_id = trace.id

        yield f"data: {json.dumps({'event_type': 'run_started', 'turn': 0, 'trace_id': trace_id, 'session_id': session_id})}\n\n"

        # Create agent, event stream, and cancellation event
        agent = SkillsAgent(
            model=config.get("model_name"),
            model_provider=config.get("model_provider"),
            max_turns=config["max_turns"],
            verbose=False,
            allowed_skills=config["skills"],
            allowed_tools=config["allowed_tools"],
            equipped_mcp_servers=config["equipped_mcp_servers"],
            custom_system_prompt=config["system_prompt"],
            executor_name=config.get("executor_name"),
            workspace_id=session_id,
        )

        event_stream = EventStream()
        cancel_event = asyncio.Event()

        # Register stream for steering (same-worker fast path + cross-worker polling)
        if trace_id:
            _active_streams[trace_id] = event_stream
        steering_task = asyncio.create_task(
            poll_steering_messages(trace_id, event_stream)
        ) if trace_id else None

        agent_task = asyncio.create_task(
            agent.run(
                actual_request,
                conversation_history=history,
                image_contents=image_contents,
                event_stream=event_stream,
                cancellation_event=cancel_event,
            )
        )

        last_complete_event = None
        last_messages_snapshot = None  # Incremental checkpoint for resilient save
        last_snapshot_for_display = None  # Last snapshot before compression (for display extraction)
        compression_happened = False  # Track if context_compressed event was seen
        collected_steps = []
        current_text_buffer = ""
        was_cancelled = False

        try:
            async for event in event_stream:
                # Heartbeat — SSE comment to keep connection alive through proxies
                if event.event_type == "heartbeat":
                    yield ": heartbeat\n\n"
                    continue

                # Intercept turn_complete for incremental checkpoint (not forwarded to client)
                if event.event_type == "turn_complete":
                    snapshot = event.data.get("messages_snapshot")
                    last_messages_snapshot = snapshot
                    # Track pre-compression snapshot for display extraction
                    if not compression_happened and snapshot:
                        last_snapshot_for_display = snapshot
                    # Save checkpoint: only updates agent_context, not display messages
                    if session_id and snapshot:
                        try:
                            await save_session_checkpoint(session_id, snapshot)
                        except Exception:
                            pass  # fire-and-forget
                    continue

                # Intercept context_compressed to set flag (still forward to client)
                if event.event_type == "context_compressed":
                    compression_happened = True

                event_data = {
                    "event_type": event.event_type,
                    "turn": event.turn,
                    **event.data
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                event_type = event.event_type
                if event_type == "text_delta":
                    current_text_buffer += event.data.get("text", "")
                elif event_type == "assistant" and event.data.get("content"):
                    collected_steps.append({
                        "role": "assistant",
                        "content": event.data.get("content", "")[:2000],
                        "tool_name": None,
                        "tool_input": None,
                    })
                elif event_type in ("tool_call", "tool_result", "turn_start", "complete"):
                    if current_text_buffer:
                        collected_steps.append({
                            "role": "assistant",
                            "content": current_text_buffer[:2000],
                            "tool_name": None,
                            "tool_input": None,
                        })
                        current_text_buffer = ""
                    if event_type == "tool_result":
                        collected_steps.append({
                            "role": "tool",
                            "content": event.data.get("tool_result", "")[:5000],
                            "tool_name": event.data.get("tool_name"),
                            "tool_input": event.data.get("tool_input"),
                        })
                    elif event_type == "complete":
                        last_complete_event = event.data

            await agent_task

        except (asyncio.CancelledError, GeneratorExit):
            was_cancelled = True
            cancel_event.set()
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass

        finally:
            # Stop steering poll and clean up
            if steering_task:
                steering_task.cancel()
                try:
                    await steering_task
                except asyncio.CancelledError:
                    pass
            if trace_id:
                cleanup_steering_dir(trace_id)
                _active_streams.pop(trace_id, None)

            agent.cleanup()

            duration_ms = int((time.time() - start_time) * 1000)

            if was_cancelled:
                final_status = "cancelled"
                is_success = False
                error_msg = "Request was cancelled by user"
            elif last_complete_event:
                is_success = last_complete_event.get("success", False)
                final_status = "completed" if is_success else "failed"
                error_msg = last_complete_event.get("error")
            else:
                final_status = "failed"
                is_success = False
                error_msg = "Agent did not complete"

            final_answer = last_complete_event.get("answer", "") if last_complete_event else ""

            await _finalize_trace(trace_id, {
                "status": final_status,
                "success": is_success,
                "answer": final_answer,
                "error": error_msg,
                "total_turns": last_complete_event.get("total_turns", 0) if last_complete_event else 0,
                "total_input_tokens": last_complete_event.get("total_input_tokens", 0) if last_complete_event else 0,
                "total_output_tokens": last_complete_event.get("total_output_tokens", 0) if last_complete_event else 0,
                "skills_used": last_complete_event.get("skills_used", []) if last_complete_event else [],
                "steps": collected_steps,
                "duration_ms": duration_ms,
            })

            # Save full conversation messages to session (dual-store)
            if session_id:
                if not was_cancelled and last_complete_event:
                    # Normal completion — definitive save
                    final_msgs = last_complete_event.get("final_messages")

                    # Compute new display messages (only the new turns from this request)
                    new_display = None
                    if last_snapshot_for_display and history_len is not None:
                        # Use pre-compression snapshot for accurate display extraction
                        new_display = last_snapshot_for_display[history_len:]
                    elif final_msgs and not compression_happened and history_len is not None:
                        new_display = final_msgs[history_len:]
                    # else: fallback to simple user+assistant pair (handled by save_session_messages)

                    await save_session_messages(
                        session_id,
                        final_answer,
                        request.request,
                        final_messages=final_msgs,
                        display_append_messages=new_display if new_display else None,
                    )
                elif last_messages_snapshot:
                    # Cancelled or interrupted — save last checkpoint (agent_context only)
                    # Use sync DB to avoid orphaned async connections in cancelled context
                    try:
                        save_session_checkpoint_sync(session_id, last_messages_snapshot)
                    except Exception:
                        pass

        if not was_cancelled:
            yield f"data: {json.dumps({'event_type': 'trace_saved', 'turn': 0, 'trace_id': trace_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/{agent_id}/chat/sync", response_model=PublishedChatResponse)
async def published_chat_sync(agent_id: str, request: PublishedChatRequest):
    """Non-streaming chat with a published agent. Returns complete response as JSON."""
    # Validate agent exists and is published
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentPresetDB).where(
                AgentPresetDB.id == agent_id,
                AgentPresetDB.is_published == True,
            )
        )
        preset = result.scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Published agent not found")

        if preset.api_response_mode == "streaming":
            raise HTTPException(
                status_code=400,
                detail="This agent is configured for streaming mode. Use /chat endpoint."
            )

        config = await _resolve_published_config(preset)

    # Validate API key before proceeding
    from app.api.v1.agent import _validate_api_key
    _validate_api_key(config)

    # Session management — published agents may omit session_id for auto-creation
    if request.session_id:
        session_data = await load_or_create_session(request.session_id, agent_id)
    else:
        from app.db.models import generate_uuid
        auto_sid = generate_uuid()
        session_data = await load_or_create_session(auto_sid, agent_id)

    session_id = session_data.session_id
    history = session_data.agent_context  # Use agent_context for the agent
    history_len = len(history) if history else 0

    # Pre-compress if context exceeds threshold
    sync_provider = config.get("model_provider") or settings.default_model_provider
    sync_model = config.get("model_name") or settings.default_model_name
    if history:
        history = await pre_compress_if_needed(history, sync_provider, sync_model)

    # Build actual request with file info and image blocks
    from app.api.v1.agent import _build_request_with_files
    actual_request, image_contents = _build_request_with_files(
        request.request,
        request.uploaded_files,
        model_provider=config.get("model_provider"),
        model_name=config.get("model_name"),
    )

    start_time = time.time()

    # Create trace record
    trace_id = None
    async with AsyncSessionLocal() as trace_db:
        actual_model = config.get("model_name") or settings.default_model_name
        actual_provider = config.get("model_provider") or settings.default_model_provider
        trace = AgentTraceDB(
            request=request.request,
            skills_used=[],
            model=actual_model,
            model_provider=actual_provider,
            status="running",
            success=False,
            answer="",
            error=None,
            total_turns=0,
            total_input_tokens=0,
            total_output_tokens=0,
            steps=[],
            llm_calls=[],
            duration_ms=0,
            executor_name=config.get("executor_name"),
        )
        trace_db.add(trace)
        await trace_db.commit()
        trace_id = trace.id

    # Run agent (async, non-streaming — no event_stream)
    agent = SkillsAgent(
        model=config.get("model_name"),
        model_provider=config.get("model_provider"),
        max_turns=config["max_turns"],
        verbose=False,
        allowed_skills=config["skills"],
        allowed_tools=config["allowed_tools"],
        equipped_mcp_servers=config["equipped_mcp_servers"],
        custom_system_prompt=config["system_prompt"],
        executor_name=config.get("executor_name"),
        workspace_id=session_id,
    )

    try:
        agent_result = await agent.run(actual_request, conversation_history=history, image_contents=image_contents)
    except Exception as e:
        agent_result = None
        error_str = str(e)
    finally:
        agent.cleanup()

    duration_ms = int((time.time() - start_time) * 1000)

    if agent_result:
        result_data = {
            "success": agent_result.success,
            "answer": agent_result.answer,
            "error": agent_result.error,
            "total_turns": agent_result.total_turns,
            "total_input_tokens": agent_result.total_input_tokens,
            "total_output_tokens": agent_result.total_output_tokens,
            "skills_used": agent_result.skills_used,
            "output_files": agent_result.output_files or None,
            "final_messages": agent_result.final_messages,
            "steps": [
                {
                    "role": step.role,
                    "content": step.content[:5000] if step.content else "",
                    "tool_name": step.tool_name,
                    "tool_input": step.tool_input,
                }
                for step in (agent_result.steps or [])
            ],
        }
    else:
        result_data = {"success": False, "answer": "", "error": error_str, "steps": [], "total_turns": 0}

    # Update trace
    async with AsyncSessionLocal() as trace_db:
        final_status = "completed" if result_data.get("success") else "failed"
        await trace_db.execute(
            update(AgentTraceDB)
            .where(AgentTraceDB.id == trace_id)
            .values(
                status=final_status,
                success=result_data.get("success", False),
                answer=result_data.get("answer", ""),
                error=result_data.get("error"),
                total_turns=result_data.get("total_turns", 0),
                total_input_tokens=result_data.get("total_input_tokens", 0),
                total_output_tokens=result_data.get("total_output_tokens", 0),
                skills_used=result_data.get("skills_used", []),
                steps=result_data.get("steps", []),
                duration_ms=duration_ms,
            )
        )
        await trace_db.commit()

    # Save full conversation messages to session (dual-store)
    if session_id and result_data.get("success"):
        final_msgs = result_data.get("final_messages")
        # Compute new display messages (only the new turns from this request)
        new_display = None
        if final_msgs and history_len is not None:
            new_display = final_msgs[history_len:]

        await save_session_messages(
            session_id,
            result_data.get("answer", ""),
            request.request,
            final_messages=final_msgs,
            display_append_messages=new_display if new_display else None,
        )

    return PublishedChatResponse(
        success=result_data.get("success", False),
        answer=result_data.get("answer", ""),
        total_turns=result_data.get("total_turns", 0),
        steps=result_data.get("steps", []),
        error=result_data.get("error"),
        trace_id=trace_id,
        session_id=session_id,
        output_files=result_data.get("output_files"),
    )
