---
sidebar_position: 2
---

# Agent Memory

Agent memory gives agents the ability to remember information across sessions. Without memory, agents forget everything when context is compressed or a conversation ends. The memory system has two layers: **file-based bootstrap memory** loaded into every session, and **DB-backed memory entries** searchable via vector similarity.

## Architecture Overview

```
                          System Prompt
                              │
                    ┌─────────┴──────────┐
                    │  ## Agent Memory    │
                    │  ┌───────────────┐  │
                    │  │ SOUL.md       │  │  ← persona, tone
                    │  │ USER.md       │  │  ← user preferences
                    │  │ MEMORY.md     │  │  ← curated facts
                    │  │ memory/*.md   │  │  ← daily logs
                    │  └───────────────┘  │
                    │  ### Memory Recall  │  ← search directive
                    └────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         Normal Turn    Memory Tools     Flush Turn
         (read-only)    (runtime CRUD)   (pre-compression)
              │               │               │
              │          ┌────┴────┐     ┌────┴────┐
              │          │ search  │     │ read    │
              │          │ save    │     │ write   │
              │          │ get     │     │ (scoped)│
              │          └────┬────┘     └────┬────┘
              │               │               │
              │          PostgreSQL       Filesystem
              │          + pgvector      agents/{id}/
              │               │               │
              └───────────────┴───────────────┘
```

## File-Based Memory (Bootstrap Files)

Bootstrap files are markdown files loaded into the system prompt at the start of every agent session. They provide persistent context that the agent always has access to.

### Files

| File | Purpose | Example Content |
|------|---------|-----------------|
| `SOUL.md` | Agent persona, tone, behavior | "You are a senior staff engineer. Be direct and concise." |
| `USER.md` | User preferences and habits | "User prefers dark mode, Python, and code over prose." |
| `MEMORY.md` | Curated long-term facts | "Project migrated from REST to gRPC on March 10." |
| `memory/YYYY-MM-DD.md` | Daily session logs | Progress notes, decisions, TODOs from each day |

### Directory Structure

```
memory/
├── global/              # Shared across all agents
│   ├── SOUL.md
│   ├── USER.md
│   └── MEMORY.md
└── agents/
    └── {agent-id}/      # Per-agent (overrides global)
        ├── SOUL.md
        ├── USER.md
        ├── MEMORY.md
        └── memory/
            ├── 2026-03-01.md
            └── 2026-03-02.md
```

**Override logic:** Per-agent files take precedence over global files of the same name. If an agent has its own `SOUL.md`, the global `SOUL.md` is ignored for that agent.

### Truncation

Large files are truncated to prevent system prompt bloat:

| Limit | Value |
|-------|-------|
| Per-file limit | 20,000 chars |
| Total limit (all files) | 60,000 chars |
| Head ratio | 70% (kept from start) |
| Tail ratio | 20% (kept from end) |

When a file exceeds its limit, it's split into head + truncation marker + tail:

```
[first 70% of content]
…(truncated MEMORY.md: kept 14000+4000 of 25000 chars)…
[last 20% of content]
```

### Daily Log Loading

At session start, the two most recent daily logs are loaded automatically:
- `memory/YYYY-MM-DD.md` (today, UTC)
- `memory/YYYY-MM-DD.md` (yesterday, UTC)

This provides continuity between sessions without unbounded growth.

## System Prompt Injection

Bootstrap files are injected into the system prompt via `_build_memory_section()`. The resulting section looks like:

```markdown
## Agent Memory

If SOUL.md is present, embody its persona and tone. Avoid stiff,
generic replies; follow its guidance unless higher-priority
instructions override it.

### SOUL.md
[file content]

### USER.md
[file content]

### MEMORY.md
[file content]

### memory/2026-03-02.md
[file content]

### Memory Recall
Before answering anything about prior work, decisions, dates,
people, preferences, or todos: run memory_search on MEMORY.md +
memory/*.md; then use memory_get to pull only the needed lines.
If low confidence after search, say you checked.

Citations: include Source: <path#line> when it helps the user
verify memory snippets.
```

The SOUL.md persona instruction only appears when SOUL.md exists. The Memory Recall directive only appears when the agent has an `agent_id` (memory tools available).

## Memory Flush (Autonomous Persistence)

The memory flush is a **silent, fire-and-forget agent turn** that runs before context compression. It gives the LLM scoped read/write tools to persist important information from the conversation to memory files.

### When It Triggers

The flush fires when context compression is needed — i.e., when input tokens exceed 70% of the model's context window limit. Only agents with an `agent_id` get memory flush.

### How It Works

```
1. Compression threshold reached
2. Snapshot last 20 messages at call site
3. asyncio.create_task() → fire-and-forget
4. Compression proceeds concurrently
5. Flush LLM decides what to remember
6. Writes to SOUL.md / USER.md / MEMORY.md / memory/*.md
7. NO_REPLY if nothing to store
```

### Flush Prompts

**System prompt** (appended to agent's own system prompt):

> Pre-compaction memory flush turn. The session is near auto-compaction; capture durable memories to disk. You may reply, but usually NO_REPLY is correct.

**User prompt** (with placeholders filled):

> Pre-compaction memory flush. Store durable memories now:
> - SOUL.md for persona, tone, and behavior instructions
> - USER.md for user preferences, habits, and background
> - MEMORY.md for curated long-term facts worth remembering
> - memory/{date}.md for session-specific progress and decisions
>
> Create memory/ directory if needed. IMPORTANT: If a file already exists, READ it first, then WRITE with new content appended — do not overwrite existing entries. If nothing to store, reply with NO_REPLY.
>
> Existing files:
> {list of files with sizes}
>
> Current time: 2026-03-02 14:30:00 UTC

### Scoped Tools

The flush turn gets **only two tools** — dedicated read/write schemas restricted to the agent's memory directory:

| Tool | Input | Returns |
|------|-------|---------|
| `read` | `file_path` (relative, e.g. `SOUL.md`) | `{"content": "..."}` or `{"error": "..."}` |
| `write` | `file_path`, `content` | `{"success": true, "path": "..."}` or `{"error": "..."}` |

Path traversal is blocked — any path resolving outside the agent's memory directory returns an access denied error.

### Constraints

| Parameter | Value |
|-----------|-------|
| Max turns | 3 |
| Messages passed | Last 20 (sliced at call site to avoid exceeding context) |
| Execution | Fire-and-forget (`asyncio.create_task`) |
| Error handling | Logged but non-fatal |
| NO_REPLY detection | Exact match: `^\s*NO_REPLY\s*$` |

## DB-Backed Memory Entries

For structured, searchable memory, entries are stored in PostgreSQL with pgvector embeddings.

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `agent_id` | UUID (nullable) | `NULL` = global memory |
| `content` | TEXT | Memory text (max 4096 chars) |
| `category` | VARCHAR | `fact`, `preference`, `procedure`, `context`, `session_summary` |
| `source` | VARCHAR | `manual`, `auto_flush`, `agent_tool`, `session_end` |
| `embedding` | vector(1536) | pgvector embedding for semantic search |
| `embedding_model` | VARCHAR | e.g. `text-embedding-3-small` |
| `session_id` | UUID (nullable) | Optional session association |
| `created_at` | TIMESTAMP(TZ) | UTC |
| `updated_at` | TIMESTAMP(TZ) | UTC |

### Search

Two search modes with automatic fallback:

1. **Vector search** (when embedding API key is configured):
   - Query is embedded via OpenAI `text-embedding-3-small`
   - Cosine similarity via pgvector `<=>` operator
   - Returns results ranked by similarity (0–1)

2. **Keyword fallback** (when no embedding API key):
   - Case-insensitive `ILIKE` search
   - Ordered by `created_at DESC`

## Memory Tools (Runtime)

During normal conversation, agents with an `agent_id` get three memory tools:

### memory_search

Search memory entries by semantic similarity.

```json
{
  "query": "What date did we start the gRPC migration?",
  "top_k": 5
}
```

Returns matching entries with similarity scores.

### memory_save

Save new information to long-term memory.

```json
{
  "content": "User prefers FastAPI over Flask for all new projects.",
  "category": "preference"
}
```

Categories: `fact`, `preference`, `procedure`, `context`.

### memory_get

Read a memory file by relative path, optionally with line range.

```json
{
  "path": "memory/2026-03-02.md",
  "from_line": 10,
  "lines": 20
}
```

Returns file content or error if not found.

## API Endpoints

### Bootstrap Files

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/memory/files?agent_id={id}` | List files with metadata |
| `GET` | `/memory/files/{scope}/{filename}` | Read file content |
| `PUT` | `/memory/files/{scope}/{filename}` | Write file content |
| `DELETE` | `/memory/files/{scope}/{filename}` | Delete file |

`scope` is either `"global"` or an agent UUID. `filename` is one of `SOUL.md`, `USER.md`, `MEMORY.md`.

### Memory Entries

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/memory/entries?agent_id={id}&category={cat}&limit=50` | List entries |
| `POST` | `/memory/entries` | Create entry |
| `PUT` | `/memory/entries/{entry_id}` | Update entry |
| `DELETE` | `/memory/entries/{entry_id}` | Delete entry |
| `POST` | `/memory/search` | Semantic search |

## Frontend

The Memory tab on the agent detail page provides two sections:

### Bootstrap File Editor

- Tab interface for SOUL.md / USER.md / MEMORY.md
- Scope toggle: Global vs Agent-specific
- Monospace editor with save/delete actions
- Dirty state indicator

### Memory Entries List

- Search bar with semantic search
- Category badges (color-coded)
- Similarity score display (when searching)
- Add/delete entries with confirmation dialogs
