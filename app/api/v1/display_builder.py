"""DisplayMessageBuilder — accumulates SSE events into ChatMessage[] format.

The session `messages` column is purely for frontend display.  This builder
maps backend streaming events to the frontend StreamEventRecord format so
that refreshing the page renders identically to the live stream.
"""
from __future__ import annotations

from typing import Optional


class DisplayMessageBuilder:
    """Accumulates streaming events into ChatMessage[] format for session display storage."""

    def __init__(self):
        self._messages: list = []           # Finalized ChatMessage dicts
        self._current_events: list = []     # StreamEventRecords for current assistant
        self._text_buffer: str = ""         # Accumulate text_delta chunks

    def add_user_message(self, content: str, uploaded_files=None):
        """Add user message with clean text + optional attachedFiles metadata."""
        self._flush_assistant()
        msg: dict = {"role": "user", "content": content}
        if uploaded_files:
            msg["attachedFiles"] = [
                {"file_id": f.file_id, "filename": f.filename}
                for f in uploaded_files
            ]
        self._messages.append(msg)

    def add_event(self, event_type: str, turn: int, data: dict):
        """Map a backend SSE event to a StreamEventRecord and accumulate."""
        # Skip non-display events (but NOT text_delta — we accumulate those)
        if event_type in ("run_started", "trace_saved", "heartbeat",
                          "turn_complete", "context_compressed"):
            return

        # Accumulate text_delta chunks into buffer
        if event_type == "text_delta":
            self._text_buffer += data.get("text", "")
            return

        # Flush accumulated text as an assistant record before processing
        # boundary events (tool_call, tool_result, turn_start, complete, etc.)
        self._flush_text_buffer()

        record = self._map_to_record(event_type, turn, data)
        if record:
            self._current_events.append(record)

    def _map_to_record(self, event_type: str, turn: int, data: dict) -> Optional[dict]:
        """Map backend event -> frontend StreamEventRecord (without id/timestamp)."""
        if event_type == "turn_start":
            return {"type": "turn_start", "data": {"turn": turn, "maxTurns": data.get("max_turns", 0)}}
        elif event_type == "assistant":
            content = data.get("content", "")
            if not content:
                return None
            return {"type": "assistant", "data": {
                "content": content,
                "inputTokens": data.get("input_tokens"),
                "outputTokens": data.get("output_tokens"),
            }}
        elif event_type == "tool_call":
            return {"type": "tool_call", "data": {
                "toolName": data.get("tool_name", ""),
                "toolInput": data.get("tool_input"),
            }}
        elif event_type == "tool_result":
            return {"type": "tool_result", "data": {
                "toolName": data.get("tool_name", ""),
                "toolResult": data.get("tool_result", ""),
                "success": not data.get("is_error", False),
            }}
        elif event_type == "output_file":
            return {"type": "output_file", "data": {
                "fileId": data.get("file_id", ""),
                "filename": data.get("filename", ""),
                "size": data.get("size", 0),
                "contentType": data.get("content_type", ""),
                "downloadUrl": data.get("download_url", ""),
                "description": data.get("description"),
            }}
        elif event_type == "ask_user":
            return {"type": "ask_user", "data": {
                "promptId": data.get("prompt_id", ""),
                "question": data.get("question", ""),
                "options": data.get("options"),
            }}
        elif event_type == "complete":
            return {"type": "complete", "data": {
                "success": data.get("success", False),
                "answer": data.get("answer"),
                "totalTurns": data.get("total_turns", 0),
                "totalInputTokens": data.get("total_input_tokens"),
                "totalOutputTokens": data.get("total_output_tokens"),
            }}
        elif event_type == "error":
            return {"type": "error", "data": {
                "message": data.get("message", data.get("error", "")),
            }}
        elif event_type == "steering_received":
            return {"type": "steering_received", "data": {
                "message": data.get("message", ""),
            }}
        return None

    def _flush_text_buffer(self):
        """Flush accumulated text_delta chunks as an assistant StreamEventRecord."""
        if self._text_buffer:
            self._current_events.append({"type": "assistant", "data": {
                "content": self._text_buffer,
            }})
            self._text_buffer = ""

    def _flush_assistant(self):
        """Flush accumulated events as an assistant ChatMessage."""
        self._flush_text_buffer()
        if self._current_events:
            self._messages.append({
                "role": "assistant",
                "content": "",
                "streamEvents": self._current_events,
            })
            self._current_events = []

    def get_messages(self) -> list:
        """Get finalized display messages (flushes current assistant).

        This is a finalizing call — it flushes pending events into an assistant
        message.  Safe to call multiple times (idempotent after flush), but do
        NOT call add_event() after get_messages() and expect those events to
        merge into the same assistant block.
        """
        self._flush_assistant()
        return list(self._messages)

    def get_snapshot(self) -> list:
        """Get current state including in-progress assistant (for checkpoints)."""
        result = list(self._messages)
        # Include both accumulated events and any buffered text
        pending_events = list(self._current_events)
        if self._text_buffer:
            pending_events.append({"type": "assistant", "data": {
                "content": self._text_buffer,
            }})
        if pending_events:
            result.append({
                "role": "assistant",
                "content": "",
                "streamEvents": pending_events,
            })
        return result

    @classmethod
    def from_agent_result(cls, result, request_text: str, uploaded_files=None) -> "DisplayMessageBuilder":
        """Build display messages from a non-streaming AgentResult.

        NOTE: This builds StreamEventRecords directly (bypassing add_event /
        _map_to_record) because AgentResult.steps have a different shape than
        live SSE events.  If new event types are added to _map_to_record, they
        won't automatically appear here — update both paths.
        """
        builder = cls()
        builder.add_user_message(request_text, uploaded_files)
        # Build events from result.steps
        for step in (result.steps or []):
            if step.tool_name == "ask_user":
                builder._current_events.append({"type": "tool_call", "data": {
                    "toolName": "ask_user",
                    "toolInput": step.tool_input,
                }})
                builder._current_events.append({"type": "ask_user", "data": {
                    "promptId": "",
                    "question": (step.tool_input or {}).get("question", ""),
                    "options": (step.tool_input or {}).get("options"),
                }})
            elif step.tool_name:
                # AgentStep doesn't carry an is_error flag, so infer failure
                # from the step content containing common error markers.
                content = step.content or ""
                is_error = (
                    step.role == "tool"
                    and content.lstrip().startswith(("{\"error\"", "Error:", "Traceback"))
                )
                builder._current_events.append({"type": "tool_call", "data": {
                    "toolName": step.tool_name,
                    "toolInput": step.tool_input,
                }})
                builder._current_events.append({"type": "tool_result", "data": {
                    "toolName": step.tool_name,
                    "toolResult": (content[:5000] if content else ""),
                    "success": not is_error,
                }})
            elif step.content:
                builder._current_events.append({"type": "assistant", "data": {
                    "content": step.content,
                }})
        # Add complete event
        builder._current_events.append({"type": "complete", "data": {
            "success": result.success,
            "answer": result.answer,
            "totalTurns": result.total_turns,
            "totalInputTokens": result.total_input_tokens,
            "totalOutputTokens": result.total_output_tokens,
        }})
        return builder
