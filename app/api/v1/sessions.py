"""Shared session management helpers.

Used by both the agent (chat panel) and published agent endpoints
to load/create/save server-side sessions via PublishedSessionDB.

Dual-store design:
- `messages`: Append-only display history — never compressed, preserves all
  tool_use/tool_result blocks for frontend rendering.
- `agent_context`: Agent working message list — whole-replaced each request,
  may contain compression summaries.  NULL → fallback to `messages`.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update

from app.db.database import AsyncSessionLocal
from app.db.models import PublishedSessionDB

logger = logging.getLogger("skills_api")

# Sentinel agent_id for chat-panel sessions (not tied to a published agent)
CHAT_SENTINEL_AGENT_ID = "__chat__"


@dataclass
class SessionData:
    """Data returned from load_or_create_session."""
    session_id: str
    display_messages: Optional[List[dict]] = None  # Full display history (for append)
    agent_context: Optional[List[dict]] = None      # Agent working messages


async def load_or_create_session(
    session_id: str,
    agent_id: str,
) -> SessionData:
    """Load existing session or create a new one.

    Returns SessionData with display_messages and agent_context.
    For brand-new sessions both fields are None.
    For existing sessions with agent_context=NULL, falls back to copying messages.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishedSessionDB).where(
                PublishedSessionDB.id == session_id,
                PublishedSessionDB.agent_id == agent_id,
            )
        )
        session_record = result.scalar_one_or_none()

        if session_record:
            display = session_record.messages or []
            # Fallback: if agent_context is NULL, use messages as starting context
            ctx = session_record.agent_context
            if ctx is None:
                ctx = list(display)  # Copy so mutations don't affect display
            return SessionData(
                session_id=session_id,
                display_messages=display,
                agent_context=ctx if ctx else None,
            )
        else:
            # Create new session with caller-provided ID
            new_session = PublishedSessionDB(
                id=session_id,
                agent_id=agent_id,
                messages=[],
                agent_context=None,
            )
            db.add(new_session)
            await db.commit()

            return SessionData(session_id=session_id)


async def save_session_messages(
    session_id: str,
    final_answer: str,
    request_text: str,
    final_messages: Optional[list] = None,
    display_append_messages: Optional[list] = None,
) -> None:
    """Save conversation data to session (dual-store).

    - `agent_context`: whole-replaced with *final_messages* (the agent's working
      message list, which may include compression summaries).
    - `messages`: *display_append_messages* are appended to the existing display
      history.  If not provided, falls back to appending a simple user+assistant pair.
    """
    try:
        async with AsyncSessionLocal() as session_db:
            result = await session_db.execute(
                select(PublishedSessionDB).where(
                    PublishedSessionDB.id == session_id,
                )
            )
            session_record = result.scalar_one_or_none()
            if not session_record:
                return

            # Build values dict
            values = {"updated_at": datetime.utcnow()}

            # agent_context — whole-replace
            if final_messages is not None:
                values["agent_context"] = final_messages

            # messages — append display data
            current_display = session_record.messages or []
            if display_append_messages:
                current_display = current_display + display_append_messages
            else:
                # Fallback: append simple user+assistant pair
                if request_text:
                    current_display = list(current_display)
                    current_display.append({"role": "user", "content": request_text})
                    if final_answer:
                        current_display.append({"role": "assistant", "content": final_answer})
            values["messages"] = current_display

            await session_db.execute(
                update(PublishedSessionDB)
                .where(PublishedSessionDB.id == session_id)
                .values(**values)
            )
            await session_db.commit()
    except Exception:
        pass  # Don't fail the response if session save fails


async def save_session_checkpoint(
    session_id: str,
    agent_context: list,
) -> None:
    """Incremental checkpoint: update only agent_context (turn_complete saves).

    This does NOT touch `messages` — display history is only appended at the
    final save to avoid partial/duplicate entries during streaming.
    """
    try:
        async with AsyncSessionLocal() as session_db:
            await session_db.execute(
                update(PublishedSessionDB)
                .where(PublishedSessionDB.id == session_id)
                .values(
                    agent_context=agent_context,
                    updated_at=datetime.utcnow(),
                )
            )
            await session_db.commit()
    except Exception:
        pass  # fire-and-forget


async def pre_compress_if_needed(
    agent_context: List[dict],
    model_provider: str,
    model_name: str,
) -> List[dict]:
    """Pre-compress agent context if token estimate exceeds model threshold.

    Called before passing context to the agent to avoid "LLM stream failed"
    errors when accumulated tokens exceed the model's context window.

    Returns the (possibly compressed) context.
    """
    from app.agent.agent import COMPRESSION_THRESHOLD_RATIO, CHARS_PER_TOKEN
    from app.llm.models import get_context_limit

    if not agent_context:
        return agent_context

    context_limit = get_context_limit(model_provider, model_name)
    threshold = int(context_limit * COMPRESSION_THRESHOLD_RATIO)

    # Estimate token count from serialized content
    total_chars = sum(
        len(json.dumps(msg.get("content", ""), ensure_ascii=False))
        for msg in agent_context
    )
    estimated_tokens = int(total_chars / CHARS_PER_TOKEN)

    if estimated_tokens <= threshold:
        return agent_context

    logger.info(
        f"[Pre-Compress] Estimated {estimated_tokens} tokens exceeds threshold {threshold}, compressing..."
    )

    try:
        from app.agent.agent import compress_messages_standalone
        compressed, s_in, s_out = await compress_messages_standalone(
            agent_context, model_provider, model_name, verbose=True
        )
        logger.info(f"[Pre-Compress] Done: {len(agent_context)} → {len(compressed)} messages (summary: {s_in}in/{s_out}out)")
        return compressed
    except Exception as e:
        logger.warning(f"[Pre-Compress] Failed: {e}, using original context")
        return agent_context
