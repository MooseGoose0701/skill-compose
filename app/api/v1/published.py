"""Published Agent API - Public endpoints for published agent presets.

Provides public (no auth) endpoints for:
- Getting published agent info
- Streaming chat with published agents (server-side session management)
- Retrieving session history
"""
import asyncio
import json
import time
from typing import Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import SkillsAgent
from app.api.v1.agent import _finalize_trace
from app.api.v1.sessions import load_or_create_session, save_session_messages
from app.config import get_settings
from app.db.database import AsyncSessionLocal, get_db
from app.db.models import AgentPresetDB, AgentTraceDB, PublishedSessionDB, ExecutorDB

settings = get_settings()

_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter(prefix="/published", tags=["published"])


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

        # Validate response mode
        if preset.api_response_mode == "non_streaming":
            raise HTTPException(
                status_code=400,
                detail="This agent is configured for non-streaming mode. Use /chat/sync endpoint."
            )

        # Resolve executor name if executor_id is set
        executor_name = None
        if preset.executor_id:
            executor_result = await db.execute(
                select(ExecutorDB).where(ExecutorDB.id == preset.executor_id)
            )
            executor = executor_result.scalar_one_or_none()
            if executor:
                executor_name = executor.name

        # Capture preset config
        config = {
            "skills": preset.skill_ids,
            "allowed_tools": preset.builtin_tools,
            "max_turns": preset.max_turns,
            "equipped_mcp_servers": preset.mcp_servers,
            "system_prompt": preset.system_prompt,
            "model_provider": preset.model_provider,
            "model_name": preset.model_name,
            "executor_name": executor_name,
        }

    # Session management — published agents may omit session_id for auto-creation
    if request.session_id:
        session_id, history = await load_or_create_session(request.session_id, agent_id)
    else:
        from app.db.models import generate_uuid
        auto_sid = generate_uuid()
        session_id, history = await load_or_create_session(auto_sid, agent_id)

    # Build actual request with file info and image blocks
    from app.api.v1.agent import _build_request_with_files
    actual_request, image_contents = _build_request_with_files(
        request.request,
        request.uploaded_files,
        model_provider=config.get("model_provider"),
        model_name=config.get("model_name"),
    )

    # Create queue for thread communication
    import queue
    event_queue: queue.Queue = queue.Queue()

    def run_agent_in_thread():
        try:
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
            )

            for event in agent.run_stream(actual_request, conversation_history=history, image_contents=image_contents):
                event_data = {
                    "event_type": event.event_type,
                    "turn": event.turn,
                    **event.data
                }
                event_queue.put(("event", event_data))

            event_queue.put(("done", None))
        except Exception as e:
            event_queue.put(("error", str(e)))

    async def event_generator():
        start_time = time.time()
        loop = asyncio.get_event_loop()

        # Create trace record
        trace_id = None
        async with AsyncSessionLocal() as trace_db:
            # Determine actual model for trace
            actual_model = config.get("model_name") or settings.default_model_name
            actual_provider = config.get("model_provider") or settings.default_model_provider
            trace = AgentTraceDB(
                request=request.request,
                skills_used=[],  # Will be updated on completion with actually used skills
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
            )
            trace_db.add(trace)
            await trace_db.commit()
            trace_id = trace.id

        # Include session_id in run_started event
        yield f"data: {json.dumps({'event_type': 'run_started', 'turn': 0, 'trace_id': trace_id, 'session_id': session_id})}\n\n"

        # Start agent in thread
        future = loop.run_in_executor(_executor, run_agent_in_thread)

        last_complete_event = None
        collected_steps = []
        current_text_buffer = ""  # Accumulate text_delta chunks
        was_cancelled = False

        try:
            while True:
                try:
                    msg_type, data = await loop.run_in_executor(
                        None, lambda: event_queue.get(timeout=0.1)
                    )

                    if msg_type == "done":
                        break
                    elif msg_type == "error":
                        yield f"data: {json.dumps({'event_type': 'error', 'turn': 0, 'error': data})}\n\n"
                        break
                    elif msg_type == "event":
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                        event_type = data.get("event_type")
                        if event_type == "text_delta":
                            current_text_buffer += data.get("text", "")
                        elif event_type == "assistant" and data.get("content"):
                            collected_steps.append({
                                "role": "assistant",
                                "content": data.get("content", "")[:2000],
                                "tool_name": None,
                                "tool_input": None,
                            })
                        elif event_type in ("tool_call", "tool_result", "turn_start", "complete"):
                            # Flush buffered text as assistant step
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
                                    "content": data.get("tool_result", "")[:5000],
                                    "tool_name": data.get("tool_name"),
                                    "tool_input": data.get("tool_input"),
                                })
                            elif event_type == "complete":
                                last_complete_event = data

                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue

            await future

        except (asyncio.CancelledError, GeneratorExit):
            was_cancelled = True

        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            # Update trace (resilient to task cancellation)
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

            # Save session messages
            if not was_cancelled and session_id and last_complete_event:
                await save_session_messages(
                    session_id,
                    final_answer,
                    request.request,
                    final_messages=last_complete_event.get("final_messages"),
                )

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

        # Validate response mode
        if preset.api_response_mode == "streaming":
            raise HTTPException(
                status_code=400,
                detail="This agent is configured for streaming mode. Use /chat endpoint."
            )

        # Resolve executor name if executor_id is set
        executor_name = None
        if preset.executor_id:
            executor_result = await db.execute(
                select(ExecutorDB).where(ExecutorDB.id == preset.executor_id)
            )
            executor = executor_result.scalar_one_or_none()
            if executor:
                executor_name = executor.name

        # Capture preset config
        config = {
            "skills": preset.skill_ids,
            "allowed_tools": preset.builtin_tools,
            "max_turns": preset.max_turns,
            "equipped_mcp_servers": preset.mcp_servers,
            "system_prompt": preset.system_prompt,
            "model_provider": preset.model_provider,
            "model_name": preset.model_name,
            "executor_name": executor_name,
        }

    # Session management — published agents may omit session_id for auto-creation
    if request.session_id:
        session_id, history = await load_or_create_session(request.session_id, agent_id)
    else:
        from app.db.models import generate_uuid
        auto_sid = generate_uuid()
        session_id, history = await load_or_create_session(auto_sid, agent_id)

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
        )
        trace_db.add(trace)
        await trace_db.commit()
        trace_id = trace.id

    # Run agent synchronously
    loop = asyncio.get_event_loop()
    result_data = {"success": False, "answer": "", "error": None, "steps": [], "total_turns": 0}

    def run_agent_sync():
        try:
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
            )

            result = agent.run(actual_request, conversation_history=history, image_contents=image_contents)
            return {
                "success": result.success,
                "answer": result.answer,
                "error": result.error,
                "total_turns": result.total_turns,
                "total_input_tokens": result.total_input_tokens,
                "total_output_tokens": result.total_output_tokens,
                "skills_used": result.skills_used,
                "output_files": result.output_files or None,
                "final_messages": result.final_messages,
                "steps": [
                    {
                        "role": step.role,
                        "content": step.content[:5000] if step.content else "",
                        "tool_name": step.tool_name,
                        "tool_input": step.tool_input,
                    }
                    for step in (result.steps or [])
                ],
            }
        except Exception as e:
            return {"success": False, "answer": "", "error": str(e), "steps": [], "total_turns": 0}

    result_data = await loop.run_in_executor(_executor, run_agent_sync)
    duration_ms = int((time.time() - start_time) * 1000)

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

    # Save session messages
    if session_id and result_data.get("success"):
        await save_session_messages(
            session_id,
            result_data.get("answer", ""),
            request.request,
            final_messages=result_data.get("final_messages"),
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
