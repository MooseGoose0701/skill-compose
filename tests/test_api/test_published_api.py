"""
Tests for Published Agent API endpoints.

Endpoints tested:
- GET  /api/v1/published/{id}                     — Get published agent info
- GET  /api/v1/published/{id}/sessions/{sid}       — Get session messages
- POST /api/v1/published/{id}/chat                 — SSE streaming chat
- POST /api/v1/published/{id}/chat/{trace_id}/steer — Steer running agent

Note: Published endpoints use AsyncSessionLocal directly (not get_db),
so we must mock AsyncSessionLocal to control database interactions.
"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import StreamEvent
from app.agent.event_stream import EventStream
from app.db.models import AgentPresetDB, AgentTraceDB, PublishedSessionDB

API = "/api/v1/published"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_preset(published=True, **overrides):
    """Create an AgentPresetDB-like mock."""
    preset = MagicMock(spec=AgentPresetDB)
    preset.id = overrides.get("id", str(uuid.uuid4()))
    preset.name = overrides.get("name", "test-agent")
    preset.description = overrides.get("description", "Test agent")
    preset.is_published = published
    preset.api_response_mode = overrides.get("api_response_mode", "streaming")
    preset.skill_ids = overrides.get("skill_ids", ["test-skill"])
    preset.builtin_tools = overrides.get("builtin_tools", None)
    preset.max_turns = overrides.get("max_turns", 10)
    preset.mcp_servers = overrides.get("mcp_servers", ["fetch"])
    preset.system_prompt = overrides.get("system_prompt", None)
    return preset


def _make_session_record(agent_id, session_id=None, messages=None):
    """Create a PublishedSessionDB-like mock (no spec to allow all attrs)."""
    record = MagicMock()
    record.id = session_id or str(uuid.uuid4())
    record.agent_id = agent_id
    record.messages = messages or [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    record.created_at = datetime(2025, 1, 1)
    record.updated_at = datetime(2025, 1, 1)
    return record


def _mock_db_factory(*scalars):
    """Build a callable that returns async context managers for AsyncSessionLocal.

    Each ``db.execute()`` call (across any number of ``AsyncSessionLocal()``
    context managers) returns the next item from *scalars* via
    ``result.scalar_one_or_none()``.

    Use as ``MockSL.side_effect = _mock_db_factory(preset, session)``.
    """
    call_idx = {"i": 0}

    def _next_result():
        idx = call_idx["i"] % len(scalars) if scalars else 0
        call_idx["i"] += 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = scalars[idx] if scalars else None
        return mock_result

    def _make_ctx():
        @asynccontextmanager
        async def _ctx():
            mock_sess = AsyncMock(spec=AsyncSession)
            mock_sess.execute = AsyncMock(side_effect=lambda *a, **kw: _next_result())
            mock_sess.add = MagicMock()
            mock_sess.commit = AsyncMock()
            yield mock_sess

        return _ctx()

    return _make_ctx


# ---------------------------------------------------------------------------
# GET /published/{agent_id}
# ---------------------------------------------------------------------------


class TestGetPublishedAgent:
    """Tests for GET /api/v1/published/{agent_id}."""

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_get_published_agent_info(self, MockSL, client: AsyncClient):
        """Fetching a published agent returns its public info."""
        preset = _make_preset(published=True)
        MockSL.side_effect = _mock_db_factory(preset)

        resp = await client.get(f"{API}/{preset.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == preset.id
        assert body["name"] == preset.name

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_get_unpublished_agent_404(self, MockSL, client: AsyncClient):
        """Fetching an unpublished agent returns 404."""
        MockSL.side_effect = _mock_db_factory(None)

        resp = await client.get(f"{API}/{str(uuid.uuid4())}")
        assert resp.status_code == 404

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_get_nonexistent_agent_404(self, MockSL, client: AsyncClient):
        """Fetching a nonexistent agent returns 404."""
        MockSL.side_effect = _mock_db_factory(None)

        resp = await client.get(f"{API}/{str(uuid.uuid4())}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /published/{agent_id}/sessions/{session_id}
# ---------------------------------------------------------------------------


class TestGetSession:
    """Tests for GET /api/v1/published/{agent_id}/sessions/{session_id}."""

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_get_session_messages(self, MockSL, client: AsyncClient):
        """Fetching an existing session returns its messages."""
        preset = _make_preset(published=True)
        session = _make_session_record(preset.id)

        # First call → find preset; second call → find session
        MockSL.side_effect = _mock_db_factory(preset, session)

        resp = await client.get(
            f"{API}/{preset.id}/sessions/{session.id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == session.id
        assert body["agent_id"] == preset.id
        assert len(body["messages"]) == 2

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_get_session_agent_not_found(self, MockSL, client: AsyncClient):
        """If agent is not published, return 404."""
        MockSL.side_effect = _mock_db_factory(None)

        resp = await client.get(
            f"{API}/{str(uuid.uuid4())}/sessions/{str(uuid.uuid4())}"
        )
        assert resp.status_code == 404

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_get_session_not_found(self, MockSL, client: AsyncClient):
        """Fetching a nonexistent session returns 404."""
        preset = _make_preset(published=True)
        # First call → find preset; second call → no session
        MockSL.side_effect = _mock_db_factory(preset, None)

        resp = await client.get(
            f"{API}/{preset.id}/sessions/{str(uuid.uuid4())}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /published/{agent_id}/chat
# ---------------------------------------------------------------------------


def _make_stream_events():
    """Minimal StreamEvent objects for a successful agent run."""
    return [
        StreamEvent(event_type="turn_start", turn=1, data={"turn": 1}),
        StreamEvent(
            event_type="assistant",
            turn=1,
            data={"content": "Hello!", "turn": 1},
        ),
        StreamEvent(
            event_type="complete",
            turn=1,
            data={
                "success": True,
                "answer": "Done",
                "total_turns": 1,
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "skills_used": [],
                "output_files": [],
                "final_messages": [],
            },
        ),
    ]


def _make_mock_agent_instance(events=None):
    """Create a mock SkillsAgent whose run() pushes events to event_stream."""
    from app.agent.agent import AgentResult

    if events is None:
        events = _make_stream_events()

    complete_event = next((e for e in events if e.event_type == "complete"), None)
    result = AgentResult(
        success=complete_event.data.get("success", True) if complete_event else True,
        answer=complete_event.data.get("answer", "Done") if complete_event else "Done",
        total_turns=complete_event.data.get("total_turns", 1) if complete_event else 1,
        total_input_tokens=complete_event.data.get("total_input_tokens", 100) if complete_event else 100,
        total_output_tokens=complete_event.data.get("total_output_tokens", 50) if complete_event else 50,
        skills_used=complete_event.data.get("skills_used", []) if complete_event else [],
        output_files=complete_event.data.get("output_files", []) if complete_event else [],
        final_messages=complete_event.data.get("final_messages", []) if complete_event else [],
    )

    mock_instance = MagicMock()
    mock_instance.model = "kimi-k2.5"
    mock_instance.model_provider = "kimi"
    mock_instance.cleanup = MagicMock()

    async def mock_run(request, conversation_history=None, image_contents=None,
                       event_stream=None, cancellation_event=None):
        if event_stream:
            for event in events:
                await event_stream.push(event)
            await event_stream.close()
        return result

    mock_instance.run = AsyncMock(side_effect=mock_run)
    return mock_instance


class TestPublishedChat:
    """Tests for POST /api/v1/published/{agent_id}/chat."""

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_chat_unpublished_404(self, MockSL, client: AsyncClient):
        """Chatting with an unpublished agent returns 404."""
        MockSL.side_effect = _mock_db_factory(None)

        resp = await client.post(
            f"{API}/{str(uuid.uuid4())}/chat",
            json={"request": "hello"},
        )
        assert resp.status_code == 404

    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_chat_nonexistent_404(self, MockSL, client: AsyncClient):
        """Chatting with a nonexistent agent returns 404."""
        MockSL.side_effect = _mock_db_factory(None)

        resp = await client.post(
            f"{API}/{str(uuid.uuid4())}/chat",
            json={"request": "hello"},
        )
        assert resp.status_code == 404

    @patch("app.api.v1.published.SkillsAgent")
    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_chat_creates_session(
        self, MockSL, MockAgent, client: AsyncClient
    ):
        """Chatting with a valid published agent returns SSE stream."""
        preset = _make_preset(published=True)
        preset.model_provider = None
        preset.model_name = None
        preset.executor_id = None

        # Mock agent
        MockAgent.return_value = _make_mock_agent_instance()

        # Build a mock session local that returns preset on first call,
        # then no session (new session), then works for trace/session saves
        mock_result_preset = MagicMock()
        mock_result_preset.scalar_one_or_none.return_value = preset

        mock_result_no_session = MagicMock()
        mock_result_no_session.scalar_one_or_none.return_value = None

        mock_result_empty = MagicMock()
        mock_result_empty.scalar_one_or_none.return_value = None

        call_idx = {"i": 0}
        results = [mock_result_preset, mock_result_no_session, mock_result_empty, mock_result_empty, mock_result_empty]

        @asynccontextmanager
        async def _ctx():
            idx = min(call_idx["i"], len(results) - 1)
            call_idx["i"] += 1

            mock_sess = AsyncMock(spec=AsyncSession)
            mock_sess.execute = AsyncMock(return_value=results[idx])
            mock_sess.add = MagicMock()
            mock_sess.commit = AsyncMock()
            yield mock_sess

        MockSL.side_effect = lambda: _ctx()

        session_id = str(uuid.uuid4())
        resp = await client.post(
            f"{API}/{preset.id}/chat",
            json={"request": "hello", "session_id": session_id},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # Parse SSE events
        lines = [l for l in resp.text.strip().split("\n") if l.startswith("data: ")]
        assert len(lines) >= 1
        first = json.loads(lines[0].replace("data: ", ""))
        assert first["event_type"] == "run_started"
        assert first["session_id"] == session_id


# ---------------------------------------------------------------------------
# POST /published/{agent_id}/chat/{trace_id}/steer
# ---------------------------------------------------------------------------


class TestPublishedSteer:
    """Tests for POST /api/v1/published/{agent_id}/chat/{trace_id}/steer."""

    async def test_steer_no_active_run_404(self, client: AsyncClient):
        """Steering a non-existent trace returns 404."""
        agent_id = str(uuid.uuid4())
        resp = await client.post(
            f"{API}/{agent_id}/chat/nonexistent-trace/steer",
            json={"message": "switch to plan B"},
        )
        assert resp.status_code == 404
        assert "No active run" in resp.json()["detail"]

    async def test_steer_completed_run_409(self, client: AsyncClient):
        """Steering a completed (closed) stream returns 409."""
        from app.api.v1.published import _active_streams

        es = EventStream()
        await es.close()
        _active_streams["pub-trace-closed"] = es

        agent_id = str(uuid.uuid4())
        try:
            resp = await client.post(
                f"{API}/{agent_id}/chat/pub-trace-closed/steer",
                json={"message": "too late"},
            )
            assert resp.status_code == 409
            assert "already completed" in resp.json()["detail"]
        finally:
            _active_streams.pop("pub-trace-closed", None)

    async def test_steer_injects_message(self, client: AsyncClient):
        """Steering an active published stream injects the message."""
        from app.api.v1.published import _active_streams

        es = EventStream()
        _active_streams["pub-trace-active"] = es

        agent_id = str(uuid.uuid4())
        try:
            resp = await client.post(
                f"{API}/{agent_id}/chat/pub-trace-active/steer",
                json={"message": "use a different approach"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "injected"

            # Verify the injection was received
            assert es.has_injection() is True
            assert es.get_injection_nowait() == "use a different approach"
        finally:
            _active_streams.pop("pub-trace-active", None)

    async def test_steer_cross_worker_via_filesystem(self, client: AsyncClient, db_session):
        """Cross-worker steering: running trace in DB + filesystem queue."""
        from app.agent.steering import STEERING_DIR, cleanup_steering_dir

        trace = AgentTraceDB(
            request="test",
            skills_used=[],
            model="test",
            model_provider="test",
            status="running",
            success=False,
            answer="",
            total_turns=0,
            total_input_tokens=0,
            total_output_tokens=0,
            steps=[],
            llm_calls=[],
            duration_ms=0,
        )
        db_session.add(trace)
        await db_session.commit()

        agent_id = str(uuid.uuid4())
        try:
            resp = await client.post(
                f"{API}/{agent_id}/chat/{trace.id}/steer",
                json={"message": "published cross-worker steer"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "injected"

            # Verify filesystem message
            trace_dir = STEERING_DIR / trace.id
            msg_files = list(trace_dir.glob("*.msg"))
            assert len(msg_files) == 1
            assert msg_files[0].read_text(encoding="utf-8") == "published cross-worker steer"
        finally:
            cleanup_steering_dir(trace.id)
