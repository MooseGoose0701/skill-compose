"""
Tests for agent context window compression.

Tests the compression helpers (_should_compress, _serialize_messages_for_summary,
_compress_messages) and the integration into run().
"""
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.agent.agent import (
    SkillsAgent,
    StreamEvent,
    COMPRESSION_THRESHOLD_RATIO,
    MAX_RECENT_TURNS,
)
from app.llm.models import MODEL_CONTEXT_LIMITS, DEFAULT_CONTEXT_LIMIT
from tests.mocks.mock_anthropic import (
    MockResponse,
    MockTextBlock,
    MockToolUseBlock,
    MockUsage,
    simple_text_response,
    create_mock_client,
    create_mock_llm_client,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(**kwargs) -> SkillsAgent:
    """Create a SkillsAgent with mocked externals."""
    defaults = dict(
        model="claude-sonnet-4-5-20250929",
        max_turns=5,
        verbose=False,
        log_dir="/tmp/test_logs",
        equipped_mcp_servers=[],
    )
    defaults.update(kwargs)
    mock_workspace = MagicMock()
    mock_workspace.cleanup = MagicMock()
    with patch("app.agent.agent.get_tools_for_agent", return_value=([], {}, mock_workspace)):
        agent = SkillsAgent(**defaults)
    return agent


def _build_conversation(num_pairs: int) -> list:
    """Build a fake conversation with num_pairs user/assistant turns."""
    messages = []
    for i in range(num_pairs):
        messages.append({"role": "user", "content": f"User message {i}"})
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": f"Assistant message {i}"}],
        })
    return messages


def _build_tool_conversation(num_pairs: int) -> list:
    """Build a conversation with tool calls and tool results."""
    messages = []
    for i in range(num_pairs):
        messages.append({"role": "user", "content": f"User request {i}"})
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "text", "text": f"Let me use a tool for step {i}"},
                {
                    "type": "tool_use",
                    "id": f"tool_{i}",
                    "name": "execute_code",
                    "input": {"code": f"print('step {i}')"},
                },
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": f"tool_{i}",
                    "content": f"Output of step {i}",
                }
            ],
        })
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": f"Step {i} done."}],
        })
    return messages


# ===========================================================================
# _should_compress
# ===========================================================================

class TestShouldCompress:
    def test_below_threshold(self):
        agent = _make_agent()
        # 70% of 200K = 140K — 100K should NOT trigger
        assert agent._should_compress(100_000) is False

    def test_at_threshold(self):
        agent = _make_agent()
        threshold = int(200_000 * COMPRESSION_THRESHOLD_RATIO)
        # Exactly at threshold should NOT trigger (need to exceed)
        assert agent._should_compress(threshold) is False

    def test_above_threshold(self):
        agent = _make_agent()
        threshold = int(200_000 * COMPRESSION_THRESHOLD_RATIO)
        assert agent._should_compress(threshold + 1) is True

    def test_uses_model_specific_limit(self):
        agent = _make_agent(model="claude-opus-4-6")
        threshold = int(MODEL_CONTEXT_LIMITS["claude-opus-4-6"] * COMPRESSION_THRESHOLD_RATIO)
        assert agent._should_compress(threshold + 1) is True

    def test_unknown_model_uses_default(self):
        agent = _make_agent(model="claude-unknown-model")
        threshold = int(DEFAULT_CONTEXT_LIMIT * COMPRESSION_THRESHOLD_RATIO)
        assert agent._should_compress(threshold + 1) is True
        assert agent._should_compress(threshold - 1) is False


# ===========================================================================
# _serialize_messages_for_summary
# ===========================================================================

class TestSerializeMessages:
    def test_simple_text_messages(self):
        agent = _make_agent()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = agent._serialize_messages_for_summary(messages)
        assert "[user]: Hello" in result
        assert "[assistant]: Hi there" in result

    def test_structured_content(self):
        agent = _make_agent()
        messages = [
            {"role": "assistant", "content": [
                {"type": "text", "text": "Let me help"},
                {"type": "tool_use", "name": "execute_code", "input": {"code": "x=1"}},
            ]},
        ]
        result = agent._serialize_messages_for_summary(messages)
        assert "[assistant]: Let me help" in result
        assert "tool_use(execute_code)" in result

    def test_tool_result_content(self):
        agent = _make_agent()
        messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "output data"},
            ]},
        ]
        result = agent._serialize_messages_for_summary(messages)
        assert "[tool_result]: output data" in result

    def test_truncates_long_tool_input(self):
        agent = _make_agent()
        long_input = {"code": "x" * 1000}
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "name": "execute_code", "input": long_input},
            ]},
        ]
        result = agent._serialize_messages_for_summary(messages)
        assert "...(truncated)" in result

    def test_truncates_long_tool_result(self):
        agent = _make_agent()
        messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "x" * 2000},
            ]},
        ]
        result = agent._serialize_messages_for_summary(messages)
        assert "...(truncated)" in result
        # The truncated content should be at most 1000 + len("...(truncated)")
        for part in result.split("\n\n"):
            if "[tool_result]" in part:
                assert len(part) < 1100

    def test_truncates_overall_text_at_100k(self):
        agent = _make_agent()
        # Create enough messages to exceed 100K chars
        messages = []
        for i in range(200):
            messages.append({"role": "user", "content": "x" * 600})
            messages.append({"role": "assistant", "content": "y" * 600})
        result = agent._serialize_messages_for_summary(messages)
        assert "[... truncated middle section ...]" in result
        # Result should be around 100K + marker length
        assert len(result) < 110_000


# ===========================================================================
# _compress_messages (async)
# ===========================================================================

@pytest.mark.asyncio
class TestCompressMessages:
    async def test_not_enough_messages_skips(self):
        agent = _make_agent()
        # Only 2 messages — not enough logical turns
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]},
        ]
        result, s_in, s_out = await agent._compress_messages(messages)
        assert result is messages  # unchanged
        assert s_in == 0
        assert s_out == 0

    async def test_compresses_long_conversation(self):
        agent = _make_agent()
        # Mock the summarization API call (async)
        summary_response = MockResponse(
            content=[MockTextBlock(text="Summary of conversation")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=500, output_tokens=100),
        )
        agent.client = create_mock_llm_client([summary_response])

        messages = _build_conversation(10)  # 20 messages
        compressed, s_in, s_out = await agent._compress_messages(messages)

        # Should have: 1 summary + 1 ack + recent messages
        assert len(compressed) < len(messages)
        assert compressed[0]["role"] == "user"
        assert "continued from a previous conversation" in compressed[0]["content"]
        assert s_in == 500
        assert s_out == 100

    async def test_summary_message_format(self):
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="This is the summary")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=200, output_tokens=50),
        )
        agent.client = create_mock_llm_client([summary_response])

        messages = _build_conversation(10)
        compressed, _, _ = await agent._compress_messages(messages)

        summary_msg = compressed[0]["content"]
        assert "This session is being continued" in summary_msg
        assert "This is the summary" in summary_msg
        assert "Continue with the last task" in summary_msg

    async def test_recent_messages_preserved(self):
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="Summary")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=200, output_tokens=50),
        )
        agent.client = create_mock_llm_client([summary_response])

        messages = _build_conversation(10)  # 20 messages total
        compressed, _, _ = await agent._compress_messages(messages)

        # The last few messages should be present in compressed output
        last_msg = messages[-1]
        assert any(
            m.get("content") == last_msg.get("content")
            for m in compressed
        )

    async def test_maintains_user_assistant_alternation(self):
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="Summary")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=200, output_tokens=50),
        )
        agent.client = create_mock_llm_client([summary_response])

        messages = _build_conversation(10)
        compressed, _, _ = await agent._compress_messages(messages)

        # First message should be user (summary)
        assert compressed[0]["role"] == "user"
        # Verify alternation: no two consecutive messages with same role
        for i in range(1, len(compressed)):
            assert compressed[i]["role"] != compressed[i - 1]["role"], (
                f"Messages {i-1} and {i} both have role '{compressed[i]['role']}'"
            )

    async def test_fallback_on_api_failure(self):
        agent = _make_agent()
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(side_effect=Exception("API error"))

        messages = _build_conversation(10)
        compressed, s_in, s_out = await agent._compress_messages(messages)

        # Should still return compressed messages (fallback)
        assert len(compressed) < len(messages)
        assert "continued from a previous conversation" in compressed[0]["content"]
        # No tokens consumed on failure
        assert s_in == 0
        assert s_out == 0

    async def test_tool_conversation_compression(self):
        """Test compression with tool calls and tool results."""
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="Summary with tools")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=300, output_tokens=80),
        )
        agent.client = create_mock_llm_client([summary_response])

        messages = _build_tool_conversation(8)  # 32 messages (4 per pair), 8 > MAX_RECENT_TURNS=5
        compressed, s_in, s_out = await agent._compress_messages(messages)

        assert len(compressed) < len(messages)
        assert s_in == 300

    async def test_iterative_summary_detection(self):
        """When old_messages starts with a previous summary, UPDATE prompt is used."""
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="<summary>\n## Updated\nNew summary\n</summary>")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=400, output_tokens=150),
        )
        agent.client = create_mock_llm_client([summary_response])

        # Build messages that simulate a previous compression + new turns
        previous_summary_content = (
            "This session is being continued from a previous conversation.\n\n"
            "<summary>\n## Primary Request\nUser wanted X\n</summary>\n\nContinue."
        )
        messages = [
            {"role": "user", "content": previous_summary_content},
            {"role": "assistant", "content": [{"type": "text", "text": "I understand the context. Let me continue from where we left off."}]},
        ]
        # Add enough new turns to trigger compression (>MAX_RECENT_TURNS)
        for i in range(8):
            messages.append({"role": "user", "content": f"New request {i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"New response {i}"}]})

        compressed, s_in, s_out = await agent._compress_messages(messages)

        assert len(compressed) < len(messages)
        # Verify the LLM call used the UPDATE prompt (contains "previous-summary")
        call_args = agent.client.acreate.call_args
        system_used = call_args.kwargs.get("system", "")
        assert "previous-summary" in system_used
        assert s_in == 400
        assert s_out == 150

    async def test_file_tracking_appended_to_summary(self):
        """Compression appends <read-files> and <modified-files> tags."""
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="<summary>\n## Test\nSummary\n</summary>")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=300, output_tokens=100),
        )
        agent.client = create_mock_llm_client([summary_response])

        # Build messages with file tool operations
        messages = [
            {"role": "user", "content": "Read and write files"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "r:0", "name": "read", "input": {"file_path": "/app/config.py"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "r:0", "content": "content"},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "w:0", "name": "write", "input": {"file_path": "/app/out.txt"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w:0", "content": "written"},
            ]},
            {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
        ]
        # Add more turns to trigger compression
        for i in range(8):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"A{i}"}]})

        compressed, _, _ = await agent._compress_messages(messages)
        summary = compressed[0]["content"]
        assert "<read-files>" in summary
        assert "/app/config.py" in summary
        assert "<modified-files>" in summary
        assert "/app/out.txt" in summary


# ===========================================================================
# _extract_file_operations
# ===========================================================================

class TestExtractFileOperations:
    def test_extracts_read_operations(self):
        from app.agent.agent import _extract_file_operations
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "r:0", "name": "read", "input": {"file_path": "/app/main.py"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "r:0", "content": "content"},
            ]},
        ]
        read_files, modified_files = _extract_file_operations(messages)
        assert "/app/main.py" in read_files
        assert len(modified_files) == 0

    def test_extracts_write_operations(self):
        from app.agent.agent import _extract_file_operations
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "w:0", "name": "write", "input": {"file_path": "/app/out.txt"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w:0", "content": "ok"},
            ]},
        ]
        read_files, modified_files = _extract_file_operations(messages)
        assert len(read_files) == 0
        assert "/app/out.txt" in modified_files

    def test_extracts_edit_operations(self):
        from app.agent.agent import _extract_file_operations
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "e:0", "name": "edit", "input": {"file_path": "/app/models.py"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "e:0", "content": "edited"},
            ]},
        ]
        _, modified_files = _extract_file_operations(messages)
        assert "/app/models.py" in modified_files

    def test_extracts_new_files_from_tool_result(self):
        from app.agent.agent import _extract_file_operations
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "c:0", "name": "execute_code", "input": {"code": "make_chart()"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "c:0",
                 "content": '{"success": true, "output": "done", "new_files": [{"filename": "chart.png"}]}'},
            ]},
        ]
        _, modified_files = _extract_file_operations(messages)
        assert "chart.png" in modified_files

    def test_extracts_glob_and_grep(self):
        from app.agent.agent import _extract_file_operations
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "g:0", "name": "glob", "input": {"path": "/app", "pattern": "**/*.py"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "g:0", "content": "found files"},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "s:0", "name": "grep", "input": {"path": "/app/src"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "s:0", "content": "matches"},
            ]},
        ]
        read_files, _ = _extract_file_operations(messages)
        assert "/app/**/*.py" in read_files
        assert "/app/src" in read_files

    def test_empty_messages(self):
        from app.agent.agent import _extract_file_operations
        read_files, modified_files = _extract_file_operations([])
        assert len(read_files) == 0
        assert len(modified_files) == 0

    def test_plain_text_messages_no_ops(self):
        from app.agent.agent import _extract_file_operations
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        read_files, modified_files = _extract_file_operations(messages)
        assert len(read_files) == 0
        assert len(modified_files) == 0


# ===========================================================================
# _extract_previous_file_tracking
# ===========================================================================

class TestExtractPreviousFileTracking:
    def test_extracts_both_sections(self):
        from app.agent.agent import _extract_previous_file_tracking
        text = """<summary>
## Test
<read-files>
/app/main.py
/app/config.py
</read-files>
<modified-files>
/app/output.csv
</modified-files>
</summary>"""
        read_files, modified_files = _extract_previous_file_tracking(text)
        assert read_files == {"/app/main.py", "/app/config.py"}
        assert modified_files == {"/app/output.csv"}

    def test_handles_missing_sections(self):
        from app.agent.agent import _extract_previous_file_tracking
        text = "<summary>No file tracking here</summary>"
        read_files, modified_files = _extract_previous_file_tracking(text)
        assert len(read_files) == 0
        assert len(modified_files) == 0

    def test_handles_empty_sections(self):
        from app.agent.agent import _extract_previous_file_tracking
        text = "<read-files>\n</read-files>\n<modified-files>\n</modified-files>"
        read_files, modified_files = _extract_previous_file_tracking(text)
        assert len(read_files) == 0
        assert len(modified_files) == 0


# ===========================================================================
# _build_file_tracking_section
# ===========================================================================

class TestBuildFileTrackingSection:
    def test_builds_both_sections(self):
        from app.agent.agent import _build_file_tracking_section
        result = _build_file_tracking_section(
            read_files={"/app/a.py", "/app/b.py"},
            modified_files={"/app/out.txt"},
        )
        assert "<read-files>" in result
        assert "/app/a.py" in result
        assert "/app/b.py" in result
        assert "<modified-files>" in result
        assert "/app/out.txt" in result

    def test_empty_sets(self):
        from app.agent.agent import _build_file_tracking_section
        result = _build_file_tracking_section(set(), set())
        assert result == ""

    def test_only_read_files(self):
        from app.agent.agent import _build_file_tracking_section
        result = _build_file_tracking_section({"/app/x.py"}, set())
        assert "<read-files>" in result
        assert "<modified-files>" not in result


# ===========================================================================
# Split turn handling
# ===========================================================================

@pytest.mark.asyncio
class TestSplitTurnHandling:
    """Tests for the split-oversized-turn code path in _compress_messages."""

    async def test_split_turn_produces_prefix_summary(self):
        """When keep_turns==1 and the turn is oversized, it should be split."""
        agent = _make_agent()
        # Very small context so 1 turn exceeds 50% of budget
        mock_workspace = MagicMock()
        mock_workspace.cleanup = MagicMock()
        with patch("app.agent.agent.get_tools_for_agent", return_value=([], {}, mock_workspace)):
            agent = SkillsAgent(
                model="claude-sonnet-4-5-20250929",
                max_turns=5,
                verbose=False,
                log_dir="/tmp/test_logs",
                equipped_mcp_servers=[],
            )
        agent._get_context_limit = lambda: 5000  # Tiny: budget = 1250 tokens

        # LLM calls: first for turn prefix summary, second for history summary
        prefix_response = MockResponse(
            content=[MockTextBlock(text="## Original Request\nUser asked to do work\n## Early Progress\nStarted\n## Context for Suffix\nContinuing")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=100, output_tokens=50),
        )
        summary_response = MockResponse(
            content=[MockTextBlock(text="<summary>\n## Primary Request\nOverall summary\n</summary>")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=200, output_tokens=80),
        )
        agent.client = create_mock_llm_client([prefix_response, summary_response])

        # Build: 2 turns. Turn 1 is small, turn 2 is very large (many tool calls)
        messages = [
            {"role": "user", "content": "First simple question"},
            {"role": "assistant", "content": [{"type": "text", "text": "Simple answer"}]},
        ]
        # Turn 2: large with many tool steps
        messages.append({"role": "user", "content": "Do a big task"})
        for step in range(10):
            messages.append({
                "role": "assistant",
                "content": [
                    {"type": "text", "text": f"Step {step}: working..."},
                    {"type": "tool_use", "id": f"tool_{step}", "name": "execute_code",
                     "input": {"code": f"result_{step} = process({step})\n" + "x" * 500}},
                ],
            })
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": f"tool_{step}",
                     "content": f"Output of step {step}: " + "Y" * 500},
                ],
            })
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "All steps complete!"}],
        })

        compressed, _, _ = await agent._compress_messages(messages)

        # Should have compressed output
        assert len(compressed) < len(messages)
        # Summary should contain turn prefix context
        summary_content = compressed[0]["content"]
        assert "Recent turn prefix context" in summary_content

    async def test_split_turn_no_valid_cut_points_keeps_whole(self):
        """When the oversized turn has no valid cut points, keep it whole."""
        agent = _make_agent()
        agent._get_context_limit = lambda: 3000  # Tiny

        summary_response = MockResponse(
            content=[MockTextBlock(text="<summary>\nSummary\n</summary>")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=100, output_tokens=50),
        )
        agent.client = create_mock_llm_client([summary_response])

        # Turn 1: small
        messages = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": [{"type": "text", "text": "OK"}]},
        ]
        # Turn 2: large but ONLY a user message + one assistant with tool_use + tool_result + final
        # All assistant messages are followed by tool_result, so no valid cut points
        messages.append({"role": "user", "content": "Big task"})
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t:0", "name": "execute_code",
                 "input": {"code": "x" * 2000}},
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t:0",
                 "content": "Y" * 2000},
            ],
        })
        # Final assistant is at the end, but there's only one cut point possibility
        # and it's the last message — best_cut would need to be > turn_start
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "Done"}],
        })

        compressed, _, _ = await agent._compress_messages(messages)
        # Should still produce compressed output (no split, just regular compression)
        assert len(compressed) < len(messages)
        assert compressed[0]["role"] == "user"
        assert "<summary>" in compressed[0]["content"]

    async def test_split_turn_prefix_llm_failure_uses_fallback(self):
        """When turn prefix LLM call fails, fallback to serialized text."""
        agent = _make_agent()
        agent._get_context_limit = lambda: 5000  # Tiny

        call_count = {"n": 0}

        async def mock_acreate(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call (turn prefix summary) fails
                raise Exception("API error")
            # Second call (main summary) succeeds
            resp = MagicMock()
            resp.text_content = "<summary>\nMain summary\n</summary>"
            resp.usage = MagicMock(input_tokens=200, output_tokens=80)
            return resp

        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(side_effect=mock_acreate)

        # Turn 1: small
        messages = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": [{"type": "text", "text": "Answer"}]},
        ]
        # Turn 2: large with many steps
        messages.append({"role": "user", "content": "Do complex work"})
        for step in range(8):
            messages.append({
                "role": "assistant",
                "content": [
                    {"type": "text", "text": f"Working on step {step}"},
                    {"type": "tool_use", "id": f"t_{step}", "name": "bash",
                     "input": {"command": f"echo step_{step}" + "Z" * 300}},
                ],
            })
            messages.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": f"t_{step}",
                     "content": f"step_{step} output " + "W" * 300},
                ],
            })
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "All done!"}],
        })

        compressed, _, _ = await agent._compress_messages(messages)

        # Should still produce output despite prefix LLM failure
        assert len(compressed) < len(messages)
        summary_content = compressed[0]["content"]
        # Fallback uses serialized text as turn prefix summary
        assert "Recent turn prefix context" in summary_content


@pytest.mark.asyncio
class TestIterativeFallback:
    """Tests for iterative compression fallback behavior."""

    async def test_iterative_api_failure_preserves_previous_summary(self):
        """When UPDATE prompt API call fails, fallback uses previous_summary_text."""
        agent = _make_agent()
        agent.client = MagicMock()
        agent.client.acreate = AsyncMock(side_effect=Exception("API error"))

        # Build messages with previous summary
        previous_summary_content = (
            "This session is being continued from a previous conversation.\n\n"
            "<summary>\n## Primary Request\nUser wanted to build a dashboard\n"
            "## Current State\nHalfway done\n</summary>\n\n"
            "Continue with the last task."
        )
        messages = [
            {"role": "user", "content": previous_summary_content},
            {"role": "assistant", "content": [{"type": "text", "text": "I understand the context. Let me continue from where we left off."}]},
        ]
        for i in range(8):
            messages.append({"role": "user", "content": f"New request {i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"Response {i}"}]})

        compressed, s_in, s_out = await agent._compress_messages(messages)

        # Should use the previous summary as fallback
        assert len(compressed) < len(messages)
        summary_content = compressed[0]["content"]
        assert "User wanted to build a dashboard" in summary_content
        assert s_in == 0  # No API tokens consumed
        assert s_out == 0

    async def test_no_file_operations_no_xml_tags(self):
        """When no file operations in conversation, no <read-files>/<modified-files> tags."""
        agent = _make_agent()
        summary_response = MockResponse(
            content=[MockTextBlock(text="<summary>\n## Test\nPlain conversation\n</summary>")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=200, output_tokens=50),
        )
        agent.client = create_mock_llm_client([summary_response])

        # Simple conversation with no tool calls
        messages = _build_conversation(10)
        compressed, _, _ = await agent._compress_messages(messages)

        summary_content = compressed[0]["content"]
        assert "<read-files>" not in summary_content
        assert "<modified-files>" not in summary_content


@pytest.mark.asyncio
class TestStandaloneIterativeCompression:
    """Tests for compress_messages_standalone iterative path."""

    async def test_standalone_iterative_uses_update_prompt(self):
        """compress_messages_standalone detects previous summary and uses UPDATE prompt."""
        from app.agent.agent import compress_messages_standalone

        mock_resp = MagicMock()
        mock_resp.text_content = "<summary>\n## Updated\nMerged summary\n</summary>"
        mock_resp.usage = MagicMock(input_tokens=300, output_tokens=100)

        # Build messages with previous summary
        previous_summary_content = (
            "This session is being continued from a previous conversation.\n\n"
            "<summary>\n## Primary Request\nUser wanted X\n</summary>\n\n"
            "Continue."
        )
        messages = [
            {"role": "user", "content": previous_summary_content},
            {"role": "assistant", "content": [{"type": "text", "text": "I understand the context. Let me continue from where we left off."}]},
        ]
        for i in range(8):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"A{i}"}]})

        with patch("app.agent.agent.LLMClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.acreate = AsyncMock(return_value=mock_resp)
            MockClient.return_value = mock_client_instance

            compressed, s_in, s_out = await compress_messages_standalone(
                messages, model_provider="kimi", model_name="kimi-k2.5"
            )

        assert len(compressed) < len(messages)
        # Verify the UPDATE prompt was used
        call_args = mock_client_instance.acreate.call_args
        system_used = call_args.kwargs.get("system", "")
        assert "previous-summary" in system_used
        assert s_in == 300
        assert s_out == 100

    async def test_standalone_file_tracking(self):
        """compress_messages_standalone includes file tracking."""
        from app.agent.agent import compress_messages_standalone

        mock_resp = MagicMock()
        mock_resp.text_content = "<summary>\n## Test\nSummary\n</summary>"
        mock_resp.usage = MagicMock(input_tokens=200, output_tokens=50)

        # Messages with read and write operations
        messages = [
            {"role": "user", "content": "Analyze data"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "r:0", "name": "read", "input": {"file_path": "/app/data.csv"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "r:0", "content": "csv data"},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "w:0", "name": "write", "input": {"file_path": "/app/report.md"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w:0", "content": "written"},
            ]},
            {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
        ]
        for i in range(8):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"A{i}"}]})

        with patch("app.agent.agent.LLMClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.acreate = AsyncMock(return_value=mock_resp)
            MockClient.return_value = mock_client_instance

            compressed, _, _ = await compress_messages_standalone(
                messages, model_provider="kimi", model_name="kimi-k2.5"
            )

        summary_content = compressed[0]["content"]
        assert "<read-files>" in summary_content
        assert "/app/data.csv" in summary_content
        assert "<modified-files>" in summary_content
        assert "/app/report.md" in summary_content

    async def test_standalone_fallback_preserves_previous_summary(self):
        """Standalone fallback on API failure uses previous_summary_text when available."""
        from app.agent.agent import compress_messages_standalone

        previous_summary_content = (
            "This session is being continued from a previous conversation.\n\n"
            "<summary>\n## Primary Request\nUser wanted to refactor code\n</summary>\n\n"
            "Continue."
        )
        messages = [
            {"role": "user", "content": previous_summary_content},
            {"role": "assistant", "content": [{"type": "text", "text": "I understand the context. Let me continue from where we left off."}]},
        ]
        for i in range(8):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"A{i}"}]})

        with patch("app.agent.agent.LLMClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.acreate = AsyncMock(side_effect=Exception("API error"))
            MockClient.return_value = mock_client_instance

            compressed, s_in, s_out = await compress_messages_standalone(
                messages, model_provider="kimi", model_name="kimi-k2.5"
            )

        assert len(compressed) < len(messages)
        summary_content = compressed[0]["content"]
        assert "User wanted to refactor code" in summary_content
        assert s_in == 0
        assert s_out == 0


# ===========================================================================
# Integration: run() with compression (async)
# ===========================================================================

@pytest.mark.asyncio
class TestRunWithCompression:
    async def test_compression_triggered_in_run(self):
        """When input_tokens exceeds threshold, compression should fire."""
        agent = _make_agent(max_turns=3)

        # Provide enough conversation history so _compress_messages has enough
        # messages to split.
        history = _build_conversation(5)  # 10 messages

        # First response: high token count triggers compression on next turn
        high_token_response = MockResponse(
            content=[MockToolUseBlock(name="list_skills", input={})],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=150_000, output_tokens=100),
        )
        # Summary response (from _compress_messages)
        summary_response = MockResponse(
            content=[MockTextBlock(text="Summary of conversation")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=500, output_tokens=100),
        )
        # Final response after compression
        final_response = MockResponse(
            content=[MockTextBlock(text="Task complete")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=5000, output_tokens=200),
        )

        agent.client = create_mock_llm_client([high_token_response, summary_response, final_response])

        # Mock acall_tool to return something
        with patch("app.agent.agent.acall_tool", new_callable=AsyncMock, return_value="tool output"):
            result = await agent.run("Do something", conversation_history=history)

        assert result.success is True
        assert result.answer == "Task complete"
        # Summary tokens should be included in total
        assert result.total_input_tokens == 150_000 + 500 + 5000
        assert result.total_output_tokens == 100 + 100 + 200

    async def test_no_compression_below_threshold(self):
        """Compression should not fire when tokens are below threshold."""
        agent = _make_agent(max_turns=2)

        response = MockResponse(
            content=[MockTextBlock(text="Done")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=1000, output_tokens=50),
        )
        agent.client = create_mock_llm_client([response])

        result = await agent.run("Simple question")
        assert result.success is True
        # Only one API call, no compression
        assert agent.client.acreate.call_count == 1


# ===========================================================================
# Integration: run() streaming with compression (async)
# ===========================================================================

@pytest.mark.asyncio
class TestRunStreamWithCompression:
    async def test_compression_emits_event(self):
        """run() with event_stream should push a context_compressed event when compressing."""
        from app.agent.event_stream import EventStream

        agent = _make_agent(max_turns=3)

        # Provide enough conversation history for compression to have messages to split
        history = _build_conversation(5)  # 10 messages

        high_token_response = MockResponse(
            content=[MockToolUseBlock(name="list_skills", input={})],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=150_000, output_tokens=100),
        )
        summary_response = MockResponse(
            content=[MockTextBlock(text="Summary")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=500, output_tokens=100),
        )
        final_response = MockResponse(
            content=[MockTextBlock(text="Done")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=5000, output_tokens=200),
        )

        agent.client = create_mock_llm_client([high_token_response, summary_response, final_response])

        event_stream = EventStream()
        events = []

        async def collect_events():
            async for event in event_stream:
                events.append(event)

        with patch("app.agent.agent.acall_tool", new_callable=AsyncMock, return_value="tool output"):
            collector = asyncio.create_task(collect_events())
            await agent.run("Do something", conversation_history=history, event_stream=event_stream)
            await collector

        event_types = [e.event_type for e in events]
        assert "context_compressed" in event_types

        # Check the compressed event data
        compressed_event = next(e for e in events if e.event_type == "context_compressed")
        assert compressed_event.data["previous_tokens"] == 150_000
        assert compressed_event.data["context_limit"] == 200_000

    async def test_no_compression_event_below_threshold(self):
        """run() with event_stream should NOT push context_compressed when below threshold."""
        from app.agent.event_stream import EventStream

        agent = _make_agent(max_turns=2)

        response = MockResponse(
            content=[MockTextBlock(text="Done")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=1000, output_tokens=50),
        )
        agent.client = create_mock_llm_client([response])

        event_stream = EventStream()
        events = []

        async def collect_events():
            async for event in event_stream:
                events.append(event)

        collector = asyncio.create_task(collect_events())
        await agent.run("Simple question", event_stream=event_stream)
        await collector

        event_types = [e.event_type for e in events]
        assert "context_compressed" not in event_types


# ===========================================================================
# max_tokens truncation handling
# ===========================================================================

@pytest.mark.asyncio
class TestMaxTokensTruncation:
    """Tests for handling stop_reason='max_tokens' which produces incomplete tool calls."""

    async def test_run_recovers_from_truncated_tool_call(self):
        """run() should not execute truncated tool calls and should ask Claude to retry."""
        agent = _make_agent(max_turns=3)

        # First response: truncated (max_tokens) with an incomplete tool call
        truncated_response = MockResponse(
            content=[MockToolUseBlock(name="execute_code", input={})],
            stop_reason="max_tokens",
            usage=MockUsage(input_tokens=1000, output_tokens=4096),
        )
        # Second response: Claude retries with shorter code and succeeds
        retry_response = MockResponse(
            content=[MockToolUseBlock(name="execute_code", input={"code": "print('ok')"})],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=2000, output_tokens=200),
        )
        # Final response after tool execution
        final_response = MockResponse(
            content=[MockTextBlock(text="Done")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=3000, output_tokens=100),
        )

        agent.client = create_mock_llm_client([truncated_response, retry_response, final_response])

        with patch("app.agent.agent.acall_tool", new_callable=AsyncMock, return_value='{"success": true}') as mock_call:
            result = await agent.run("Generate a report")

        assert result.success is True
        assert result.answer == "Done"
        # acall_tool should only be called once (for the retry), not for the truncated call
        assert mock_call.call_count == 1
        # The truncated call should have generated a step with an error
        truncation_steps = [s for s in result.steps if s.role == "tool" and "truncated" in (s.content or "")]
        assert len(truncation_steps) == 1

    async def test_run_truncated_no_tool_calls_ends_normally(self):
        """max_tokens with no tool calls (just text truncation) should end the turn normally."""
        agent = _make_agent(max_turns=2)

        # Response truncated but only has text (no tool calls)
        truncated_text_response = MockResponse(
            content=[MockTextBlock(text="This is a very long res...")],
            stop_reason="max_tokens",
            usage=MockUsage(input_tokens=1000, output_tokens=4096),
        )
        next_response = MockResponse(
            content=[MockTextBlock(text="Final answer")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=2000, output_tokens=100),
        )

        agent.client = create_mock_llm_client([truncated_text_response, next_response])
        result = await agent.run("Write something long")

        assert result.success is True

    async def test_stream_emits_error_for_truncated_tool_call(self):
        """run() with event_stream should emit tool_result error events for truncated calls."""
        from app.agent.event_stream import EventStream

        agent = _make_agent(max_turns=3)

        truncated_response = MockResponse(
            content=[MockToolUseBlock(name="execute_code", input={})],
            stop_reason="max_tokens",
            usage=MockUsage(input_tokens=1000, output_tokens=4096),
        )
        retry_response = MockResponse(
            content=[MockToolUseBlock(name="execute_code", input={"code": "print(1)"})],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=2000, output_tokens=200),
        )
        final_response = MockResponse(
            content=[MockTextBlock(text="All done")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=3000, output_tokens=100),
        )

        agent.client = create_mock_llm_client([truncated_response, retry_response, final_response])

        event_stream = EventStream()
        events = []

        async def collect_events():
            async for event in event_stream:
                events.append(event)

        with patch("app.agent.agent.acall_tool", new_callable=AsyncMock, return_value='{"success": true}'):
            collector = asyncio.create_task(collect_events())
            await agent.run("Generate report", event_stream=event_stream)
            await collector

        event_types = [e.event_type for e in events]

        # Should have a tool_result error for the truncated call
        truncation_events = [
            e for e in events
            if e.event_type == "tool_result" and "truncated" in e.data.get("tool_result", "")
        ]
        assert len(truncation_events) == 1

        # Should still complete successfully
        assert "complete" in event_types

    async def test_multiple_truncated_tool_calls(self):
        """Multiple tool calls in a truncated response should all be handled."""
        agent = _make_agent(max_turns=3)

        # Response with two tool calls, both truncated
        truncated_response = MockResponse(
            content=[
                MockToolUseBlock(name="execute_code", input={}),
                MockToolUseBlock(name="execute_command", input={}),
            ],
            stop_reason="max_tokens",
            usage=MockUsage(input_tokens=1000, output_tokens=4096),
        )
        final_response = MockResponse(
            content=[MockTextBlock(text="OK")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=2000, output_tokens=50),
        )

        agent.client = create_mock_llm_client([truncated_response, final_response])

        with patch("app.agent.agent.acall_tool", new_callable=AsyncMock) as mock_call:
            result = await agent.run("Do two things")

        assert result.success is True
        # acall_tool should NOT have been called for truncated calls
        assert mock_call.call_count == 0
        # Both truncated tool calls should generate error steps
        truncation_steps = [s for s in result.steps if "truncated" in (s.content or "")]
        assert len(truncation_steps) == 2
