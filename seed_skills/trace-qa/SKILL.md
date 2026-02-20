---
name: trace-qa
description: >
  Analyze and answer questions about agent execution traces. Use this skill when
  the user asks about a trace, wants to debug a failed agent run, understand what
  an agent did, analyze token usage or efficiency, or asks "what happened in trace X".
  Triggers: trace analysis, trace debugging, trace QA, execution review, agent run review.
---

# Trace QA

Analyze agent execution traces to answer questions about what happened, why it failed,
how efficient it was, or any other aspect of the run.

## Workflow

Always start with `overview` to understand the trace before diving into details.

### 1. Get the overview first

```bash
python scripts/fetch_trace.py <trace_id> overview
```

This returns metadata (status, duration, tokens, model) and summaries (request, answer preview, tool usage counts). Use this to orient yourself before going deeper.

### 2. Explore steps or LLM calls as needed

Depending on the user's question, drill into the relevant data:

| User wants to know... | Command |
|------------------------|---------|
| What tools were called and in what order | `steps [start] [count]` |
| Full input/output of a specific tool call | `step <N>` |
| How many LLM calls and their token costs | `llm-calls [start] [count]` |
| What messages were sent to Claude in a specific turn | `llm-call <N>` |
| Just the final result | `answer` |

### 3. Handle long content with segmented reads

When content is large, the script automatically segments output to ~4000 characters.
If you see a `[CONTINUED: ...]` message at the end of output, call the command shown
in that message to read the next segment. Repeat until all content is read.

Example sequence:
```bash
python scripts/fetch_trace.py <id> step 5
# Output ends with: [CONTINUED: use 'step 5 --offset 4000' for next segment]

python scripts/fetch_trace.py <id> step 5 --offset 4000
# Output ends with: [CONTINUED: use 'step 5 --offset 8000' for next segment]

python scripts/fetch_trace.py <id> step 5 --offset 8000
# Full content now read
```

## Command Reference

| Mode | Syntax | Description |
|------|--------|-------------|
| `overview` | `fetch_trace.py <id> overview` | Metadata + summary stats |
| `steps` | `fetch_trace.py <id> steps [start] [count]` | Paginated step list (default: 30/page) |
| `step` | `fetch_trace.py <id> step <N> [--offset <chars>]` | Single step full content |
| `llm-calls` | `fetch_trace.py <id> llm-calls [start] [count]` | Paginated LLM call list |
| `llm-call` | `fetch_trace.py <id> llm-call <N> [--offset <chars>]` | Single LLM call full content |
| `answer` | `fetch_trace.py <id> answer` | Final answer only |

## Common Analysis Patterns

**Failure diagnosis:** overview → find error → steps list → examine failing step detail

**Token efficiency:** overview (total tokens) → llm-calls list (per-call breakdown) → identify expensive calls

**Behavior understanding:** overview → steps list → step details for key tool calls

**Tool usage audit:** overview (tool summary) → steps list filtered by tool name

## Environment

Set `API_BASE_URL` to override the default API endpoint (`http://127.0.0.1:62610`).
