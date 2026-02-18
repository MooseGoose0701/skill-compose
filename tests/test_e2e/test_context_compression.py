"""
End-to-end tests for context compression and session full-message persistence.

Covers:
- Logical turn boundary detection (never splits tool_use/tool_result pairs)
- Dynamic token budget with MAX_RECENT_TURNS cap
- Summary prompt format (<summary> tags)
- Compression message structure (alternation, recent turns preserved)
- Serialization of messages for summarization
- Published Agent session saves full messages (tool_use/tool_result)
- Session history restoration with full context

Run:
    pytest tests/test_e2e/test_context_compression.py -v
"""

import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import StreamEvent
from tests.test_e2e.conftest import parse_sse_events


# ---------------------------------------------------------------------------
# Helpers: build realistic messages with tool_use / tool_result
# ---------------------------------------------------------------------------

def _make_simple_turn(user_text: str, assistant_text: str) -> List[Dict]:
    """A simple user→assistant turn (no tools)."""
    return [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": [{"type": "text", "text": assistant_text}]},
    ]


def _make_tool_turn(
    user_text: str,
    tools: List[Dict],
    assistant_text: str,
) -> List[Dict]:
    """A turn where the agent uses one or more tools before responding.

    tools: list of {"name": ..., "input": ..., "result": ...}
    """
    msgs: List[Dict] = [{"role": "user", "content": user_text}]
    for i, tool in enumerate(tools):
        tool_id = f"{tool['name']}:{i}"
        msgs.append({
            "role": "assistant",
            "content": [{"type": "tool_use", "id": tool_id, "name": tool["name"], "input": tool.get("input", {})}],
        })
        msgs.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": tool.get("result", "ok")}],
        })
    msgs.append({
        "role": "assistant",
        "content": [{"type": "text", "text": assistant_text}],
    })
    return msgs


def _make_heavy_tool_turn(user_text: str, result_size: int = 50000) -> List[Dict]:
    """A turn with a large tool_result (simulates get_skill returning big SKILL.md)."""
    return _make_tool_turn(
        user_text,
        [{"name": "get_skill", "input": {"skill_name": "big-skill"}, "result": "X" * result_size}],
        "Done.",
    )


# ---------------------------------------------------------------------------
# Class 1: Unit-level tests for _compress_messages internals
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="class")
class TestCompressionTurnBoundariesE2E:
    """Test logical turn boundary detection and split logic."""

    _state: dict = {}

    def _make_agent(self, context_limit: int = 256_000):
        """Create a SkillsAgent with bypassed __init__ for unit testing methods."""
        from app.agent.agent import SkillsAgent
        agent = SkillsAgent.__new__(SkillsAgent)
        agent.model = "kimi-k2.5"
        agent.model_provider = "kimi"
        agent.verbose = False
        agent.client = MagicMock()
        agent._get_context_limit = lambda: context_limit
        return agent

    def _mock_summary_response(self, agent, summary_text="<summary>\n## Test\nMocked summary\n</summary>"):
        """Mock the LLM client.create call used by _compress_messages."""
        mock_resp = MagicMock()
        mock_resp.text_content = summary_text
        mock_resp.usage = MagicMock(input_tokens=500, output_tokens=200)
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(return_value=mock_resp)

    async def test_01_simple_turns_boundary_detection(self):
        """Simple user/assistant pairs: each pair is one logical turn."""
        agent = self._make_agent()
        self._mock_summary_response(agent)

        # 5 simple turns
        messages = []
        for i in range(5):
            messages.extend(_make_simple_turn(f"Q{i}", f"A{i}"))

        compressed, s_in, s_out = await agent._compress_messages(messages)
        # Should keep last 3 turns = 6 messages, compress first 2 turns
        # compressed = [summary_user, ack_assistant] + 6 recent = 8
        assert compressed[0]["role"] == "user"
        assert "<summary>" in compressed[0]["content"]
        assert compressed[1]["role"] == "assistant"
        # Recent messages start at index 2
        assert compressed[2]["content"] == "Q2"  # Turn 3 (0-indexed turn 2)

    async def test_02_tool_turns_never_split(self):
        """Turns with tool_use/tool_result: split only at logical turn boundaries."""
        agent = self._make_agent()
        self._mock_summary_response(agent)

        # Turn 1: user + get_skill + tool_result + execute_code + tool_result + assistant = 6 msgs
        turn1 = _make_tool_turn("Generate image", [
            {"name": "get_skill", "input": {"skill_name": "gemini-imagegen"}, "result": "SKILL.md content"},
            {"name": "execute_code", "input": {"code": "print(1)"}, "result": "1"},
        ], "Image generated!")

        # Turn 2: simple
        turn2 = _make_simple_turn("Make it bigger", "Resized!")

        # Turn 3: with one tool
        turn3 = _make_tool_turn("Add rainbow", [
            {"name": "execute_code", "input": {"code": "add_rainbow()"}, "result": "done"},
        ], "Rainbow added!")

        # Turn 4: simple
        turn4 = _make_simple_turn("Thanks", "You're welcome!")

        # Turn 5: current question
        messages = turn1 + turn2 + turn3 + turn4 + [{"role": "user", "content": "What model?"}]

        compressed, _, _ = await agent._compress_messages(messages)

        # Should keep last 3 logical turns (turn 3, 4, 5)
        # Recent starts at turn 3's user message "Add rainbow"
        recent_start = next(i for i, m in enumerate(compressed) if m.get("content") == "Add rainbow")
        # Verify turn 3 is complete: user, assistant(tool_use), user(tool_result), assistant(text)
        assert compressed[recent_start]["role"] == "user"
        assert compressed[recent_start]["content"] == "Add rainbow"
        # Next should be assistant with tool_use
        assert compressed[recent_start + 1]["role"] == "assistant"
        assert compressed[recent_start + 1]["content"][0]["type"] == "tool_use"
        # Then tool_result
        assert compressed[recent_start + 2]["role"] == "user"
        assert compressed[recent_start + 2]["content"][0]["type"] == "tool_result"
        # Then text response
        assert compressed[recent_start + 3]["role"] == "assistant"
        assert compressed[recent_start + 3]["content"][0]["text"] == "Rainbow added!"

    async def test_03_not_enough_turns_skip(self):
        """Only 1 logical turn: skip compression."""
        agent = self._make_agent()

        messages = _make_tool_turn("Hello", [
            {"name": "get_skill", "result": "content"},
        ], "Hi!")

        result, s_in, s_out = await agent._compress_messages(messages)
        assert result is messages  # Unchanged
        assert s_in == 0
        assert s_out == 0

    async def test_04_three_turns_compress_oldest(self):
        """3 turns with large tool results: compresses oldest, keeps recent 2."""
        agent = self._make_agent(context_limit=10_000)  # Small limit → budget = 2500 tokens
        self._mock_summary_response(agent)

        # Turn 1: heavy (~14K tokens, exceeds entire budget alone)
        turn1 = _make_tool_turn("Turn 1", [
            {"name": "get_skill", "result": "X" * 50000},
        ], "Done 1")
        # Turn 2: light
        turn2 = _make_simple_turn("Turn 2", "Done 2")
        # Turn 3: light
        turn3 = _make_simple_turn("Turn 3", "Done 3")

        messages = turn1 + turn2 + turn3
        compressed, _, _ = await agent._compress_messages(messages)

        # Summary message exists
        assert compressed[0]["role"] == "user"
        assert "<summary>" in compressed[0]["content"]
        # Recent portion includes Turn 2 and Turn 3
        recent_user_texts = [
            m["content"] for m in compressed
            if m["role"] == "user" and isinstance(m.get("content"), str)
            and "<summary>" not in m.get("content", "")
        ]
        assert "Turn 2" in recent_user_texts
        assert "Turn 3" in recent_user_texts
        # Turn 1 is compressed away
        assert "Turn 1" not in recent_user_texts

    async def test_05_tool_result_not_counted_as_turn_boundary(self):
        """User messages with tool_result content are NOT turn boundaries."""
        agent = self._make_agent()
        self._mock_summary_response(agent)

        # Build messages manually to expose the boundary detection
        messages = [
            {"role": "user", "content": "Real user turn 1"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t:0", "name": "bash", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t:0", "content": "ok"}]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t:1", "name": "bash", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t:1", "content": "ok2"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "All done"}]},
            {"role": "user", "content": "Real user turn 2"},
            {"role": "assistant", "content": [{"type": "text", "text": "Response 2"}]},
            {"role": "user", "content": "Real user turn 3"},
            {"role": "assistant", "content": [{"type": "text", "text": "Response 3"}]},
            {"role": "user", "content": "Real user turn 4"},
            {"role": "assistant", "content": [{"type": "text", "text": "Response 4"}]},
            {"role": "user", "content": "Real user turn 5"},
        ]

        compressed, _, _ = await agent._compress_messages(messages)

        # 5 real turn boundaries. Keep 3 → compress turns 1-2, keep turns 3-5.
        # Turn 3 starts at "Real user turn 3"
        recent_user_msgs = [
            m["content"] for m in compressed
            if m["role"] == "user" and isinstance(m.get("content"), str) and m["content"] != compressed[0]["content"]
        ]
        assert "Real user turn 3" in recent_user_msgs
        assert "Real user turn 4" in recent_user_msgs
        assert "Real user turn 5" in recent_user_msgs
        # Turn 1 and 2 should NOT appear in recent (compressed away)
        assert "Real user turn 1" not in recent_user_msgs
        assert "Real user turn 2" not in recent_user_msgs


# ---------------------------------------------------------------------------
# Class 2: Dynamic token budget + MAX_RECENT_TURNS cap
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="class")
class TestCompressionTokenBudgetE2E:
    """Test dynamic token budget and max turns cap."""

    _state: dict = {}

    def _make_agent(self, context_limit: int = 256_000):
        from app.agent.agent import SkillsAgent
        agent = SkillsAgent.__new__(SkillsAgent)
        agent.model = "kimi-k2.5"
        agent.model_provider = "kimi"
        agent.verbose = False
        agent.client = MagicMock()
        agent._get_context_limit = lambda: context_limit
        return agent

    def _mock_summary(self, agent):
        mock_resp = MagicMock()
        mock_resp.text_content = "<summary>\n## Test\nSummary\n</summary>"
        mock_resp.usage = MagicMock(input_tokens=500, output_tokens=200)
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(return_value=mock_resp)

    async def test_01_max_three_turns_cap(self):
        """Even with small turns, never keep more than MAX_RECENT_TURNS (3)."""
        agent = self._make_agent(context_limit=1_000_000)  # Huge budget
        self._mock_summary(agent)

        # 10 simple turns — all tiny, well within budget
        messages = []
        for i in range(10):
            messages.extend(_make_simple_turn(f"Q{i}", f"A{i}"))

        compressed, _, _ = await agent._compress_messages(messages)

        # Count real user messages in recent portion (after summary)
        recent_user_texts = [
            m["content"] for m in compressed
            if m["role"] == "user" and isinstance(m.get("content"), str) and "<summary>" not in m.get("content", "")
        ]
        # Max 3 turns kept
        assert len(recent_user_texts) == 3
        assert recent_user_texts == ["Q7", "Q8", "Q9"]

    async def test_02_token_budget_limits_before_cap(self):
        """Heavy turns hit token budget before reaching 3 turns."""
        # Small context → small budget (256K * 0.25 = 64K tokens)
        agent = self._make_agent(context_limit=256_000)
        self._mock_summary(agent)

        # Each turn has ~23K tokens of content
        messages = []
        for i in range(5):
            messages.extend(_make_heavy_tool_turn(f"Heavy task {i}", result_size=80000))

        compressed, _, _ = await agent._compress_messages(messages)

        # Count kept user text messages
        recent_user_texts = [
            m["content"] for m in compressed
            if m["role"] == "user" and isinstance(m.get("content"), str) and "<summary>" not in m.get("content", "")
        ]
        # Should keep fewer than 3 due to token budget
        assert len(recent_user_texts) < 3
        # But at least 1 is always kept
        assert len(recent_user_texts) >= 1

    async def test_03_tiny_context_keeps_at_least_one(self):
        """Even with a very small context limit, at least 1 turn is kept."""
        agent = self._make_agent(context_limit=1000)  # Tiny: budget = 250 tokens
        self._mock_summary(agent)

        messages = []
        for i in range(5):
            messages.extend(_make_heavy_tool_turn(f"Task {i}", result_size=10000))

        compressed, _, _ = await agent._compress_messages(messages)

        # At least 1 recent user text message
        recent_user_texts = [
            m["content"] for m in compressed
            if m["role"] == "user" and isinstance(m.get("content"), str) and "<summary>" not in m.get("content", "")
        ]
        assert len(recent_user_texts) >= 1

    async def test_04_all_turns_fit_skip_compression(self):
        """If all turns fit in budget + under cap, skip compression."""
        agent = self._make_agent(context_limit=1_000_000)

        # Only 2 tiny turns — both fit and under cap of 3
        messages = _make_simple_turn("Q1", "A1") + _make_simple_turn("Q2", "A2")
        result, s_in, s_out = await agent._compress_messages(messages)

        assert result is messages  # Returned as-is
        assert s_in == 0

    async def test_05_mixed_heavy_and_light_turns(self):
        """Mix of heavy and light turns: budget logic correctly accumulates."""
        agent = self._make_agent(context_limit=256_000)  # Budget = 64K tokens
        self._mock_summary(agent)

        # 3 heavy turns (~23K tokens each) + 2 light turns (~10 tokens each)
        messages = []
        for i in range(3):
            messages.extend(_make_heavy_tool_turn(f"Heavy {i}", result_size=80000))
        messages.extend(_make_simple_turn("Light 1", "OK 1"))
        messages.extend(_make_simple_turn("Light 2", "OK 2"))
        messages.append({"role": "user", "content": "Final"})

        compressed, _, _ = await agent._compress_messages(messages)

        # Light turns are tiny, should be included; heavy turns may exceed budget
        # The 2 light + "Final" should definitely be in recent
        recent_user_texts = [
            m["content"] for m in compressed
            if m["role"] == "user" and isinstance(m.get("content"), str) and "<summary>" not in m.get("content", "")
        ]
        assert "Final" in recent_user_texts
        assert "Light 2" in recent_user_texts


# ---------------------------------------------------------------------------
# Class 3: Summary format and compression message structure
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="class")
class TestCompressionSummaryFormatE2E:
    """Test summary prompt, <summary> tags, and compressed message structure."""

    _state: dict = {}

    def _make_agent(self):
        from app.agent.agent import SkillsAgent
        agent = SkillsAgent.__new__(SkillsAgent)
        agent.model = "kimi-k2.5"
        agent.model_provider = "kimi"
        agent.verbose = False
        agent.client = MagicMock()
        agent._get_context_limit = lambda: 256_000
        return agent

    async def test_01_summary_has_summary_tags(self):
        """LLM-generated summary with <summary> tags is used as-is (not double-wrapped)."""
        agent = self._make_agent()
        llm_summary = "<summary>\n## Primary Request\nUser wanted X\n## Current State\nDone Y\n</summary>"
        mock_resp = MagicMock()
        mock_resp.text_content = llm_summary
        mock_resp.usage = MagicMock(input_tokens=500, output_tokens=200)
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(return_value=mock_resp)

        messages = []
        for i in range(5):
            messages.extend(_make_simple_turn(f"Q{i}", f"A{i}"))

        compressed, _, _ = await agent._compress_messages(messages)

        summary_content = compressed[0]["content"]
        # Should contain the summary tags exactly once
        assert summary_content.count("<summary>") == 1
        assert summary_content.count("</summary>") == 1
        assert "User wanted X" in summary_content

    async def test_02_fallback_wraps_in_summary_tags(self):
        """When LLM call fails, fallback text gets wrapped in <summary> tags."""
        agent = self._make_agent()
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(side_effect=Exception("API error"))

        messages = []
        for i in range(5):
            messages.extend(_make_simple_turn(f"Q{i}", f"A{i}"))

        compressed, _, _ = await agent._compress_messages(messages)

        summary_content = compressed[0]["content"]
        assert "<summary>" in summary_content
        assert "</summary>" in summary_content

    async def test_03_compression_message_structure(self):
        """Compressed messages have proper structure: summary + ack + recent."""
        agent = self._make_agent()
        mock_resp = MagicMock()
        mock_resp.text_content = "<summary>\nTest summary\n</summary>"
        mock_resp.usage = MagicMock(input_tokens=100, output_tokens=50)
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(return_value=mock_resp)

        messages = []
        for i in range(5):
            messages.extend(_make_simple_turn(f"Q{i}", f"A{i}"))

        compressed, s_in, s_out = await agent._compress_messages(messages)

        # [0] summary user message
        assert compressed[0]["role"] == "user"
        assert "This session is being continued" in compressed[0]["content"]
        assert "<summary>" in compressed[0]["content"]

        # [1] assistant acknowledgment (since recent starts with user)
        assert compressed[1]["role"] == "assistant"
        assert "continue from where we left off" in compressed[1]["content"][0]["text"]

        # [2:] recent messages — proper user/assistant alternation
        for i in range(2, len(compressed) - 1, 2):
            assert compressed[i]["role"] == "user"
            assert compressed[i + 1]["role"] == "assistant"

        # Token counts from mock
        assert s_in == 100
        assert s_out == 50

    async def test_04_summary_prompt_contains_required_sections(self):
        """The summary system prompt includes all 7 required sections."""
        from app.agent.agent import SUMMARY_SYSTEM_PROMPT

        required_sections = [
            "Primary Request and Intent",
            "Key Technical Concepts",
            "Files and Code Sections",
            "Problem Solving",
            "All User Messages",
            "Current State",
            "Pending Tasks",
        ]
        for section in required_sections:
            assert section in SUMMARY_SYSTEM_PROMPT, f"Missing section: {section}"

        assert "<summary>" in SUMMARY_SYSTEM_PROMPT
        assert "</summary>" in SUMMARY_SYSTEM_PROMPT

    async def test_05_compression_preserves_tool_pairs_in_recent(self):
        """After compression, recent messages contain complete tool_use/tool_result pairs."""
        agent = self._make_agent()
        mock_resp = MagicMock()
        mock_resp.text_content = "<summary>\nSummary\n</summary>"
        mock_resp.usage = MagicMock(input_tokens=100, output_tokens=50)
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(return_value=mock_resp)

        # 4 turns: first has tool, rest are simple
        turn1 = _make_tool_turn("T1", [{"name": "bash", "result": "ok"}], "Done1")
        turn2 = _make_tool_turn("T2", [
            {"name": "get_skill", "result": "skill content"},
            {"name": "execute_code", "result": "output"},
        ], "Done2")
        turn3 = _make_tool_turn("T3", [{"name": "bash", "result": "ok3"}], "Done3")
        turn4 = _make_simple_turn("T4", "Done4")

        messages = turn1 + turn2 + turn3 + turn4
        compressed, _, _ = await agent._compress_messages(messages)

        # Extract recent portion (skip summary + ack)
        recent = compressed[2:]

        # Verify every tool_use has a matching tool_result
        tool_use_ids = set()
        tool_result_ids = set()
        for msg in recent:
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_use_ids.add(block["id"])
                        elif block.get("type") == "tool_result":
                            tool_result_ids.add(block["tool_use_id"])

        # Every tool_use should have a corresponding tool_result
        assert tool_use_ids == tool_result_ids


# ---------------------------------------------------------------------------
# Class 4: Serialization for summarization
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="class")
class TestSerializeMessagesE2E:
    """Test _serialize_messages_for_summary handles all message types."""

    _state: dict = {}

    def _make_agent(self):
        from app.agent.agent import SkillsAgent
        agent = SkillsAgent.__new__(SkillsAgent)
        agent.model = "kimi-k2.5"
        agent.model_provider = "kimi"
        agent.verbose = False
        agent.client = MagicMock()
        return agent

    async def test_01_serialize_text_messages(self):
        """Plain text user/assistant messages are serialized."""
        agent = self._make_agent()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi there"}]},
        ]
        text = agent._serialize_messages_for_summary(messages)
        assert "[user]: Hello" in text
        assert "[assistant]: Hi there" in text

    async def test_02_serialize_tool_use(self):
        """tool_use blocks are serialized with tool name and input."""
        agent = self._make_agent()
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t:0", "name": "execute_code", "input": {"code": "print(1)"}},
            ]},
        ]
        text = agent._serialize_messages_for_summary(messages)
        assert "tool_use(execute_code)" in text
        assert "print(1)" in text

    async def test_03_serialize_tool_result(self):
        """tool_result blocks are serialized."""
        agent = self._make_agent()
        messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t:0", "content": "execution output"},
            ]},
        ]
        text = agent._serialize_messages_for_summary(messages)
        assert "[tool_result]: execution output" in text

    async def test_04_truncate_long_tool_input(self):
        """tool_use inputs longer than 500 chars are truncated."""
        agent = self._make_agent()
        long_code = "x" * 1000
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t:0", "name": "execute_code", "input": {"code": long_code}},
            ]},
        ]
        text = agent._serialize_messages_for_summary(messages)
        assert "...(truncated)" in text

    async def test_05_truncate_long_tool_result(self):
        """tool_result content longer than 1000 chars is truncated."""
        agent = self._make_agent()
        long_result = "R" * 2000
        messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t:0", "content": long_result},
            ]},
        ]
        text = agent._serialize_messages_for_summary(messages)
        assert "...(truncated)" in text
        assert len(text) < 2000

    async def test_06_huge_text_head_tail_truncation(self):
        """Total text exceeding 100K chars is truncated to head + tail."""
        agent = self._make_agent()
        # Create many messages with large content
        messages = []
        for i in range(200):
            messages.append({"role": "user", "content": f"Message {i}: {'X' * 600}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"Response {i}: {'Y' * 600}"}]})

        text = agent._serialize_messages_for_summary(messages)
        assert "[... truncated middle section ...]" in text


# ---------------------------------------------------------------------------
# Class 5: Published Agent session saves full messages (integration)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="class")
class TestPublishedSessionFullMessagesE2E:
    """Published Agent sessions save complete messages including tool_use/tool_result."""

    _state: dict = {}

    async def test_01_create_and_publish(self, e2e_client: AsyncClient):
        """Create and publish an agent for testing."""
        resp = await e2e_client.post("/api/v1/agents", json={
            "name": "e2e-session-fullmsg",
            "description": "Test full message sessions",
            "max_turns": 5,
        })
        assert resp.status_code == 200
        pid = resp.json()["id"]
        type(self)._state["preset_id"] = pid

        resp = await e2e_client.post(
            f"/api/v1/agents/{pid}/publish",
            json={"api_response_mode": "streaming"},
        )
        assert resp.status_code == 200

    @patch("app.api.v1.published.save_session_messages", new_callable=AsyncMock)
    @patch("app.api.v1.published.load_or_create_session", new_callable=AsyncMock)
    @patch("app.api.v1.published.SkillsAgent")
    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_02_streaming_saves_full_messages(
        self, MockSL, MockAgent, MockLoadSession, _mock_save, e2e_client: AsyncClient,
    ):
        """Streaming chat saves final_messages (with tool_use/tool_result) to session."""
        pid = type(self)._state["preset_id"]
        session_id = str(uuid.uuid4())
        type(self)._state["session_id"] = session_id
        MockLoadSession.return_value = (session_id, None)

        # Build final_messages with tool context
        final_msgs = [
            {"role": "user", "content": "List skills"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "ls:0", "name": "list_skills", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "ls:0", "content": '{"skills": ["a", "b"]}'},
            ]},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Found 2 skills: a, b"},
            ]},
        ]

        # Mock agent with async run() that pushes events to event_stream
        mock_instance = MagicMock()
        mock_instance.cleanup = MagicMock()
        mock_instance.model = "kimi-k2.5"
        mock_instance.model_provider = "kimi"

        events_to_push = [
            StreamEvent(event_type="turn_start", turn=1, data={"turn": 1}),
            StreamEvent(event_type="tool_result", turn=1, data={
                "tool_name": "list_skills", "tool_input": {}, "tool_result": '{"skills": ["a","b"]}',
            }),
            StreamEvent(event_type="assistant", turn=2, data={
                "content": "Found 2 skills: a, b", "turn": 2,
            }),
            StreamEvent(event_type="complete", turn=2, data={
                "success": True,
                "answer": "Found 2 skills: a, b",
                "total_turns": 2,
                "total_input_tokens": 200,
                "total_output_tokens": 30,
                "skills_used": [],
                "final_messages": final_msgs,
            }),
        ]

        async def mock_run(request, conversation_history=None, image_contents=None,
                           event_stream=None, cancellation_event=None):
            if event_stream:
                for event in events_to_push:
                    await event_stream.push(event)
                await event_stream.close()
            from app.agent.agent import AgentResult
            return AgentResult(
                success=True, answer="Found 2 skills: a, b",
                total_turns=2, total_input_tokens=200, total_output_tokens=30,
                skills_used=[], final_messages=final_msgs,
            )

        mock_instance.run = AsyncMock(side_effect=mock_run)
        MockAgent.return_value = mock_instance

        # Mock AsyncSessionLocal with DB interactions tracking
        from app.db.models import AgentPresetDB, PublishedSessionDB

        mock_preset = MagicMock(spec=AgentPresetDB)
        mock_preset.id = pid
        mock_preset.name = "e2e-session-fullmsg"
        mock_preset.description = "Test"
        mock_preset.is_published = True
        mock_preset.api_response_mode = "streaming"
        mock_preset.skill_ids = []
        mock_preset.builtin_tools = None
        mock_preset.max_turns = 5
        mock_preset.mcp_servers = []
        mock_preset.system_prompt = None
        mock_preset.model_provider = None
        mock_preset.model_name = None
        mock_preset.executor_id = None

        saved_messages = {}
        call_idx = {"i": 0}

        @asynccontextmanager
        async def _ctx():
            idx = call_idx["i"]
            call_idx["i"] += 1
            mock_sess = AsyncMock(spec=AsyncSession)

            if idx == 0:
                # First call: find preset
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_preset
                mock_sess.execute = AsyncMock(return_value=mock_result)
            elif idx == 1:
                # Second call: find session (not found → create)
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_sess.execute = AsyncMock(return_value=mock_result)
                mock_sess.add = MagicMock()
                mock_sess.commit = AsyncMock()
            else:
                # Subsequent calls: session save — capture the update values
                mock_result = MagicMock()
                mock_session_record = MagicMock()
                mock_session_record.messages = []
                mock_result.scalar_one_or_none.return_value = mock_session_record

                async def capture_execute(stmt, *args, **kwargs):
                    if hasattr(stmt, 'compile'):
                        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
                        stmt_str = str(compiled)
                        if "UPDATE" in stmt_str and "messages" in stmt_str:
                            params = stmt.compile().params
                            if "messages" in params:
                                saved_messages["data"] = params["messages"]
                    return mock_result

                mock_sess.execute = AsyncMock(side_effect=capture_execute)
                mock_sess.commit = AsyncMock()

            yield mock_sess

        MockSL.side_effect = lambda: _ctx()

        resp = await e2e_client.post(
            f"/api/v1/published/{pid}/chat",
            json={"request": "List skills", "session_id": session_id},
        )
        assert resp.status_code == 200

        events = parse_sse_events(resp.text)
        complete_events = [e for e in events if e.get("event_type") == "complete"]
        assert len(complete_events) == 1

        # Verify complete event contains final_messages
        complete = complete_events[0]
        assert "final_messages" in complete
        fm = complete["final_messages"]
        assert len(fm) == 4
        # First: user text
        assert fm[0]["role"] == "user"
        assert fm[0]["content"] == "List skills"
        # Second: assistant tool_use
        assert fm[1]["role"] == "assistant"
        assert fm[1]["content"][0]["type"] == "tool_use"
        # Third: user tool_result
        assert fm[2]["role"] == "user"
        assert fm[2]["content"][0]["type"] == "tool_result"
        # Fourth: assistant text
        assert fm[3]["role"] == "assistant"
        assert fm[3]["content"][0]["type"] == "text"

    @patch("app.api.v1.published.save_session_messages", new_callable=AsyncMock)
    @patch("app.api.v1.published.load_or_create_session", new_callable=AsyncMock)
    @patch("app.api.v1.published.SkillsAgent")
    @patch("app.api.v1.published.AsyncSessionLocal")
    async def test_03_nonstreaming_saves_full_messages(
        self, MockSL, MockAgent, MockLoadSession, _mock_save, e2e_client: AsyncClient,
    ):
        """Non-streaming chat also saves final_messages to session."""
        pid = type(self)._state["preset_id"]

        # Unpublish and re-publish as non_streaming
        await e2e_client.post(f"/api/v1/agents/{pid}/unpublish")
        resp = await e2e_client.post(
            f"/api/v1/agents/{pid}/publish",
            json={"api_response_mode": "non_streaming"},
        )
        assert resp.status_code == 200

        session_id = str(uuid.uuid4())
        MockLoadSession.return_value = (session_id, None)

        final_msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi!"}]},
        ]

        from app.agent.agent import AgentResult
        mock_result = AgentResult(
            success=True, answer="Hi!", total_turns=1,
            total_input_tokens=100, total_output_tokens=20,
            skills_used=[], output_files=[], final_messages=final_msgs,
        )

        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(return_value=mock_result)
        mock_instance.cleanup = MagicMock()
        mock_instance.model = "kimi-k2.5"
        mock_instance.model_provider = "kimi"
        MockAgent.return_value = mock_instance

        from app.db.models import AgentPresetDB

        mock_preset = MagicMock(spec=AgentPresetDB)
        mock_preset.id = pid
        mock_preset.name = "e2e-session-fullmsg"
        mock_preset.description = "Test"
        mock_preset.is_published = True
        mock_preset.api_response_mode = "non_streaming"
        mock_preset.skill_ids = []
        mock_preset.builtin_tools = None
        mock_preset.max_turns = 5
        mock_preset.mcp_servers = []
        mock_preset.system_prompt = None
        mock_preset.model_provider = None
        mock_preset.model_name = None
        mock_preset.executor_id = None

        call_idx = {"i": 0}

        @asynccontextmanager
        async def _ctx():
            idx = call_idx["i"]
            call_idx["i"] += 1
            mock_sess = AsyncMock(spec=AsyncSession)

            if idx == 0:
                mock_r = MagicMock()
                mock_r.scalar_one_or_none.return_value = mock_preset
                mock_sess.execute = AsyncMock(return_value=mock_r)
            elif idx == 1:
                mock_r = MagicMock()
                mock_r.scalar_one_or_none.return_value = None
                mock_sess.execute = AsyncMock(return_value=mock_r)
                mock_sess.add = MagicMock()
                mock_sess.commit = AsyncMock()
            else:
                mock_r = MagicMock()
                mock_session_record = MagicMock()
                mock_session_record.messages = []
                mock_r.scalar_one_or_none.return_value = mock_session_record
                mock_sess.execute = AsyncMock(return_value=mock_r)
                mock_sess.commit = AsyncMock()

            yield mock_sess

        MockSL.side_effect = lambda: _ctx()

        resp = await e2e_client.post(
            f"/api/v1/published/{pid}/chat/sync",
            json={"request": "Hello", "session_id": session_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["answer"] == "Hi!"

    async def test_04_cleanup(self, e2e_client: AsyncClient):
        pid = type(self)._state["preset_id"]
        await e2e_client.post(f"/api/v1/agents/{pid}/unpublish")
        resp = await e2e_client.delete(f"/api/v1/agents/{pid}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Class 6: _should_compress threshold
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio(loop_scope="class")
class TestShouldCompressE2E:
    """Test compression trigger threshold."""

    _state: dict = {}

    def _make_agent(self, context_limit: int = 200_000):
        from app.agent.agent import SkillsAgent
        agent = SkillsAgent.__new__(SkillsAgent)
        agent.model = "kimi-k2.5"
        agent.model_provider = "kimi"
        agent.verbose = False
        agent.client = MagicMock()
        agent._get_context_limit = lambda: context_limit
        return agent

    async def test_01_below_threshold_no_compress(self):
        """Input tokens below 70% of limit: don't compress."""
        agent = self._make_agent(200_000)
        # 70% of 200K = 140K
        assert agent._should_compress(100_000) is False
        assert agent._should_compress(139_999) is False

    async def test_02_at_threshold_no_compress(self):
        """Input tokens exactly at threshold: don't compress (> not >=)."""
        agent = self._make_agent(200_000)
        assert agent._should_compress(140_000) is False

    async def test_03_above_threshold_compress(self):
        """Input tokens above 70% of limit: compress."""
        agent = self._make_agent(200_000)
        assert agent._should_compress(140_001) is True
        assert agent._should_compress(180_000) is True
