"""Agent API - Run the skills agent"""
import asyncio
import base64
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import SkillsAgent
from app.api.v1.sessions import load_or_create_session, save_session_messages, CHAT_SENTINEL_AGENT_ID
from app.db.database import get_db, AsyncSessionLocal, SyncSessionLocal
from app.db.models import AgentTraceDB, AgentPresetDB

logger = logging.getLogger("skills_api")

# Thread pool for running sync generators
_executor = ThreadPoolExecutor(max_workers=8)

router = APIRouter(prefix="/agent", tags=["Agent"])


async def _update_trace_async(trace_id: str, values: dict):
    """Update trace record via async session."""
    async with AsyncSessionLocal() as trace_db:
        await trace_db.execute(
            update(AgentTraceDB)
            .where(AgentTraceDB.id == trace_id)
            .values(**values)
        )
        await trace_db.commit()


def _update_trace_sync(trace_id: str, values: dict):
    """Update trace record via sync session (fallback when async is cancelled)."""
    with SyncSessionLocal() as sync_db:
        sync_db.execute(
            update(AgentTraceDB)
            .where(AgentTraceDB.id == trace_id)
            .values(**values)
        )
        sync_db.commit()


async def _finalize_trace(trace_id: str, values: dict):
    """Update trace with final status, resilient to task cancellation.

    Uses asyncio.shield() to protect the DB update from CancelledError.
    Falls back to sync DB if async fails (e.g. event loop shutting down).
    """
    try:
        await asyncio.shield(_update_trace_async(trace_id, values))
    except (asyncio.CancelledError, Exception) as e:
        logger.warning(f"Async trace update failed for {trace_id}, trying sync fallback: {e}")
        try:
            _update_trace_sync(trace_id, values)
        except Exception as e2:
            logger.error(f"Sync trace update also failed for {trace_id}: {e2}")


class UploadedFile(BaseModel):
    """Info about an uploaded file"""
    file_id: str
    filename: str
    path: str  # Full path for agent to access
    content_type: str


class AgentRequest(BaseModel):
    """Agent run request.

    If agent_id is provided, the preset's config is used and individual
    config fields (skills, allowed_tools, etc.) are ignored.
    """
    request: str = Field(..., description="The task/request for the agent")
    agent_id: Optional[str] = Field(None, description="Agent preset ID. When set, uses preset config and ignores individual config fields.")
    model_provider: Optional[str] = Field(None, description="LLM provider: anthropic, openrouter, openai, google")
    model_name: Optional[str] = Field(None, description="Model name/ID for the provider")
    skills: Optional[List[str]] = Field(None, description="List of skill names to activate (None = all available)")
    allowed_tools: Optional[List[str]] = Field(None, description="List of tool names to enable (None = all available)")
    max_turns: int = Field(60, description="Maximum turns before stopping", ge=1, le=60000)
    session_id: str = Field(..., description="Session ID for server-side session management. "
                                             "History is loaded from DB automatically.")
    uploaded_files: Optional[List[UploadedFile]] = Field(
        None, description="List of uploaded files available to the agent"
    )
    equipped_mcp_servers: Optional[List[str]] = Field(
        None, description="List of MCP server names to enable (None = all available)"
    )
    system_prompt: Optional[str] = Field(
        None, description="Custom system prompt to append to the base prompt"
    )
    executor_id: Optional[str] = Field(
        None, description="Executor ID for code execution (custom mode only, ignored when agent_id is set)"
    )


class StepInfo(BaseModel):
    """Info about a single execution step"""
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None


class AgentResponse(BaseModel):
    """Agent run response"""
    success: bool
    answer: str
    total_turns: int
    steps: List[StepInfo]
    error: Optional[str] = None
    trace_id: Optional[str] = None  # ID of saved trace for later reference
    output_files: Optional[List[dict]] = None


async def _resolve_agent_config(request: AgentRequest, db: AsyncSession) -> dict:
    """Resolve effective agent config. If agent_id is set, load preset and use its config."""
    from sqlalchemy import select
    from app.db.models import ExecutorDB

    if not request.agent_id:
        # Custom mode: resolve executor_name from executor_id if provided
        executor_name = None
        if request.executor_id:
            executor_result = await db.execute(
                select(ExecutorDB).where(ExecutorDB.id == request.executor_id)
            )
            executor = executor_result.scalar_one_or_none()
            if executor:
                executor_name = executor.name

        return {
            "skills": request.skills,
            "allowed_tools": request.allowed_tools,
            "max_turns": request.max_turns,
            "equipped_mcp_servers": request.equipped_mcp_servers,
            "system_prompt": request.system_prompt,
            "model_provider": request.model_provider,
            "model_name": request.model_name,
            "agent_id": None,
            "executor_name": executor_name,
        }

    result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == request.agent_id)
    )
    preset = result.scalar_one_or_none()
    if not preset:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Agent preset '{request.agent_id}' not found")

    # Get executor name if executor_id is set
    executor_name = None
    if preset.executor_id:
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
        "model_provider": preset.model_provider or request.model_provider,
        "model_name": preset.model_name or request.model_name,
        "agent_id": preset.id,
        "executor_name": executor_name,
    }


def _build_request_with_files(
    request_text: str,
    uploaded_files: Optional[List[UploadedFile]],
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[str, Optional[List[dict]]]:
    """Build the actual request text and image content blocks from uploaded files.

    Separates image files (for vision-capable models) from non-image files.
    Images are encoded as base64 Anthropic-format image blocks.
    Non-image files are appended as text paths in the request.

    Returns:
        (actual_request, image_contents) where image_contents is None if no images
        or the model doesn't support vision.
    """
    if not uploaded_files:
        return request_text, None

    from app.llm.models import supports_vision

    # Check if model supports vision
    provider = model_provider or "kimi"
    model = model_name or "kimi-k2.5"
    has_vision = supports_vision(provider, model)

    # Separate image files from non-image files
    image_files = []
    non_image_files = []
    for f in uploaded_files:
        if has_vision and f.content_type and f.content_type.startswith("image/"):
            image_files.append(f)
        else:
            non_image_files.append(f)

    # Build text request with non-image file paths
    actual_request = request_text
    if non_image_files:
        files_info = "\n".join([
            f"- {f.filename}: {Path(f.path).resolve()} (type: {f.content_type})"
            for f in non_image_files
        ])
        actual_request = f"""{request_text}

[Uploaded Files]
The user has uploaded the following files that you can access:
{files_info}

IMPORTANT: Use the absolute file paths shown above when reading or processing files."""

    # Build image content blocks
    image_contents = None
    if image_files:
        image_contents = []
        for f in image_files:
            try:
                file_path = Path(f.path).resolve()
                with open(file_path, "rb") as fp:
                    data = base64.standard_b64encode(fp.read()).decode("utf-8")
                image_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": f.content_type,
                        "data": data,
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to read image file {f.filename}: {e}")
                # Fall back to text path for this file
                actual_request += f"\n- {f.filename}: {Path(f.path).resolve()} (type: {f.content_type})"

        if not image_contents:
            image_contents = None

    return actual_request, image_contents


@router.post("/run", response_model=AgentResponse)
async def run_agent(request: AgentRequest, db: AsyncSession = Depends(get_db)):
    """
    Run the skills agent on a task.

    The agent will:
    1. List available skills
    2. Read relevant skill documentation
    3. Write and execute code
    4. Return the final result

    Execution traces are automatically saved to the database.

    All built-in tools are always available to the agent.
    MCP tools depend on the equipped_mcp_servers parameter.

    Example:
        POST /api/v1/agent/run
        {"request": "Analyze sales data and generate a report"}
    """
    # Resolve config from agent_id or individual fields
    config = await _resolve_agent_config(request, db)

    start_time = time.time()

    agent = SkillsAgent(
        model=config.get("model_name"),
        model_provider=config.get("model_provider"),
        max_turns=config["max_turns"],
        verbose=True,
        allowed_skills=config["skills"],
        allowed_tools=config["allowed_tools"],
        equipped_mcp_servers=config["equipped_mcp_servers"],
        custom_system_prompt=config["system_prompt"],
        executor_name=config.get("executor_name"),
    )

    try:
        # Load session history from DB
        agent_id = request.agent_id or CHAT_SENTINEL_AGENT_ID
        session_id, history = await load_or_create_session(request.session_id, agent_id)

        # Build the actual request with file info and image blocks
        actual_request, image_contents = _build_request_with_files(
            request.request,
            request.uploaded_files,
            model_provider=config.get("model_provider"),
            model_name=config.get("model_name"),
        )

        result = agent.run(actual_request, conversation_history=history, image_contents=image_contents)

        duration_ms = int((time.time() - start_time) * 1000)

        # Save trace to database
        trace = AgentTraceDB(
            request=request.request,
            skills_used=result.skills_used or [],
            model_provider=agent.model_provider,
            model=agent.model,
            status="completed" if result.success else "failed",
            success=result.success,
            answer=result.answer,
            error=result.error,
            total_turns=result.total_turns,
            total_input_tokens=result.total_input_tokens,
            total_output_tokens=result.total_output_tokens,
            steps=[asdict(step) for step in result.steps],
            llm_calls=[asdict(call) for call in result.llm_calls],
            duration_ms=duration_ms,
        )
        db.add(trace)
        await db.commit()

        # Save session
        await save_session_messages(
            session_id,
            result.answer or "",
            request.request,
            final_messages=result.final_messages if hasattr(result, 'final_messages') else None,
        )

        return AgentResponse(
            success=result.success,
            answer=result.answer,
            total_turns=result.total_turns,
            steps=[
                StepInfo(
                    role=step.role,
                    content=step.content[:1000] if step.content else "",
                    tool_name=step.tool_name,
                    tool_input=step.tool_input,
                )
                for step in result.steps
            ],
            error=result.error,
            trace_id=trace.id,
            output_files=result.output_files or None,
        )
    finally:
        # Always cleanup workspace
        agent.cleanup()


@router.post("/run/stream")
async def run_agent_stream(request: AgentRequest, db: AsyncSession = Depends(get_db)):
    """
    Run the skills agent with streaming output (SSE).

    Returns Server-Sent Events with each turn's progress.
    Event types:
    - turn_start: New turn started
    - text_delta: Incremental text chunk from LLM
    - assistant: Assistant text response (legacy, may be skipped when text_delta is used)
    - tool_call: Tool being called
    - tool_result: Tool execution result
    - complete: Agent finished successfully
    - error: Agent encountered an error
    """
    # Resolve config from agent_id or individual fields
    config = await _resolve_agent_config(request, db)

    # Build the actual request with file info and image blocks
    actual_request, image_contents = _build_request_with_files(
        request.request,
        request.uploaded_files,
        model_provider=config.get("model_provider"),
        model_name=config.get("model_name"),
    )

    # Load session history from DB
    agent_id = request.agent_id or CHAT_SENTINEL_AGENT_ID
    session_id, history = await load_or_create_session(request.session_id, agent_id)

    # Create queue for thread communication
    import queue
    event_queue: queue.Queue = queue.Queue()

    def run_agent_in_thread():
        """Run the synchronous agent in a separate thread."""
        agent = None
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
        finally:
            # Always cleanup workspace
            if agent:
                agent.cleanup()

    async def event_generator():
        start_time = time.time()
        loop = asyncio.get_event_loop()

        # Create trace record at the start (with running status)
        trace_id = None
        from app.config import settings as app_settings
        effective_provider = config.get("model_provider") or app_settings.default_model_provider
        effective_model = config.get("model_name") or app_settings.default_model_name
        async with AsyncSessionLocal() as trace_db:
            trace = AgentTraceDB(
                request=request.request,
                skills_used=[],  # Will be updated on completion with actually used skills
                model_provider=effective_provider,
                model=effective_model,
                status="running",  # Will be updated on completion
                success=False,  # Will be updated on completion
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

        # Send run_started event with trace_id and session_id
        yield f"data: {json.dumps({'event_type': 'run_started', 'turn': 0, 'trace_id': trace_id, 'session_id': session_id})}\n\n"

        # Start agent in thread
        future = loop.run_in_executor(_executor, run_agent_in_thread)

        last_complete_event = None
        collected_steps = []  # Collect steps during streaming
        current_text_buffer = ""  # Accumulate text_delta chunks
        was_cancelled = False

        try:
            while True:
                # Check queue for events (non-blocking with small timeout)
                try:
                    # Use run_in_executor to avoid blocking the event loop
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

                        # Collect steps from events
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
                    # No event yet, continue waiting
                    await asyncio.sleep(0.05)
                    continue

            # Wait for thread to finish
            await future

        except (asyncio.CancelledError, GeneratorExit):
            # Request was cancelled (e.g., user clicked Stop)
            was_cancelled = True
            # Don't re-raise, let finally block update the trace

        finally:
            # Always update trace record with final results
            duration_ms = int((time.time() - start_time) * 1000)

            # Determine final status
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

            await _finalize_trace(trace_id, {
                "status": final_status,
                "success": is_success,
                "answer": last_complete_event.get("answer", "") if last_complete_event else "",
                "error": error_msg,
                "total_turns": last_complete_event.get("total_turns", 0) if last_complete_event else 0,
                "total_input_tokens": last_complete_event.get("total_input_tokens", 0) if last_complete_event else 0,
                "total_output_tokens": last_complete_event.get("total_output_tokens", 0) if last_complete_event else 0,
                "skills_used": last_complete_event.get("skills_used", []) if last_complete_event else [],
                "steps": collected_steps,
                "duration_ms": duration_ms,
            })

            # Save session messages
            final_messages = last_complete_event.get("final_messages") if last_complete_event else None
            await save_session_messages(
                session_id,
                last_complete_event.get("answer", "") if last_complete_event else "",
                request.request,
                final_messages=final_messages,
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
