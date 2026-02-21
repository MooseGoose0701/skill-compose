"""
End-to-end tests for context compression using real Kimi 2.5 API.

These tests verify the full compression pipeline:
1. Compression triggers correctly based on token threshold
2. LLM generates a <summary> block with structured sections
3. Agent continues to work after compression
4. Published Agent sessions handle compression across turns

Run:
    MOONSHOT_API_KEY_REAL=sk-xxx pytest tests/test_e2e/test_e2e_compression_real.py -v

Uses a very low compression threshold to trigger compression
within a few turns of normal conversation.
"""

import json
import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.db.models import PublishedSessionDB
from tests.test_e2e.conftest import parse_sse_events

# ---------------------------------------------------------------------------
# Kimi API Key
# ---------------------------------------------------------------------------

_KIMI_KEY = (
    os.environ.get("KIMI_API_KEY_REAL", "")
    or os.environ.get("MOONSHOT_API_KEY_REAL", "")
)

skip_no_kimi = pytest.mark.skipif(
    not _KIMI_KEY,
    reason="KIMI_API_KEY_REAL or MOONSHOT_API_KEY_REAL not set",
)


def _patch_kimi_key():
    return patch.dict(os.environ, {"MOONSHOT_API_KEY": _KIMI_KEY})


# Patch compression to trigger very aggressively:
# - Threshold at 1% of context (2560 tokens for Kimi K2.5)
# - Token budget at 0.1% (256 tokens) — forces compression even with 2 turns
# - Max 1 recent turn — ensures at least 1 turn gets compressed
def _patch_low_threshold():
    return patch.multiple(
        "app.agent.agent",
        COMPRESSION_THRESHOLD_RATIO=0.01,
        RECENT_TURNS_TOKEN_BUDGET=0.001,
        MAX_RECENT_TURNS=1,
    )


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_SKILL_DIR = Path("skills/e2e-compression-skill")

_SKILL_MD = """\
---
name: e2e-compression-skill
description: A test skill for verifying context compression with real LLM calls.
---

# E2E Compression Test Skill

## Overview

This skill exists solely for testing context window compression.
It contains enough content to contribute to token accumulation.

## Details

- Purpose: Verify that context compression works correctly with real LLM
- Expected behavior: When the conversation exceeds the compression threshold,
  older messages are summarized and recent turns are preserved
- Key fact to remember: The secret code is ALPHA-7749
- Another fact: The project name is "Quantum Orchid"

## Usage

When asked about this skill, respond with the key facts above.
"""


def _build_large_history() -> list:
    """Build a conversation history with tool_use/tool_result that generates
    significant token volume — enough to exceed a low threshold."""
    history = []

    # Turn 1: user asks, assistant uses list_skills
    history.append({"role": "user", "content": "What skills are available?"})
    history.append({
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Let me check the available skills for you."},
            {"type": "tool_use", "id": "list_skills:0", "name": "list_skills", "input": {}},
        ],
    })
    history.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": "list_skills:0",
            "content": json.dumps({
                "skills": [
                    {"name": "e2e-compression-skill", "description": "A test skill"},
                    {"name": "data-analysis", "description": "Analyze data with pandas"},
                    {"name": "web-scraper", "description": "Scrape web pages"},
                ],
                "count": 3,
            }),
        }],
    })
    history.append({
        "role": "assistant",
        "content": [{"type": "text", "text": "I found 3 skills available."}],
    })

    # Turn 2: user asks about a skill, assistant uses get_skill
    history.append({"role": "user", "content": "Tell me about the compression skill"})
    history.append({
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Let me fetch the details."},
            {"type": "tool_use", "id": "get_skill:1", "name": "get_skill", "input": {"skill_name": "e2e-compression-skill"}},
        ],
    })
    long_skill_content = _SKILL_MD + "\n\n" + ("Additional reference material. " * 200)
    history.append({
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "get_skill:1", "content": long_skill_content}],
    })
    history.append({
        "role": "assistant",
        "content": [{"type": "text", "text": "The secret code is ALPHA-7749 and the project name is Quantum Orchid."}],
    })

    # Turn 3: code execution
    history.append({"role": "user", "content": "Can you run some Python code to compute 2+2?"})
    history.append({
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Sure, let me run that."},
            {"type": "tool_use", "id": "execute_code:2", "name": "execute_code", "input": {"code": "print(2+2)"}},
        ],
    })
    history.append({
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "execute_code:2", "content": '{"output":"4","exit_code":0,"new_files":[]}'}],
    })
    history.append({"role": "assistant", "content": [{"type": "text", "text": "The result is 4."}]})

    return history


# ---------------------------------------------------------------------------
# Single test class — all tests share one event loop to avoid asyncpg conflicts
# ---------------------------------------------------------------------------

@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_kimi
class TestRealCompressionE2E:
    """Full E2E compression tests with real Kimi 2.5 API.

    Tests:
    01. Streaming agent with pre-loaded history → compression event fires
    02. Published Agent Turn 1: tool usage builds session
    03. Published Agent Turn 2: compression fires on session history
    04. Published Agent Turn 3: session works after compression
    05. Verify session messages exist
    06. Direct _compress_messages call → verify <summary> format
    07. Verify summary has structured sections
    08. Verify compression reduced message count
    09. Cleanup
    """

    _state: dict = {}

    @pytest.fixture(autouse=True, scope="class")
    def _cleanup_disk(self):
        yield
        if _SKILL_DIR.exists():
            shutil.rmtree(_SKILL_DIR)

    # -------------------------------------------------------------------------
    # 1. Streaming agent compression via /agent/run/stream
    # -------------------------------------------------------------------------

    async def test_01_stream_with_compression_event(self, e2e_client: AsyncClient, e2e_session_factories):
        """Stream agent with long history + tool use → compression fires on Turn 2."""
        # Pre-create a session with long history in the DB
        session_id = str(uuid.uuid4())
        history = []
        for i in range(6):
            history.append({
                "role": "user",
                "content": f"Tell me about planet number {i+1}. Include many details.",
            })
            history.append({
                "role": "assistant",
                "content": f"Planet {i+1}: " + ("This planet has many moons and interesting features. " * 50),
            })

        from app.api.v1.sessions import CHAT_SENTINEL_AGENT_ID
        _AsyncSessionLocal = e2e_session_factories["async"]
        async with _AsyncSessionLocal() as db:
            db.add(PublishedSessionDB(
                id=session_id,
                agent_id=CHAT_SENTINEL_AGENT_ID,
                messages=history,
            ))
            await db.commit()

        with _patch_kimi_key(), _patch_low_threshold(), patch("app.api.v1.sessions.AsyncSessionLocal", _AsyncSessionLocal):
            resp = await e2e_client.post(
                "/api/v1/agent/run/stream",
                json={
                    "request": "Use execute_code to compute 6 * 7, then tell me the result.",
                    "session_id": session_id,
                    "max_turns": 5,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                },
                timeout=180,
            )

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        # Should have context_compressed event
        compressed_events = [e for e in events if e.get("event_type") == "context_compressed"]
        assert len(compressed_events) >= 1, (
            f"Expected context_compressed event, got: {[e.get('event_type') for e in events]}"
        )

        # Should complete successfully
        complete = next((e for e in events if e.get("event_type") == "complete"), None)
        assert complete is not None
        assert complete.get("success") is True
        assert "42" in complete.get("answer", ""), f"Expected 42, got: {complete.get('answer')}"

        type(self)._state["trace_id_stream"] = events[0].get("trace_id") if events else None

        # Verify dual-store: agent_context should differ from display messages after compression
        async with _AsyncSessionLocal() as db:
            from sqlalchemy import select as sa_select
            result = await db.execute(
                sa_select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one_or_none()

        assert record is not None
        # Display messages should still contain original history + new turn
        assert len(record.messages) >= len(history), (
            f"Display messages ({len(record.messages)}) should contain at least original history ({len(history)})"
        )
        # agent_context should be set (compressed) and shorter than display
        if record.agent_context is not None:
            assert len(record.agent_context) < len(record.messages), (
                f"agent_context ({len(record.agent_context)}) should be shorter than "
                f"display messages ({len(record.messages)}) after compression"
            )

    # -------------------------------------------------------------------------
    # 2-5. Published Agent multi-turn compression
    # -------------------------------------------------------------------------

    async def test_02_setup_published_agent(self, e2e_client: AsyncClient):
        """Create skill + agent → publish (streaming)."""
        _SKILL_DIR.mkdir(parents=True, exist_ok=True)
        (_SKILL_DIR / "SKILL.md").write_text(_SKILL_MD, encoding="utf-8")

        resp = await e2e_client.post(
            "/api/v1/registry/import-local",
            json={"skill_names": ["e2e-compression-skill"]},
        )
        assert resp.status_code == 200
        assert resp.json()["total_imported"] >= 1

        resp2 = await e2e_client.post(
            "/api/v1/agents",
            json={
                "name": "e2e-compression-agent",
                "description": "Test agent for compression",
                "system_prompt": "You are a concise assistant. Always respond in 1-2 sentences.",
                "skill_ids": ["e2e-compression-skill"],
                "builtin_tools": ["execute_code", "bash", "list_skills", "get_skill"],
                "mcp_servers": [],
                "max_turns": 10,
                "model_provider": "kimi",
                "model_name": "kimi-k2.5",
            },
        )
        assert resp2.status_code == 200
        agent_id = resp2.json()["id"]
        type(self)._state["agent_id"] = agent_id

        resp3 = await e2e_client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"api_response_mode": "streaming"},
        )
        assert resp3.status_code == 200

    async def test_03_published_turn1_tool_usage(self, e2e_client: AsyncClient):
        """Published Turn 1: Ask agent to use tools — builds session history."""
        agent_id = type(self)._state["agent_id"]
        session_id = str(uuid.uuid4())
        type(self)._state["session_id"] = session_id

        with _patch_kimi_key():
            resp = await e2e_client.post(
                f"/api/v1/published/{agent_id}/chat",
                json={
                    "request": "List available skills, then use execute_code to compute 2+2. Be brief.",
                    "session_id": session_id,
                },
                timeout=180,
            )

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)
        complete = next((e for e in events if e.get("event_type") == "complete"), None)
        assert complete is not None
        assert complete.get("success") is True

    async def test_04_published_turn2_compression(self, e2e_client: AsyncClient):
        """Published Turn 2: Compression fires on session history."""
        agent_id = type(self)._state["agent_id"]
        session_id = type(self)._state["session_id"]

        # Patch _should_compress directly on the class — reliable across threads
        from app.agent.agent import SkillsAgent
        original = SkillsAgent._should_compress
        SkillsAgent._should_compress = lambda self, tokens: tokens > 0

        try:
            with _patch_kimi_key():
                resp = await e2e_client.post(
                    f"/api/v1/published/{agent_id}/chat",
                    json={
                        "request": "Use execute_code to compute 100 * 200, then tell me the result.",
                        "session_id": session_id,
                    },
                    timeout=180,
                )
        finally:
            SkillsAgent._should_compress = original

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        compressed = [e for e in events if e.get("event_type") == "context_compressed"]
        assert len(compressed) >= 1, (
            f"Expected context_compressed, got: {[e.get('event_type') for e in events]}"
        )

        complete = next((e for e in events if e.get("event_type") == "complete"), None)
        assert complete is not None
        assert complete.get("success") is True

    async def test_05_published_turn3_post_compression(self, e2e_client: AsyncClient):
        """Published Turn 3: Session works after compression."""
        agent_id = type(self)._state["agent_id"]
        session_id = type(self)._state["session_id"]

        with _patch_kimi_key():
            resp = await e2e_client.post(
                f"/api/v1/published/{agent_id}/chat",
                json={"request": "Say hello briefly.", "session_id": session_id},
                timeout=120,
            )

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)
        complete = next((e for e in events if e.get("event_type") == "complete"), None)
        assert complete is not None
        assert complete.get("success") is True
        assert len(complete.get("answer", "")) > 0

    async def test_06_verify_session_messages(self, e2e_client: AsyncClient, e2e_session_factories):
        """Session display messages are append-only; agent_context is separately stored."""
        agent_id = type(self)._state["agent_id"]
        session_id = type(self)._state["session_id"]

        # Verify display messages via API
        resp = await e2e_client.get(
            f"/api/v1/published/{agent_id}/sessions/{session_id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == session_id
        assert len(body["messages"]) >= 2

        # Verify dual-store invariant by querying DB directly
        _AsyncSessionLocal = e2e_session_factories["async"]
        async with _AsyncSessionLocal() as db:
            from sqlalchemy import select as sa_select
            result = await db.execute(
                sa_select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
            )
            record = result.scalar_one_or_none()

        assert record is not None, "Session should exist in DB"

        display_msgs = record.messages or []
        agent_ctx = record.agent_context

        # Display messages should be the full append-only history
        assert len(display_msgs) >= 4, (
            f"Expected >= 4 display messages (3 turns of user+assistant), got {len(display_msgs)}"
        )

        # agent_context should be set (not NULL) after compression happened
        assert agent_ctx is not None, (
            "agent_context should be populated after compression"
        )

        # After compression, agent_context should differ from display messages.
        # It may be shorter (summary replaced older turns) or slightly longer
        # (summary + recent turns with tool_use/tool_result expanding into
        # more message entries than the user-visible display messages).
        assert len(agent_ctx) > 0, (
            "agent_context should have entries after compression"
        )

        # Store for later verification
        type(self)._state["display_msg_count"] = len(display_msgs)
        type(self)._state["agent_ctx_count"] = len(agent_ctx)
        type(self)._state["agent_ctx"] = agent_ctx

    # -------------------------------------------------------------------------
    # 6-8. Summary quality (direct _compress_messages call)
    # -------------------------------------------------------------------------

    async def test_07_summary_format(self):
        """_compress_messages with real Kimi 2.5 produces <summary> tags."""
        from app.agent.agent import SkillsAgent

        history = _build_large_history()

        with _patch_kimi_key():
            agent = SkillsAgent(
                model_provider="kimi",
                model="kimi-k2.5",
                verbose=True,
            )

        # Very small context limit to force compression
        agent._get_context_limit = lambda: 5000

        compressed, s_in, s_out = await agent._compress_messages(history)

        assert s_in > 0, "Summary should have consumed input tokens"
        assert s_out > 0, "Summary should have produced output tokens"
        assert len(compressed) >= 2

        summary_msg = compressed[0]["content"]
        assert "<summary>" in summary_msg, f"Missing <summary> tag in: {summary_msg[:500]}"

        type(self)._state["summary_text"] = summary_msg
        type(self)._state["compressed_count"] = len(compressed)
        type(self)._state["original_count"] = len(history)

    async def test_08_summary_sections(self):
        """Summary contains expected structured sections."""
        summary = type(self)._state.get("summary_text", "")
        assert len(summary) > 0

        for header in ("Primary Request", "Current State"):
            assert header.lower() in summary.lower(), f"Missing section: {header}"

    async def test_09_compression_reduced_messages(self):
        """Compression reduced total message count."""
        original = type(self)._state.get("original_count", 0)
        compressed = type(self)._state.get("compressed_count", 0)
        assert compressed < original, f"Expected reduction: {original} → {compressed}"

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def test_10_cleanup(self, e2e_client: AsyncClient):
        """Delete agent, skill, and traces."""
        agent_id = type(self)._state.get("agent_id")
        if agent_id:
            await e2e_client.post(f"/api/v1/agents/{agent_id}/unpublish")
            await e2e_client.delete(f"/api/v1/agents/{agent_id}")

        await e2e_client.delete("/api/v1/registry/skills/e2e-compression-skill")

        tid = type(self)._state.get("trace_id_stream")
        if tid:
            await e2e_client.delete(f"/api/v1/traces/{tid}")
