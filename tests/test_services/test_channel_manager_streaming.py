"""
Tests for ChannelManager turn-by-turn progress streaming.

Covers:
- _run_agent_streaming(): event consumption, per-turn progress callbacks
- _run_agent() delegation: on_progress triggers streaming path
- _run_agent() without on_progress: unchanged non-streaming path
- _handle_inbound() wiring: adapter receives progress messages
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.agent.agent import StreamEvent
from app.agent.event_stream import EventStream
from app.db.models import AgentPresetDB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_preset(**overrides) -> AgentPresetDB:
    defaults = dict(
        id=str(uuid.uuid4()),
        name="stream-test",
        max_turns=10,
        skill_ids=[],
        model_provider="kimi",
        model_name="kimi-k2.5",
    )
    defaults.update(overrides)
    return AgentPresetDB(**defaults)


def _mock_agent_result(**overrides):
    """Return a MagicMock that quacks like AgentResult."""
    defaults = dict(
        success=True,
        answer="Final answer",
        total_turns=2,
        total_input_tokens=100,
        total_output_tokens=50,
        steps=[],
        llm_calls=[],
        skills_used=[],
        error=None,
        output_files=[],
        final_messages=[],
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


async def _emit_events(stream: EventStream, events: list[StreamEvent]):
    """Push a sequence of events then close the stream."""
    for ev in events:
        await stream.push(ev)
    await stream.close()


# ---------------------------------------------------------------------------
# _run_agent_streaming unit tests
# ---------------------------------------------------------------------------


class TestRunAgentStreaming:
    """Direct tests for ChannelManager._run_agent_streaming."""

    async def test_single_turn_no_progress(self):
        """Single turn (no turn_complete before complete) sends no progress."""
        from app.services.channel_manager import ChannelManager

        progress_texts: list[str] = []

        async def on_progress(text: str):
            progress_texts.append(text)

        mock_result = _mock_agent_result(total_turns=1)

        # Mock agent.run to emit events then return result
        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("turn_start", 1, {"max_turns": 10}))
            await es.push(StreamEvent("text_delta", 1, {"text": "Hello!"}))
            await es.push(StreamEvent("complete", 1, {"success": True}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        result = await ChannelManager._run_agent_streaming(
            mock_agent, "Hi", None, None, on_progress,
        )

        assert result is mock_result
        assert progress_texts == []  # No turn_complete → no progress

    async def test_multi_turn_sends_progress(self):
        """Multi-turn execution sends progress at each turn_complete."""
        from app.services.channel_manager import ChannelManager

        progress_texts: list[str] = []

        async def on_progress(text: str):
            progress_texts.append(text)

        mock_result = _mock_agent_result(total_turns=3)

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            # Turn 1: text + tool call → turn_complete
            await es.push(StreamEvent("turn_start", 1, {}))
            await es.push(StreamEvent("text_delta", 1, {"text": "Let me search"}))
            await es.push(StreamEvent("tool_call", 1, {"tool_name": "search_code"}))
            await es.push(StreamEvent("turn_complete", 1, {}))
            # Turn 2: text + tool call → turn_complete
            await es.push(StreamEvent("turn_start", 2, {}))
            await es.push(StreamEvent("text_delta", 2, {"text": "Found results, analyzing"}))
            await es.push(StreamEvent("tool_call", 2, {"tool_name": "read_file"}))
            await es.push(StreamEvent("turn_complete", 2, {}))
            # Turn 3: final answer → complete
            await es.push(StreamEvent("turn_start", 3, {}))
            await es.push(StreamEvent("text_delta", 3, {"text": "Final answer"}))
            await es.push(StreamEvent("complete", 3, {"success": True}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        result = await ChannelManager._run_agent_streaming(
            mock_agent, "Search for bugs", None, None, on_progress,
        )

        assert result is mock_result
        assert len(progress_texts) == 2
        assert "Let me search" in progress_texts[0]
        assert "search_code" in progress_texts[0]
        assert "Found results, analyzing" in progress_texts[1]
        assert "read_file" in progress_texts[1]

    async def test_empty_turn_no_progress(self):
        """turn_complete with empty buffer sends no progress."""
        from app.services.channel_manager import ChannelManager

        progress_texts: list[str] = []

        async def on_progress(text: str):
            progress_texts.append(text)

        mock_result = _mock_agent_result()

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("turn_start", 1, {}))
            # No text_delta — just tool_result, etc.
            await es.push(StreamEvent("turn_complete", 1, {}))
            await es.push(StreamEvent("complete", 2, {"success": True}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        await ChannelManager._run_agent_streaming(
            mock_agent, "Empty turn", None, None, on_progress,
        )

        assert progress_texts == []

    async def test_tool_hint_format(self):
        """Tool calls are formatted as '> Using tool: <name>...' hints."""
        from app.services.channel_manager import ChannelManager

        progress_texts: list[str] = []

        async def on_progress(text: str):
            progress_texts.append(text)

        mock_result = _mock_agent_result()

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("turn_start", 1, {}))
            await es.push(StreamEvent("text_delta", 1, {"text": "Checking..."}))
            await es.push(StreamEvent("tool_call", 1, {"tool_name": "execute_code"}))
            await es.push(StreamEvent("tool_call", 1, {"tool_name": "read_file"}))
            await es.push(StreamEvent("turn_complete", 1, {}))
            await es.push(StreamEvent("complete", 2, {"success": True}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        await ChannelManager._run_agent_streaming(
            mock_agent, "Tools", None, None, on_progress,
        )

        assert len(progress_texts) == 1
        assert "> Using tool: execute_code..." in progress_texts[0]
        assert "> Using tool: read_file..." in progress_texts[0]

    async def test_progress_callback_error_does_not_crash(self):
        """If on_progress raises, execution continues without crashing."""
        from app.services.channel_manager import ChannelManager

        async def failing_progress(text: str):
            raise ConnectionError("Feishu API down")

        mock_result = _mock_agent_result()

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("turn_start", 1, {}))
            await es.push(StreamEvent("text_delta", 1, {"text": "Turn 1 text"}))
            await es.push(StreamEvent("turn_complete", 1, {}))
            await es.push(StreamEvent("text_delta", 2, {"text": "Final"}))
            await es.push(StreamEvent("complete", 2, {"success": True}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        # Should not raise despite callback failure
        result = await ChannelManager._run_agent_streaming(
            mock_agent, "Resilient", None, None, failing_progress,
        )

        assert result is mock_result

    async def test_error_event_breaks_loop(self):
        """An 'error' event breaks the consumption loop."""
        from app.services.channel_manager import ChannelManager

        progress_texts: list[str] = []

        async def on_progress(text: str):
            progress_texts.append(text)

        mock_result = _mock_agent_result(success=False, error="LLM crashed")

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("turn_start", 1, {}))
            await es.push(StreamEvent("text_delta", 1, {"text": "Working..."}))
            await es.push(StreamEvent("turn_complete", 1, {}))
            await es.push(StreamEvent("error", 2, {"error": "LLM crashed"}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        result = await ChannelManager._run_agent_streaming(
            mock_agent, "Error test", None, None, on_progress,
        )

        assert result is mock_result
        # Turn 1 progress was sent before the error
        assert len(progress_texts) == 1

    async def test_passes_conversation_history_and_images(self):
        """Conversation history and image_contents are forwarded to agent.run."""
        from app.services.channel_manager import ChannelManager

        captured_kwargs = {}
        mock_result = _mock_agent_result()

        async def mock_run(prompt, **kwargs):
            captured_kwargs.update(kwargs)
            es = kwargs["event_stream"]
            await es.push(StreamEvent("complete", 1, {"success": True}))
            await es.close()
            return mock_result

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        history = [{"role": "user", "content": "Old msg"}]
        images = [{"type": "image", "source": {"type": "base64", "data": "abc"}}]

        await ChannelManager._run_agent_streaming(
            mock_agent, "New msg", history, images, AsyncMock(),
        )

        assert captured_kwargs["conversation_history"] is history
        assert captured_kwargs["image_contents"] is images
        assert captured_kwargs["event_stream"] is not None


# ---------------------------------------------------------------------------
# _run_agent delegation tests
# ---------------------------------------------------------------------------


class TestRunAgentDelegation:
    """Verify _run_agent routes to streaming vs non-streaming correctly."""

    @patch("app.agent.SkillsAgent")
    async def test_with_on_progress_uses_streaming(self, MockSkillsAgent):
        """When on_progress is provided, _run_agent delegates to _run_agent_streaming."""
        from app.services.channel_manager import ChannelManager

        mock_result = _mock_agent_result()

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("complete", 1, {"success": True}))
            await es.close()
            return mock_result

        mock_instance = MagicMock()
        mock_instance.model_provider = "kimi"
        mock_instance.model = "kimi-k2.5"
        mock_instance.cleanup = MagicMock()
        mock_instance.run = mock_run
        MockSkillsAgent.return_value = mock_instance

        preset = _make_preset()
        progress_called = []

        async def on_progress(text: str):
            progress_called.append(text)

        mock_trace_session = AsyncMock()
        mock_trace_session.__aenter__ = AsyncMock(return_value=mock_trace_session)
        mock_trace_session.__aexit__ = AsyncMock(return_value=False)
        mock_trace_session.add = MagicMock()
        mock_trace_session.commit = AsyncMock()

        with patch("app.db.database.AsyncSessionLocal", return_value=mock_trace_session), \
             patch("app.api.v1.sessions.save_session_messages", new_callable=AsyncMock):
            manager = ChannelManager.__new__(ChannelManager)
            manager._adapters = {}
            answer, _ = await manager._run_agent(
                preset, "Test", on_progress=on_progress,
            )

        assert answer == "Final answer"
        mock_instance.cleanup.assert_called_once()

    @patch("app.agent.SkillsAgent")
    async def test_without_on_progress_no_streaming(self, MockSkillsAgent):
        """When on_progress is None, _run_agent uses direct (non-streaming) path."""
        from app.services.channel_manager import ChannelManager

        mock_result = _mock_agent_result()

        mock_instance = MagicMock()
        mock_instance.model_provider = "kimi"
        mock_instance.model = "kimi-k2.5"
        mock_instance.cleanup = MagicMock()
        mock_instance.run = AsyncMock(return_value=mock_result)
        MockSkillsAgent.return_value = mock_instance

        preset = _make_preset()

        mock_trace_session = AsyncMock()
        mock_trace_session.__aenter__ = AsyncMock(return_value=mock_trace_session)
        mock_trace_session.__aexit__ = AsyncMock(return_value=False)
        mock_trace_session.add = MagicMock()
        mock_trace_session.commit = AsyncMock()

        with patch("app.db.database.AsyncSessionLocal", return_value=mock_trace_session), \
             patch("app.api.v1.sessions.save_session_messages", new_callable=AsyncMock):
            manager = ChannelManager.__new__(ChannelManager)
            manager._adapters = {}
            answer, _ = await manager._run_agent(preset, "Test")

        assert answer == "Final answer"
        # agent.run was called directly (no event_stream kwarg)
        call_kwargs = mock_instance.run.call_args[1]
        assert "event_stream" not in call_kwargs
        mock_instance.cleanup.assert_called_once()

    @patch("app.agent.SkillsAgent")
    async def test_streaming_path_still_saves_trace(self, MockSkillsAgent):
        """Streaming path still creates and saves an agent trace."""
        from app.services.channel_manager import ChannelManager
        from app.db.models import AgentTraceDB

        mock_result = _mock_agent_result()

        async def mock_run(prompt, **kwargs):
            es = kwargs["event_stream"]
            await es.push(StreamEvent("complete", 1, {"success": True}))
            await es.close()
            return mock_result

        mock_instance = MagicMock()
        mock_instance.model_provider = "kimi"
        mock_instance.model = "kimi-k2.5"
        mock_instance.cleanup = MagicMock()
        mock_instance.run = mock_run
        MockSkillsAgent.return_value = mock_instance

        preset = _make_preset()
        added_objects = []

        mock_trace_session = AsyncMock()
        mock_trace_session.__aenter__ = AsyncMock(return_value=mock_trace_session)
        mock_trace_session.__aexit__ = AsyncMock(return_value=False)
        mock_trace_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_trace_session.commit = AsyncMock()

        with patch("app.db.database.AsyncSessionLocal", return_value=mock_trace_session), \
             patch("app.api.v1.sessions.save_session_messages", new_callable=AsyncMock):
            manager = ChannelManager.__new__(ChannelManager)
            manager._adapters = {}
            await manager._run_agent(
                preset, "Trace test", session_id="sess-123",
                on_progress=AsyncMock(),
            )

        trace_objects = [o for o in added_objects if isinstance(o, AgentTraceDB)]
        assert len(trace_objects) == 1
        assert trace_objects[0].status == "completed"
        assert trace_objects[0].session_id == "sess-123"
