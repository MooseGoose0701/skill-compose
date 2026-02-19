"""
Unit tests for session management helpers (app/api/v1/sessions.py).

Tests the dual-store session pattern:
- `messages`: Append-only display history (never compressed)
- `agent_context`: Agent working message list (whole-replaced each request)

All tests run against a real PostgreSQL test database (skills_api_test).
"""
import uuid
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.database import Base
from app.db.models import PublishedSessionDB
from app.api.v1.sessions import (
    SessionData,
    load_or_create_session,
    save_session_messages,
    save_session_checkpoint,
    pre_compress_if_needed,
)


TEST_DATABASE_URL = "postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test"

AGENT_ID = "test-agent-001"


# ---------------------------------------------------------------------------
# Fixtures — own engine + factory per test (isolated from conftest db_session)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def session_env():
    """Provide (async_session, async_sessionmaker) with fresh tables per test.

    The session functions in sessions.py use AsyncSessionLocal() internally,
    so we patch it with the factory returned here.
    """
    from app.db import models  # noqa: F401 — register models with Base

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_size=3)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = factory()
    try:
        yield session, factory
    finally:
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test: load_or_create_session
# ---------------------------------------------------------------------------


class TestLoadOrCreateSession:
    """Tests for load_or_create_session."""

    @pytest.mark.asyncio
    async def test_create_new_session(self, session_env):
        """Brand-new session returns SessionData with None fields."""
        db, factory = session_env
        session_id = str(uuid.uuid4())

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            data = await load_or_create_session(session_id, AGENT_ID)

        assert isinstance(data, SessionData)
        assert data.session_id == session_id
        assert data.display_messages is None
        assert data.agent_context is None

        # Verify record was created in DB
        result = await db.execute(
            select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.agent_id == AGENT_ID
        assert record.messages == []
        assert record.agent_context is None

    @pytest.mark.asyncio
    async def test_load_existing_with_agent_context(self, session_env):
        """Existing session with agent_context returns both stores."""
        db, factory = session_env
        session_id = str(uuid.uuid4())
        display_msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        agent_ctx = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "<summary>Greeting exchange</summary>"},
        ]

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=display_msgs, agent_context=agent_ctx,
        )
        db.add(session)
        await db.commit()

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            data = await load_or_create_session(session_id, AGENT_ID)

        assert data.session_id == session_id
        assert data.display_messages == display_msgs
        assert data.agent_context == agent_ctx

    @pytest.mark.asyncio
    async def test_backward_compat_null_agent_context(self, session_env):
        """When agent_context is NULL, fallback to copying messages."""
        db, factory = session_env
        session_id = str(uuid.uuid4())
        display_msgs = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=display_msgs, agent_context=None,
        )
        db.add(session)
        await db.commit()

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            data = await load_or_create_session(session_id, AGENT_ID)

        assert data.display_messages == display_msgs
        # agent_context should be a COPY of display messages
        assert data.agent_context == display_msgs
        # But not the same object
        assert data.agent_context is not data.display_messages

    @pytest.mark.asyncio
    async def test_empty_existing_session(self, session_env):
        """Existing session with empty messages returns None agent_context."""
        db, factory = session_env
        session_id = str(uuid.uuid4())

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=[], agent_context=None,
        )
        db.add(session)
        await db.commit()

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            data = await load_or_create_session(session_id, AGENT_ID)

        assert data.display_messages == []
        # Empty list fallback → [] → `if ctx` is False → None
        assert data.agent_context is None

    @pytest.mark.asyncio
    async def test_wrong_agent_id_creates_new(self, session_env):
        """Session lookup with different agent_id creates a new session."""
        db, factory = session_env
        original_id = str(uuid.uuid4())

        session = PublishedSessionDB(
            id=original_id, agent_id="other-agent",
            messages=[{"role": "user", "content": "hi"}],
        )
        db.add(session)
        await db.commit()

        # Use a different session_id to avoid PK conflict
        new_session_id = str(uuid.uuid4())
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            data = await load_or_create_session(new_session_id, AGENT_ID)

        assert data.session_id == new_session_id
        assert data.display_messages is None


# ---------------------------------------------------------------------------
# Test: save_session_messages
# ---------------------------------------------------------------------------


class TestSaveSessionMessages:
    """Tests for save_session_messages (dual-store save)."""

    @pytest.mark.asyncio
    async def test_append_display_and_replace_agent_context(self, session_env):
        """Display messages appended, agent_context whole-replaced."""
        db, factory = session_env
        session_id = str(uuid.uuid4())
        existing_display = [
            {"role": "user", "content": "turn 1"},
            {"role": "assistant", "content": "response 1"},
        ]

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=existing_display,
            agent_context=[{"role": "user", "content": "old context"}],
        )
        db.add(session)
        await db.commit()

        new_display = [
            {"role": "user", "content": "turn 2"},
            {"role": "assistant", "content": "response 2"},
        ]
        new_agent_ctx = [
            {"role": "user", "content": "compressed summary"},
            {"role": "user", "content": "turn 2"},
            {"role": "assistant", "content": "response 2"},
        ]

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="response 2",
                request_text="turn 2",
                final_messages=new_agent_ctx,
                display_append_messages=new_display,
            )

        # Re-read from DB with fresh session
        async with factory() as fresh:
            result = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one()

        # messages should be existing + appended
        assert len(record.messages) == 4
        assert record.messages[:2] == existing_display
        assert record.messages[2:] == new_display

        # agent_context should be completely replaced
        assert record.agent_context == new_agent_ctx

    @pytest.mark.asyncio
    async def test_fallback_simple_user_assistant_pair(self, session_env):
        """Without display_append_messages, falls back to user+assistant pair."""
        db, factory = session_env
        session_id = str(uuid.uuid4())

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID, messages=[],
        )
        db.add(session)
        await db.commit()

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="The answer is 42",
                request_text="What is the meaning?",
            )

        async with factory() as fresh:
            result = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one()

        assert len(record.messages) == 2
        assert record.messages[0] == {"role": "user", "content": "What is the meaning?"}
        assert record.messages[1] == {"role": "assistant", "content": "The answer is 42"}

    @pytest.mark.asyncio
    async def test_nonexistent_session_is_noop(self, session_env):
        """Saving to a nonexistent session does not raise."""
        _, factory = session_env
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id="nonexistent-id",
                final_answer="answer",
                request_text="request",
            )

    @pytest.mark.asyncio
    async def test_agent_context_not_set_when_final_messages_none(self, session_env):
        """When final_messages is None, agent_context should not be updated."""
        db, factory = session_env
        session_id = str(uuid.uuid4())
        original_ctx = [{"role": "user", "content": "original"}]

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=[], agent_context=original_ctx,
        )
        db.add(session)
        await db.commit()

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="answer",
                request_text="request",
                final_messages=None,
            )

        # The save creates its own session, so we need a fresh read
        async with factory() as fresh:
            result = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one()

        # agent_context should remain unchanged
        assert record.agent_context == original_ctx


# ---------------------------------------------------------------------------
# Test: save_session_checkpoint
# ---------------------------------------------------------------------------


class TestSaveSessionCheckpoint:
    """Tests for save_session_checkpoint (agent_context only)."""

    @pytest.mark.asyncio
    async def test_checkpoint_updates_only_agent_context(self, session_env):
        """Checkpoint updates agent_context without touching messages."""
        db, factory = session_env
        session_id = str(uuid.uuid4())
        original_messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=original_messages, agent_context=None,
        )
        db.add(session)
        await db.commit()

        checkpoint_ctx = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
            {"role": "user", "content": "new turn"},
        ]

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_checkpoint(session_id, checkpoint_ctx)

        async with factory() as fresh:
            result = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one()

        # messages should be UNCHANGED
        assert record.messages == original_messages
        # agent_context should be updated
        assert record.agent_context == checkpoint_ctx

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_replace(self, session_env):
        """Multiple checkpoints each replace the previous agent_context."""
        db, factory = session_env
        session_id = str(uuid.uuid4())

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=[{"role": "user", "content": "hi"}],
            agent_context=[{"role": "user", "content": "initial"}],
        )
        db.add(session)
        await db.commit()

        ctx_v1 = [{"role": "user", "content": "checkpoint 1"}]
        ctx_v2 = [{"role": "user", "content": "checkpoint 2"}]

        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_checkpoint(session_id, ctx_v1)
            await save_session_checkpoint(session_id, ctx_v2)

        async with factory() as fresh:
            result = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one()

        # Should be latest checkpoint, not accumulated
        assert record.agent_context == ctx_v2
        # messages untouched
        assert record.messages == [{"role": "user", "content": "hi"}]


# ---------------------------------------------------------------------------
# Test: pre_compress_if_needed
# ---------------------------------------------------------------------------


class TestPreCompressIfNeeded:
    """Tests for pre_compress_if_needed."""

    @pytest.mark.asyncio
    async def test_empty_context_passthrough(self):
        """Empty or None context returns as-is."""
        result = await pre_compress_if_needed([], "kimi", "kimi-k2.5")
        assert result == []

        result = await pre_compress_if_needed(None, "kimi", "kimi-k2.5")
        assert result is None

    @pytest.mark.asyncio
    async def test_below_threshold_passthrough(self):
        """Context below threshold passes through unchanged."""
        short_context = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = await pre_compress_if_needed(short_context, "kimi", "kimi-k2.5")
        assert result == short_context

    @pytest.mark.asyncio
    async def test_above_threshold_triggers_compression(self):
        """Context above threshold calls compress_messages_standalone."""
        large_context = []
        for i in range(100):
            large_context.append({"role": "user", "content": f"Question {i}: " + "x" * 5000})
            large_context.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 5000})

        compressed_result = [
            {"role": "user", "content": "<summary>Compressed</summary>"},
            {"role": "user", "content": "last question"},
            {"role": "assistant", "content": "last answer"},
        ]

        with patch("app.agent.agent.compress_messages_standalone", new_callable=AsyncMock) as mock_compress:
            mock_compress.return_value = (compressed_result, 1000, 200)
            result = await pre_compress_if_needed(large_context, "kimi", "kimi-k2.5")

        assert result == compressed_result
        mock_compress.assert_called_once()

    @pytest.mark.asyncio
    async def test_compression_failure_returns_original(self):
        """If compression fails, returns original context."""
        large_context = []
        for i in range(100):
            large_context.append({"role": "user", "content": "x" * 5000})
            large_context.append({"role": "assistant", "content": "y" * 5000})

        with patch("app.agent.agent.compress_messages_standalone", new_callable=AsyncMock) as mock_compress:
            mock_compress.side_effect = Exception("LLM API error")
            result = await pre_compress_if_needed(large_context, "kimi", "kimi-k2.5")

        # Should return original, not raise
        assert result == large_context


# ---------------------------------------------------------------------------
# Test: Dual-store invariant (integration)
# ---------------------------------------------------------------------------


class TestDualStoreInvariant:
    """Integration tests verifying the dual-store invariant:
    - messages is append-only (grows monotonically)
    - agent_context is whole-replaced (may shrink after compression)
    """

    @pytest.mark.asyncio
    async def test_multi_turn_dual_store(self, session_env):
        """Simulate 3 turns: messages grows, agent_context gets replaced each time."""
        db, factory = session_env
        session_id = str(uuid.uuid4())

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=[], agent_context=None,
        )
        db.add(session)
        await db.commit()

        # Turn 1
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="Response 1",
                request_text="Question 1",
                final_messages=[
                    {"role": "user", "content": "Question 1"},
                    {"role": "assistant", "content": "Response 1"},
                ],
                display_append_messages=[
                    {"role": "user", "content": "Question 1"},
                    {"role": "assistant", "content": "Response 1"},
                ],
            )

        async with factory() as fresh:
            r = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            rec = r.scalar_one()
        assert len(rec.messages) == 2
        assert len(rec.agent_context) == 2

        # Turn 2
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="Response 2",
                request_text="Question 2",
                final_messages=[
                    {"role": "user", "content": "Question 1"},
                    {"role": "assistant", "content": "Response 1"},
                    {"role": "user", "content": "Question 2"},
                    {"role": "assistant", "content": "Response 2"},
                ],
                display_append_messages=[
                    {"role": "user", "content": "Question 2"},
                    {"role": "assistant", "content": "Response 2"},
                ],
            )

        async with factory() as fresh:
            r = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            rec = r.scalar_one()
        assert len(rec.messages) == 4  # Grew: 2 → 4
        assert len(rec.agent_context) == 4  # Replaced: now 4

        # Turn 3 — with compression (agent_context shrinks)
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="Response 3",
                request_text="Question 3",
                final_messages=[
                    {"role": "user", "content": "<summary>Compressed turns 1-2</summary>"},
                    {"role": "user", "content": "Question 3"},
                    {"role": "assistant", "content": "Response 3"},
                ],
                display_append_messages=[
                    {"role": "user", "content": "Question 3"},
                    {"role": "assistant", "content": "Response 3"},
                ],
            )

        async with factory() as fresh:
            r = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            rec = r.scalar_one()

        # messages: monotonically grows (4 → 6)
        assert len(rec.messages) == 6
        assert rec.messages[0]["content"] == "Question 1"
        assert rec.messages[5]["content"] == "Response 3"

        # agent_context: whole-replaced, now compressed (3 messages)
        assert len(rec.agent_context) == 3
        assert "<summary>" in rec.agent_context[0]["content"]

    @pytest.mark.asyncio
    async def test_checkpoint_then_final_save(self, session_env):
        """Checkpoints update agent_context during streaming; final save appends display."""
        db, factory = session_env
        session_id = str(uuid.uuid4())

        session = PublishedSessionDB(
            id=session_id, agent_id=AGENT_ID,
            messages=[
                {"role": "user", "content": "turn 1"},
                {"role": "assistant", "content": "resp 1"},
            ],
            agent_context=[
                {"role": "user", "content": "turn 1"},
                {"role": "assistant", "content": "resp 1"},
            ],
        )
        db.add(session)
        await db.commit()

        # Simulate streaming: checkpoint saves agent_context mid-stream
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_checkpoint(session_id, [
                {"role": "user", "content": "turn 1"},
                {"role": "assistant", "content": "resp 1"},
                {"role": "user", "content": "turn 2"},
                {"role": "assistant", "content": "partial resp 2..."},
            ])

        async with factory() as fresh:
            r = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            rec = r.scalar_one()
        # messages unchanged during checkpoint
        assert len(rec.messages) == 2
        # agent_context updated
        assert len(rec.agent_context) == 4

        # Final save: append display + replace agent_context
        with patch("app.api.v1.sessions.AsyncSessionLocal", factory):
            await save_session_messages(
                session_id=session_id,
                final_answer="complete resp 2",
                request_text="turn 2",
                final_messages=[
                    {"role": "user", "content": "turn 1"},
                    {"role": "assistant", "content": "resp 1"},
                    {"role": "user", "content": "turn 2"},
                    {"role": "assistant", "content": "complete resp 2"},
                ],
                display_append_messages=[
                    {"role": "user", "content": "turn 2"},
                    {"role": "assistant", "content": "complete resp 2"},
                ],
            )

        async with factory() as fresh:
            r = await fresh.execute(
                select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            rec = r.scalar_one()
        # messages grew
        assert len(rec.messages) == 4
        # agent_context final
        assert len(rec.agent_context) == 4
        assert rec.agent_context[-1]["content"] == "complete resp 2"
