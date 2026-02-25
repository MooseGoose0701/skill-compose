"""
Unit tests for DisplayMessageBuilder (app/api/v1/display_builder.py).

Tests the conversion of streaming SSE events into ChatMessage[] format
for session display storage.
"""
from dataclasses import dataclass, field
from typing import Optional, List

import pytest

from app.api.v1.display_builder import DisplayMessageBuilder


# ── Helpers ──────────────────────────────────────────────────────────


@dataclass
class FakeUploadedFile:
    file_id: str
    filename: str
    path: str = ""
    content_type: str = ""


@dataclass
class FakeStep:
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None


@dataclass
class FakeResult:
    success: bool = True
    answer: str = "Done"
    total_turns: int = 1
    total_input_tokens: int = 100
    total_output_tokens: int = 50
    steps: Optional[list] = None
    skills_used: Optional[list] = None


# ── Basic builder tests ──────────────────────────────────────────────


class TestDisplayMessageBuilderBasic:

    def test_empty_builder(self):
        """Empty builder returns empty list."""
        b = DisplayMessageBuilder()
        assert b.get_messages() == []

    def test_user_message_only(self):
        """User message without files."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hello")
        msgs = b.get_messages()
        assert len(msgs) == 1
        assert msgs[0] == {"role": "user", "content": "Hello"}

    def test_user_message_with_files(self):
        """User message with uploaded files produces attachedFiles."""
        files = [
            FakeUploadedFile(file_id="f1", filename="data.csv"),
            FakeUploadedFile(file_id="f2", filename="image.png"),
        ]
        b = DisplayMessageBuilder()
        b.add_user_message("Analyze this", files)
        msgs = b.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Analyze this"
        assert msgs[0]["attachedFiles"] == [
            {"file_id": "f1", "filename": "data.csv"},
            {"file_id": "f2", "filename": "image.png"},
        ]

    def test_user_message_no_files_no_attached(self):
        """User message with uploaded_files=None has no attachedFiles key."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi", None)
        msgs = b.get_messages()
        assert "attachedFiles" not in msgs[0]

    def test_user_message_empty_files_no_attached(self):
        """User message with uploaded_files=[] has no attachedFiles key."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi", [])
        msgs = b.get_messages()
        assert "attachedFiles" not in msgs[0]


class TestDisplayMessageBuilderEvents:

    def test_turn_start_event(self):
        """turn_start is mapped correctly."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("turn_start", 1, {"max_turns": 10})
        msgs = b.get_messages()
        assert len(msgs) == 2
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "turn_start"
        assert evt["data"]["turn"] == 1
        assert evt["data"]["maxTurns"] == 10

    def test_assistant_event(self):
        """assistant event maps content."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("assistant", 1, {"content": "Hello!", "input_tokens": 50, "output_tokens": 10})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "assistant"
        assert evt["data"]["content"] == "Hello!"
        assert evt["data"]["inputTokens"] == 50
        assert evt["data"]["outputTokens"] == 10

    def test_assistant_empty_content_skipped(self):
        """assistant event with empty content is skipped."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("assistant", 1, {"content": ""})
        msgs = b.get_messages()
        assert len(msgs) == 1  # Only user, no assistant

    def test_tool_call_event(self):
        """tool_call maps toolName and toolInput."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("tool_call", 1, {"tool_name": "bash", "tool_input": {"command": "ls"}})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "tool_call"
        assert evt["data"]["toolName"] == "bash"
        assert evt["data"]["toolInput"] == {"command": "ls"}

    def test_tool_result_event(self):
        """tool_result maps success flag correctly."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("tool_result", 1, {"tool_name": "bash", "tool_result": "file.txt", "is_error": False})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "tool_result"
        assert evt["data"]["toolName"] == "bash"
        assert evt["data"]["toolResult"] == "file.txt"
        assert evt["data"]["success"] is True

    def test_tool_result_error(self):
        """tool_result with is_error=True produces success=False."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("tool_result", 1, {"tool_name": "bash", "tool_result": "error", "is_error": True})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["data"]["success"] is False

    def test_output_file_event(self):
        """output_file maps all fields."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("output_file", 1, {
            "file_id": "uuid1", "filename": "chart.png", "size": 1024,
            "content_type": "image/png", "download_url": "/download/uuid1",
            "description": "A chart",
        })
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "output_file"
        assert evt["data"]["fileId"] == "uuid1"
        assert evt["data"]["filename"] == "chart.png"
        assert evt["data"]["size"] == 1024
        assert evt["data"]["contentType"] == "image/png"
        assert evt["data"]["downloadUrl"] == "/download/uuid1"
        assert evt["data"]["description"] == "A chart"

    def test_ask_user_event(self):
        """ask_user maps promptId, question, options."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("ask_user", 1, {
            "prompt_id": "p1", "question": "Which format?", "options": ["CSV", "JSON"],
        })
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "ask_user"
        assert evt["data"]["promptId"] == "p1"
        assert evt["data"]["question"] == "Which format?"
        assert evt["data"]["options"] == ["CSV", "JSON"]

    def test_complete_event(self):
        """complete maps all stats."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("complete", 1, {
            "success": True, "answer": "Done", "total_turns": 3,
            "total_input_tokens": 200, "total_output_tokens": 50,
        })
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "complete"
        assert evt["data"]["success"] is True
        assert evt["data"]["answer"] == "Done"
        assert evt["data"]["totalTurns"] == 3
        assert evt["data"]["totalInputTokens"] == 200
        assert evt["data"]["totalOutputTokens"] == 50

    def test_error_event(self):
        """error maps message."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("error", 1, {"message": "Something failed"})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "error"
        assert evt["data"]["message"] == "Something failed"

    def test_error_event_fallback_key(self):
        """error event with 'error' key instead of 'message'."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("error", 1, {"error": "fail reason"})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["data"]["message"] == "fail reason"

    def test_steering_received_event(self):
        """steering_received maps message."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("steering_received", 1, {"message": "User said: focus on X"})
        msgs = b.get_messages()
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "steering_received"
        assert evt["data"]["message"] == "User said: focus on X"

    def test_unknown_event_type_ignored(self):
        """Unknown event types are silently ignored."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("some_future_event", 1, {"data": "value"})
        msgs = b.get_messages()
        assert len(msgs) == 1  # Only user, no assistant


class TestDisplayMessageBuilderSkippedEvents:

    def test_heartbeat_skipped(self):
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("heartbeat", 0, {})
        assert b.get_messages() == [{"role": "user", "content": "Hi"}]

    def test_run_started_skipped(self):
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("run_started", 0, {"trace_id": "t1"})
        assert b.get_messages() == [{"role": "user", "content": "Hi"}]

    def test_trace_saved_skipped(self):
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("trace_saved", 0, {"trace_id": "t1"})
        assert b.get_messages() == [{"role": "user", "content": "Hi"}]

    def test_text_delta_accumulated(self):
        """text_delta chunks are accumulated and flushed as assistant record."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("text_delta", 1, {"text": "Hello "})
        b.add_event("text_delta", 1, {"text": "world!"})
        msgs = b.get_messages()
        assert len(msgs) == 2
        evt = msgs[1]["streamEvents"][0]
        assert evt["type"] == "assistant"
        assert evt["data"]["content"] == "Hello world!"

    def test_text_delta_flushed_before_tool_call(self):
        """Accumulated text_delta is flushed as assistant before tool_call."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("text_delta", 1, {"text": "I'll run a command"})
        b.add_event("tool_call", 1, {"tool_name": "bash", "tool_input": {"command": "ls"}})
        msgs = b.get_messages()
        events = msgs[1]["streamEvents"]
        assert events[0]["type"] == "assistant"
        assert events[0]["data"]["content"] == "I'll run a command"
        assert events[1]["type"] == "tool_call"

    def test_text_delta_only_skipped_when_empty(self):
        """text_delta with empty text doesn't produce assistant record."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("text_delta", 1, {"text": ""})
        b.add_event("complete", 1, {"success": True})
        msgs = b.get_messages()
        events = msgs[1]["streamEvents"]
        assert len(events) == 1
        assert events[0]["type"] == "complete"

    def test_turn_complete_skipped(self):
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("turn_complete", 1, {"messages_snapshot": []})
        assert b.get_messages() == [{"role": "user", "content": "Hi"}]

    def test_context_compressed_skipped(self):
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("context_compressed", 1, {})
        assert b.get_messages() == [{"role": "user", "content": "Hi"}]


class TestDisplayMessageBuilderFlush:

    def test_new_user_flushes_assistant(self):
        """Adding a second user message flushes the pending assistant."""
        b = DisplayMessageBuilder()
        b.add_user_message("Q1")
        b.add_event("assistant", 1, {"content": "A1"})
        b.add_user_message("Q2")
        b.add_event("assistant", 2, {"content": "A2"})
        msgs = b.get_messages()
        assert len(msgs) == 4  # user, assistant, user, assistant
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["streamEvents"][0]["data"]["content"] == "A1"
        assert msgs[2]["role"] == "user"
        assert msgs[3]["role"] == "assistant"
        assert msgs[3]["streamEvents"][0]["data"]["content"] == "A2"

    def test_get_messages_flushes(self):
        """get_messages flushes pending events."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("assistant", 1, {"content": "Hello"})
        msgs = b.get_messages()
        assert len(msgs) == 2
        # After flush, _current_events should be empty
        assert len(b._current_events) == 0


class TestDisplayMessageBuilderSnapshot:

    def test_snapshot_includes_in_progress(self):
        """get_snapshot includes unflushed events without flushing."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("turn_start", 1, {"max_turns": 5})
        b.add_event("tool_call", 1, {"tool_name": "bash", "tool_input": {"command": "ls"}})

        snap = b.get_snapshot()
        assert len(snap) == 2  # user + in-progress assistant
        assert snap[1]["role"] == "assistant"
        assert len(snap[1]["streamEvents"]) == 2

        # Original builder state not modified
        assert len(b._current_events) == 2
        assert len(b._messages) == 1

    def test_snapshot_empty_events(self):
        """Snapshot with no pending events returns only finalized messages."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        snap = b.get_snapshot()
        assert len(snap) == 1
        assert snap[0]["role"] == "user"

    def test_snapshot_after_flush(self):
        """Snapshot after get_messages returns same as get_messages."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("assistant", 1, {"content": "Hello"})
        msgs = b.get_messages()
        snap = b.get_snapshot()
        assert msgs == snap

    def test_snapshot_includes_text_buffer(self):
        """Snapshot includes unflushed text_delta buffer without consuming it."""
        b = DisplayMessageBuilder()
        b.add_user_message("Hi")
        b.add_event("turn_start", 1, {"max_turns": 5})
        b.add_event("text_delta", 1, {"text": "I'm thinking"})
        b.add_event("text_delta", 1, {"text": "..."})

        snap = b.get_snapshot()
        assert len(snap) == 2  # user + in-progress assistant
        events = snap[1]["streamEvents"]
        assert len(events) == 2  # turn_start + assistant (from text buffer)
        assert events[1]["type"] == "assistant"
        assert events[1]["data"]["content"] == "I'm thinking..."

        # Original builder state preserved
        assert b._text_buffer == "I'm thinking..."
        assert len(b._current_events) == 1  # only turn_start


class TestDisplayMessageBuilderFromResult:

    def test_from_result_basic(self):
        """from_agent_result with simple assistant content."""
        result = FakeResult(
            steps=[FakeStep(role="assistant", content="Hello world")],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "Hi")
        msgs = builder.get_messages()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "Hi"}
        events = msgs[1]["streamEvents"]
        event_types = [e["type"] for e in events]
        assert "assistant" in event_types
        assert "complete" in event_types

    def test_from_result_with_tools(self):
        """from_agent_result with tool calls."""
        result = FakeResult(
            steps=[
                FakeStep(role="tool", content="result text", tool_name="bash", tool_input={"command": "ls"}),
                FakeStep(role="assistant", content="Done"),
            ],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "Run ls")
        msgs = builder.get_messages()
        events = msgs[1]["streamEvents"]
        event_types = [e["type"] for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "assistant" in event_types
        assert "complete" in event_types

    def test_from_result_with_ask_user(self):
        """from_agent_result with ask_user tool."""
        result = FakeResult(
            steps=[
                FakeStep(
                    role="tool", content="",
                    tool_name="ask_user",
                    tool_input={"question": "Which format?", "options": ["CSV", "JSON"]},
                ),
            ],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "Analyze")
        msgs = builder.get_messages()
        events = msgs[1]["streamEvents"]
        event_types = [e["type"] for e in events]
        assert "tool_call" in event_types
        assert "ask_user" in event_types
        # Verify ask_user data
        ask_evt = [e for e in events if e["type"] == "ask_user"][0]
        assert ask_evt["data"]["question"] == "Which format?"
        assert ask_evt["data"]["options"] == ["CSV", "JSON"]

    def test_from_result_with_files(self):
        """from_agent_result with uploaded files."""
        files = [FakeUploadedFile(file_id="f1", filename="data.csv")]
        result = FakeResult(
            steps=[FakeStep(role="assistant", content="Analyzed")],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "Analyze", files)
        msgs = builder.get_messages()
        assert msgs[0]["attachedFiles"] == [{"file_id": "f1", "filename": "data.csv"}]

    def test_from_result_complete_event_stats(self):
        """from_agent_result complete event has correct stats."""
        result = FakeResult(
            success=True, answer="42", total_turns=3,
            total_input_tokens=500, total_output_tokens=100,
            steps=[],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "What is 6*7?")
        msgs = builder.get_messages()
        events = msgs[1]["streamEvents"]
        complete_evt = [e for e in events if e["type"] == "complete"][0]
        assert complete_evt["data"]["success"] is True
        assert complete_evt["data"]["answer"] == "42"
        assert complete_evt["data"]["totalTurns"] == 3
        assert complete_evt["data"]["totalInputTokens"] == 500
        assert complete_evt["data"]["totalOutputTokens"] == 100

    def test_from_result_tool_result_truncated(self):
        """from_agent_result truncates tool result content to 5000 chars."""
        long_content = "x" * 10000
        result = FakeResult(
            steps=[
                FakeStep(role="tool", content=long_content, tool_name="bash", tool_input={}),
            ],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "Hi")
        msgs = builder.get_messages()
        events = msgs[1]["streamEvents"]
        tr_evt = [e for e in events if e["type"] == "tool_result"][0]
        assert len(tr_evt["data"]["toolResult"]) == 5000

    def test_from_result_tool_error_detected(self):
        """from_agent_result infers success=False from error-like content."""
        error_contents = [
            '{"error": "No such file"}',
            'Error: command not found',
            'Traceback (most recent call last):\n  File ...',
        ]
        for err_content in error_contents:
            result = FakeResult(
                steps=[FakeStep(role="tool", content=err_content, tool_name="bash", tool_input={})],
            )
            builder = DisplayMessageBuilder.from_agent_result(result, "Hi")
            msgs = builder.get_messages()
            events = msgs[1]["streamEvents"]
            tr_evt = [e for e in events if e["type"] == "tool_result"][0]
            assert tr_evt["data"]["success"] is False, f"Expected success=False for: {err_content[:30]}"

    def test_from_result_tool_success_normal_content(self):
        """from_agent_result marks normal tool output as success=True."""
        result = FakeResult(
            steps=[FakeStep(role="tool", content="file.txt\ndata.csv", tool_name="bash", tool_input={})],
        )
        builder = DisplayMessageBuilder.from_agent_result(result, "Hi")
        msgs = builder.get_messages()
        events = msgs[1]["streamEvents"]
        tr_evt = [e for e in events if e["type"] == "tool_result"][0]
        assert tr_evt["data"]["success"] is True


class TestDisplayMessageBuilderFullFlow:

    def test_full_streaming_flow(self):
        """Simulate a complete streaming session."""
        b = DisplayMessageBuilder()
        b.add_user_message("Analyze data.csv", [
            FakeUploadedFile(file_id="f1", filename="data.csv"),
        ])

        # Turn 1: tool call + result
        b.add_event("turn_start", 1, {"max_turns": 60})
        b.add_event("tool_call", 1, {"tool_name": "execute_code", "tool_input": {"code": "import pandas"}})
        b.add_event("tool_result", 1, {"tool_name": "execute_code", "tool_result": "OK"})

        # Turn 2: assistant + output file + complete
        b.add_event("turn_start", 2, {"max_turns": 60})
        b.add_event("assistant", 2, {"content": "Here are the results"})
        b.add_event("output_file", 2, {
            "file_id": "of1", "filename": "chart.png", "size": 2048,
            "content_type": "image/png", "download_url": "/download/of1",
        })
        b.add_event("complete", 2, {
            "success": True, "answer": "Here are the results",
            "total_turns": 2, "total_input_tokens": 300, "total_output_tokens": 80,
        })

        msgs = b.get_messages()
        assert len(msgs) == 2  # user + assistant
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Analyze data.csv"
        assert msgs[0]["attachedFiles"] == [{"file_id": "f1", "filename": "data.csv"}]

        events = msgs[1]["streamEvents"]
        types = [e["type"] for e in events]
        assert types == [
            "turn_start", "tool_call", "tool_result",
            "turn_start", "assistant", "output_file", "complete",
        ]

    def test_full_streaming_flow_with_text_delta(self):
        """Simulate real-world streaming: text_delta chunks between tool calls."""
        b = DisplayMessageBuilder()
        b.add_user_message("Visualize this")

        # Turn 1: assistant text (as deltas) + tool calls
        b.add_event("turn_start", 1, {"max_turns": 60})
        b.add_event("text_delta", 1, {"text": "I'll create "})
        b.add_event("text_delta", 1, {"text": "a visualizer!"})
        b.add_event("tool_call", 1, {"tool_name": "get_skill", "tool_input": {"skill_name": "remotion"}})
        b.add_event("tool_result", 1, {"tool_name": "get_skill", "tool_result": "skill content"})

        # Turn 2: more text + another tool
        b.add_event("turn_start", 2, {"max_turns": 60})
        b.add_event("text_delta", 2, {"text": "Now setting up the project"})
        b.add_event("tool_call", 2, {"tool_name": "bash", "tool_input": {"command": "npm init"}})
        b.add_event("tool_result", 2, {"tool_name": "bash", "tool_result": "OK"})

        # Final turn: text + complete
        b.add_event("turn_start", 3, {"max_turns": 60})
        b.add_event("text_delta", 3, {"text": "All done!"})
        b.add_event("complete", 3, {
            "success": True, "answer": "All done!",
            "total_turns": 3, "total_input_tokens": 500, "total_output_tokens": 100,
        })

        msgs = b.get_messages()
        assert len(msgs) == 2  # user + assistant
        events = msgs[1]["streamEvents"]
        types = [e["type"] for e in events]
        assert types == [
            "turn_start",
            "assistant",    # "I'll create a visualizer!" (flushed before tool_call)
            "tool_call",
            "tool_result",
            "turn_start",
            "assistant",    # "Now setting up the project" (flushed before tool_call)
            "tool_call",
            "tool_result",
            "turn_start",
            "assistant",    # "All done!" (flushed before complete)
            "complete",
        ]
        # Verify text content
        assistant_events = [e for e in events if e["type"] == "assistant"]
        assert assistant_events[0]["data"]["content"] == "I'll create a visualizer!"
        assert assistant_events[1]["data"]["content"] == "Now setting up the project"
        assert assistant_events[2]["data"]["content"] == "All done!"

    def test_ask_user_followed_by_user_response(self):
        """ask_user event followed by user response — frontend infers selectedAnswer from message order."""
        b = DisplayMessageBuilder()
        b.add_user_message("Create a poster")

        # Agent asks user a question
        b.add_event("turn_start", 1, {"max_turns": 60})
        b.add_event("text_delta", 1, {"text": "Which style?"})
        b.add_event("ask_user", 1, {
            "prompt_id": "p1", "question": "Choose a style",
            "options": ["Cyberpunk", "Minimal", "Retro"],
        })
        b.add_event("complete", 1, {"success": True, "total_turns": 1})

        # User responds (new request → new add_user_message)
        b.add_user_message("Cyberpunk")

        # Agent continues
        b.add_event("turn_start", 2, {"max_turns": 60})
        b.add_event("text_delta", 2, {"text": "Great choice!"})
        b.add_event("complete", 2, {"success": True, "total_turns": 2})

        msgs = b.get_messages()
        # Structure: user, assistant(ask_user), user(response), assistant(continuation)
        assert len(msgs) == 4
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Create a poster"
        assert msgs[1]["role"] == "assistant"
        ask_events = [e for e in msgs[1]["streamEvents"] if e["type"] == "ask_user"]
        assert len(ask_events) == 1
        assert ask_events[0]["data"]["options"] == ["Cyberpunk", "Minimal", "Retro"]
        # User's response is the next message — frontend uses msgs[i+1].content as selectedAnswer
        assert msgs[2]["role"] == "user"
        assert msgs[2]["content"] == "Cyberpunk"
        assert msgs[3]["role"] == "assistant"

    def test_multi_turn_conversation(self):
        """Simulate multi-turn conversation with user flushes."""
        b = DisplayMessageBuilder()

        # Turn 1
        b.add_user_message("Q1")
        b.add_event("assistant", 1, {"content": "A1"})
        b.add_event("complete", 1, {"success": True, "answer": "A1", "total_turns": 1})

        # Turn 2 (new user message flushes assistant)
        b.add_user_message("Q2")
        b.add_event("assistant", 2, {"content": "A2"})
        b.add_event("complete", 2, {"success": True, "answer": "A2", "total_turns": 2})

        msgs = b.get_messages()
        assert len(msgs) == 4  # user, assistant, user, assistant
        assert msgs[0]["content"] == "Q1"
        assert msgs[2]["content"] == "Q2"
