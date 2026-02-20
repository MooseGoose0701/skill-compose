#!/usr/bin/env python3
"""
Extract detailed context for specific issues from traces.
Helps understand WHY a skill failed or performed poorly.

Usage:
    extract_issue_context.py <traces-file> --trace-id <id>
    extract_issue_context.py <traces-file> --failed
    extract_issue_context.py <traces-file> --high-turns
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any


def load_traces(path: str) -> List[Dict[str, Any]]:
    """Load traces from a JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]


def extract_conversation_flow(trace: Dict) -> str:
    """Extract the conversation flow from a trace in a readable format."""
    lines = []
    lines.append(f"Request: {trace.get('request', 'N/A')}")
    lines.append(f"Skills Used: {trace.get('skills_used', 'N/A')}")
    lines.append(f"Success: {trace.get('success', 'N/A')}")
    lines.append("-" * 50)

    steps = trace.get('steps', [])
    for i, step in enumerate(steps):
        role = step.get('role', 'unknown')

        if role == 'assistant':
            content = step.get('content', '')
            if content:
                lines.append(f"\n[Assistant] {content[:500]}{'...' if len(content) > 500 else ''}")
            tool_name = step.get('tool_name')
            if tool_name:
                lines.append(f"  -> Calling tool: {tool_name}")

        elif role == 'tool':
            tool_name = step.get('tool_name', 'unknown')
            tool_input = step.get('tool_input', {})
            tool_result = step.get('tool_result', '')

            lines.append(f"\n[Tool: {tool_name}]")
            lines.append(f"  Input: {json.dumps(tool_input, ensure_ascii=False)[:300]}")

            if isinstance(tool_result, str):
                result_preview = tool_result[:500] + ('...' if len(tool_result) > 500 else '')
            else:
                result_preview = json.dumps(tool_result, ensure_ascii=False)[:500]
            lines.append(f"  Result: {result_preview}")

            # Highlight errors
            if isinstance(tool_result, str) and ('error' in tool_result.lower() or 'failed' in tool_result.lower()):
                lines.append("  ⚠️ POTENTIAL ERROR IN RESULT")

    lines.append("-" * 50)
    lines.append(f"\nFinal Answer: {trace.get('answer', 'N/A')[:500]}")

    return "\n".join(lines)


def extract_llm_details(trace: Dict) -> str:
    """Extract LLM call details for debugging."""
    lines = []
    llm_calls = trace.get('llm_calls', [])

    for call in llm_calls:
        turn = call.get('turn', '?')
        stop_reason = call.get('stop_reason', 'unknown')
        input_tokens = call.get('input_tokens', 0)
        output_tokens = call.get('output_tokens', 0)

        lines.append(f"\n--- Turn {turn} ---")
        lines.append(f"Stop Reason: {stop_reason}")
        lines.append(f"Tokens: {input_tokens} in / {output_tokens} out")

        response_content = call.get('response_content', [])
        for item in response_content:
            if item.get('type') == 'text':
                text = item.get('text', '')[:300]
                lines.append(f"Response: {text}...")
            elif item.get('type') == 'tool_use':
                lines.append(f"Tool Call: {item.get('name')} -> {json.dumps(item.get('input', {}))[:200]}")

    return "\n".join(lines)


def find_failed_traces(traces: List[Dict]) -> List[Dict]:
    """Find all failed traces."""
    return [t for t in traces if not t.get('success', True)]


def find_high_turn_traces(traces: List[Dict], threshold: int = 5) -> List[Dict]:
    """Find traces with high turn counts."""
    return [t for t in traces if t.get('total_turns', 0) > threshold]


def main():
    parser = argparse.ArgumentParser(description='Extract detailed issue context from traces')
    parser.add_argument('traces_path', help='Path to traces JSON file')
    parser.add_argument('--trace-id', help='Extract specific trace by ID')
    parser.add_argument('--failed', action='store_true', help='Extract all failed traces')
    parser.add_argument('--high-turns', action='store_true', help='Extract high-turn traces')
    parser.add_argument('--turns-threshold', type=int, default=5, help='Threshold for high turns')
    parser.add_argument('--show-llm', action='store_true', help='Also show LLM call details')

    args = parser.parse_args()

    try:
        traces = load_traces(args.traces_path)
    except Exception as e:
        print(f"Error loading traces: {e}", file=sys.stderr)
        sys.exit(1)

    selected_traces = []

    if args.trace_id:
        selected_traces = [t for t in traces if t.get('id') == args.trace_id]
        if not selected_traces:
            print(f"No trace found with ID: {args.trace_id}", file=sys.stderr)
            sys.exit(1)
    elif args.failed:
        selected_traces = find_failed_traces(traces)
        if not selected_traces:
            print("No failed traces found.")
            sys.exit(0)
    elif args.high_turns:
        selected_traces = find_high_turn_traces(traces, args.turns_threshold)
        if not selected_traces:
            print(f"No traces with more than {args.turns_threshold} turns found.")
            sys.exit(0)
    else:
        print("Please specify --trace-id, --failed, or --high-turns", file=sys.stderr)
        sys.exit(1)

    for trace in selected_traces:
        print("=" * 70)
        print(f"TRACE: {trace.get('id', 'unknown')}")
        print("=" * 70)
        print(extract_conversation_flow(trace))

        if args.show_llm:
            print("\n" + "=" * 70)
            print("LLM CALL DETAILS")
            print("=" * 70)
            print(extract_llm_details(trace))

        print("\n")


if __name__ == "__main__":
    main()
