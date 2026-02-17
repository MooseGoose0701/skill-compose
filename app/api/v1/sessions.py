"""Shared session management helpers.

Used by both the agent (chat panel) and published agent endpoints
to load/create/save server-side sessions via PublishedSessionDB.
"""
from datetime import datetime
from typing import Optional, Tuple, List

from sqlalchemy import select, update

from app.db.database import AsyncSessionLocal
from app.db.models import PublishedSessionDB

# Sentinel agent_id for chat-panel sessions (not tied to a published agent)
CHAT_SENTINEL_AGENT_ID = "__chat__"


async def load_or_create_session(
    session_id: str,
    agent_id: str,
) -> Tuple[str, Optional[List[dict]]]:
    """Load existing session or create a new one.

    Returns (session_id, history) where history is None for brand-new sessions.
    """
    history = None

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishedSessionDB).where(
                PublishedSessionDB.id == session_id,
                PublishedSessionDB.agent_id == agent_id,
            )
        )
        session_record = result.scalar_one_or_none()

        if session_record:
            history = session_record.messages or []
        else:
            # Create new session with caller-provided ID
            new_session = PublishedSessionDB(
                id=session_id,
                agent_id=agent_id,
                messages=[],
            )
            db.add(new_session)
            await db.commit()

    return session_id, history


async def save_session_messages(
    session_id: str,
    final_answer: str,
    request_text: str,
    final_messages: Optional[list] = None,
) -> None:
    """Save full conversation messages to session.

    If *final_messages* is provided (the full Anthropic message list from the
    agent run), it replaces the session messages entirely.  Otherwise we
    append a simple user/assistant pair.
    """
    try:
        async with AsyncSessionLocal() as session_db:
            result = await session_db.execute(
                select(PublishedSessionDB).where(
                    PublishedSessionDB.id == session_id,
                )
            )
            session_record = result.scalar_one_or_none()
            if session_record:
                if final_messages:
                    await session_db.execute(
                        update(PublishedSessionDB)
                        .where(PublishedSessionDB.id == session_id)
                        .values(
                            messages=final_messages,
                            updated_at=datetime.utcnow(),
                        )
                    )
                else:
                    current_messages = session_record.messages or []
                    current_messages.append({"role": "user", "content": request_text})
                    if final_answer:
                        current_messages.append({"role": "assistant", "content": final_answer})
                    await session_db.execute(
                        update(PublishedSessionDB)
                        .where(PublishedSessionDB.id == session_id)
                        .values(
                            messages=current_messages,
                            updated_at=datetime.utcnow(),
                        )
                    )
                await session_db.commit()
    except Exception:
        pass  # Don't fail the response if session save fails
