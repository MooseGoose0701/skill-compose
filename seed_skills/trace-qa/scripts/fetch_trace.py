#!/usr/bin/env python3
"""
Fetch and display agent execution traces in segmented views.

Traces can be very large (hundreds of steps, each with long tool results).
This script provides multiple viewing modes with automatic pagination
and content segmentation to avoid overwhelming the context window.

Usage:
    fetch_trace.py <trace_id> overview
    fetch_trace.py <trace_id> steps [start] [count]
    fetch_trace.py <trace_id> step <index> [--offset <chars>]
    fetch_trace.py <trace_id> llm-calls [start] [count]
    fetch_trace.py <trace_id> llm-call <index> [--offset <chars>]
    fetch_trace.py <trace_id> answer

Examples:
    fetch_trace.py abc123 overview
    fetch_trace.py abc123 steps 0 10
    fetch_trace.py abc123 step 3
    fetch_trace.py abc123 step 3 --offset 4000
    fetch_trace.py abc123 llm-calls
    fetch_trace.py abc123 llm-call 0
    fetch_trace.py abc123 answer
"""

import json
import os
import sys
import urllib.request
import urllib.error

SEGMENT_SIZE = 4000       # Max chars per detail output segment
LIST_PAGE_SIZE = 30       # Default items per page in list modes
PREVIEW_CHARS = 120       # Content preview length in list modes

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:62610")


def fetch_trace(trace_id: str) -> dict:
    """Fetch trace data from the API."""
    url = f"{API_BASE_URL}/api/v1/traces/{trace_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: Trace '{trace_id}' not found.", file=sys.stderr)
        else:
            print(f"Error: HTTP {e.code} fetching trace.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Cannot connect to API at {API_BASE_URL}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def format_overview(trace: dict) -> str:
    """Format trace metadata and summary statistics."""
    steps = trace.get("steps") or []
    llm_calls = trace.get("llm_calls") or []

    # Count tool calls by name
    tool_counts: dict[str, int] = {}
    for s in steps:
        name = s.get("tool_name")
        if name:
            tool_counts[name] = tool_counts.get(name, 0) + 1

    # Duration
    duration_ms = trace.get("duration_ms")
    if duration_ms is not None:
        if duration_ms >= 60000:
            duration_str = f"{duration_ms / 60000:.1f}m"
        elif duration_ms >= 1000:
            duration_str = f"{duration_ms / 1000:.1f}s"
        else:
            duration_str = f"{duration_ms}ms"
    else:
        duration_str = "N/A"

    lines = [
        "=== TRACE OVERVIEW ===",
        f"ID:             {trace.get('id', 'N/A')}",
        f"Status:         {trace.get('status', 'N/A')}",
        f"Success:        {trace.get('success', 'N/A')}",
        f"Model:          {trace.get('model', 'N/A')}",
        f"Created:        {trace.get('created_at', 'N/A')}",
        f"Duration:       {duration_str}",
        f"Total turns:    {trace.get('total_turns', 0)}",
        f"Input tokens:   {trace.get('total_input_tokens', 0):,}",
        f"Output tokens:  {trace.get('total_output_tokens', 0):,}",
        f"Total steps:    {len(steps)}",
        f"Total LLM calls:{len(llm_calls)}",
        f"Skills used:    {', '.join(trace.get('skills_used') or []) or 'none'}",
        "",
        "--- Request ---",
        truncate(trace.get("request", ""), 500),
        "",
        "--- Answer (preview) ---",
        truncate(trace.get("answer") or "(no answer)", 500),
    ]

    if trace.get("error"):
        lines.extend(["", "--- Error ---", trace["error"]])

    if tool_counts:
        lines.extend(["", "--- Tool Usage Summary ---"])
        for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: {count}")

    return "\n".join(lines)


def format_steps(trace: dict, start: int, count: int) -> str:
    """Format paginated step list with summaries."""
    steps = trace.get("steps") or []
    total = len(steps)

    if total == 0:
        return "No steps recorded in this trace."

    end = min(start + count, total)
    if start >= total:
        return f"Start index {start} is out of range (total steps: {total})."

    lines = [f"=== STEPS [{start}-{end - 1}] of {total} total ===", ""]

    for i in range(start, end):
        s = steps[i]
        role = s.get("role", "?")
        tool_name = s.get("tool_name", "")

        if role == "assistant":
            content = s.get("content", "")
            preview = truncate(content, PREVIEW_CHARS)
            lines.append(f"[{i}] assistant: {preview}")
        elif tool_name:
            tool_input = s.get("tool_input") or {}
            result = s.get("tool_result") or s.get("content") or ""
            input_preview = truncate(json.dumps(tool_input, ensure_ascii=False), PREVIEW_CHARS)
            result_preview = truncate(str(result), PREVIEW_CHARS)
            lines.append(f"[{i}] tool:{tool_name}")
            lines.append(f"     input:  {input_preview}")
            lines.append(f"     result: {result_preview}")
        else:
            content = s.get("content", "")
            lines.append(f"[{i}] {role}: {truncate(content, PREVIEW_CHARS)}")

        lines.append("")

    if end < total:
        lines.append(f"[CONTINUED: use 'steps {end} {count}' for next page]")

    return "\n".join(lines)


def format_step_detail(trace: dict, index: int, offset: int) -> str:
    """Format a single step's full content with offset-based segmentation."""
    steps = trace.get("steps") or []
    total = len(steps)

    if index < 0 or index >= total:
        return f"Step index {index} is out of range (total steps: {total})."

    s = steps[index]
    role = s.get("role", "?")
    tool_name = s.get("tool_name")

    # Build full content string
    parts = [f"=== STEP {index} of {total} ==="]
    parts.append(f"Role: {role}")
    if tool_name:
        parts.append(f"Tool: {tool_name}")

    if tool_name:
        tool_input = s.get("tool_input")
        if tool_input:
            parts.append("")
            parts.append("--- Input ---")
            parts.append(json.dumps(tool_input, indent=2, ensure_ascii=False))

        result = s.get("tool_result") or s.get("content") or ""
        if result:
            parts.append("")
            parts.append("--- Result ---")
            parts.append(str(result))
    else:
        content = s.get("content", "")
        if content:
            parts.append("")
            parts.append("--- Content ---")
            parts.append(content)

    full_text = "\n".join(parts)

    # Apply segmentation
    if offset > 0:
        full_text = full_text[offset:]
        if not full_text:
            return f"Offset {offset} is beyond end of step content."

    if len(full_text) > SEGMENT_SIZE:
        output = full_text[:SEGMENT_SIZE]
        next_offset = offset + SEGMENT_SIZE
        output += f"\n\n[CONTINUED: use 'step {index} --offset {next_offset}' for next segment]"
        return output

    return full_text


def format_llm_calls(trace: dict, start: int, count: int) -> str:
    """Format paginated LLM call list with summaries."""
    calls = trace.get("llm_calls") or []
    total = len(calls)

    if total == 0:
        return "No LLM calls recorded in this trace."

    end = min(start + count, total)
    if start >= total:
        return f"Start index {start} is out of range (total LLM calls: {total})."

    lines = [f"=== LLM CALLS [{start}-{end - 1}] of {total} total ===", ""]

    for i in range(start, end):
        c = calls[i]
        turn = c.get("turn", i)
        model = c.get("model", "?")
        stop = c.get("stop_reason", "?")
        inp = c.get("input_tokens", 0)
        out = c.get("output_tokens", 0)
        ts = c.get("timestamp", "")
        n_messages = len(c.get("request_messages") or [])
        n_blocks = len(c.get("response_content") or [])

        lines.append(f"[{i}] Turn {turn} | {model}")
        lines.append(f"     stop_reason: {stop} | tokens: {inp:,} in / {out:,} out")
        lines.append(f"     messages: {n_messages} | response blocks: {n_blocks}")
        if ts:
            lines.append(f"     timestamp: {ts}")
        lines.append("")

    if end < total:
        lines.append(f"[CONTINUED: use 'llm-calls {end} {count}' for next page]")

    return "\n".join(lines)


def format_llm_call_detail(trace: dict, index: int, offset: int) -> str:
    """Format a single LLM call's full content with offset-based segmentation."""
    calls = trace.get("llm_calls") or []
    total = len(calls)

    if index < 0 or index >= total:
        return f"LLM call index {index} is out of range (total: {total})."

    c = calls[index]

    parts = [f"=== LLM CALL {index} of {total} ==="]
    parts.append(f"Turn:         {c.get('turn', index)}")
    parts.append(f"Model:        {c.get('model', '?')}")
    parts.append(f"Stop reason:  {c.get('stop_reason', '?')}")
    parts.append(f"Input tokens: {c.get('input_tokens', 0):,}")
    parts.append(f"Output tokens:{c.get('output_tokens', 0):,}")
    parts.append(f"Timestamp:    {c.get('timestamp', 'N/A')}")

    # Request messages
    messages = c.get("request_messages") or []
    parts.append("")
    parts.append(f"--- Request Messages ({len(messages)}) ---")
    for j, msg in enumerate(messages):
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)
        parts.append(f"[msg {j}] {role}: {str(content)}")

    # Response content
    response = c.get("response_content") or []
    parts.append("")
    parts.append(f"--- Response Content ({len(response)} blocks) ---")
    parts.append(json.dumps(response, indent=2, ensure_ascii=False))

    full_text = "\n".join(parts)

    # Apply segmentation
    if offset > 0:
        full_text = full_text[offset:]
        if not full_text:
            return f"Offset {offset} is beyond end of LLM call content."

    if len(full_text) > SEGMENT_SIZE:
        output = full_text[:SEGMENT_SIZE]
        next_offset = offset + SEGMENT_SIZE
        output += f"\n\n[CONTINUED: use 'llm-call {index} --offset {next_offset}' for next segment]"
        return output

    return full_text


def format_answer(trace: dict) -> str:
    """Format only the final answer."""
    answer = trace.get("answer")
    if not answer:
        status = trace.get("status", "unknown")
        error = trace.get("error")
        if error:
            return f"No answer. Status: {status}\nError: {error}"
        return f"No answer recorded. Status: {status}"

    lines = [
        "=== FINAL ANSWER ===",
        "",
        answer,
    ]
    return "\n".join(lines)


def usage():
    print(__doc__.strip(), file=sys.stderr)
    sys.exit(1)


def parse_int_arg(args: list[str], index: int, default: int) -> int:
    """Parse an integer argument at the given index, or return default."""
    if index < len(args):
        try:
            return int(args[index])
        except ValueError:
            print(f"Error: Expected integer, got '{args[index]}'.", file=sys.stderr)
            sys.exit(1)
    return default


def parse_offset(args: list[str]) -> int:
    """Parse --offset flag from args."""
    for i, arg in enumerate(args):
        if arg == "--offset" and i + 1 < len(args):
            try:
                return int(args[i + 1])
            except ValueError:
                print(f"Error: --offset requires an integer, got '{args[i + 1]}'.", file=sys.stderr)
                sys.exit(1)
    return 0


def main():
    args = sys.argv[1:]

    if len(args) < 2:
        usage()

    trace_id = args[0]
    mode = args[1]

    trace = fetch_trace(trace_id)

    if mode == "overview":
        print(format_overview(trace))

    elif mode == "steps":
        start = parse_int_arg(args, 2, 0)
        count = parse_int_arg(args, 3, LIST_PAGE_SIZE)
        print(format_steps(trace, start, count))

    elif mode == "step":
        if len(args) < 3:
            print("Error: 'step' mode requires an index.", file=sys.stderr)
            sys.exit(1)
        index = parse_int_arg(args, 2, 0)
        offset = parse_offset(args)
        print(format_step_detail(trace, index, offset))

    elif mode == "llm-calls":
        start = parse_int_arg(args, 2, 0)
        count = parse_int_arg(args, 3, LIST_PAGE_SIZE)
        print(format_llm_calls(trace, start, count))

    elif mode == "llm-call":
        if len(args) < 3:
            print("Error: 'llm-call' mode requires an index.", file=sys.stderr)
            sys.exit(1)
        index = parse_int_arg(args, 2, 0)
        offset = parse_offset(args)
        print(format_llm_call_detail(trace, index, offset))

    elif mode == "answer":
        print(format_answer(trace))

    else:
        print(f"Error: Unknown mode '{mode}'.", file=sys.stderr)
        usage()


if __name__ == "__main__":
    main()
