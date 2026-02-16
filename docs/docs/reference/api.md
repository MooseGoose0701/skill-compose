---
sidebar_position: 1
---

# API Reference

All endpoints are served from `http://localhost:62610` (configurable via `API_PORT`).

## Agent

### Run Agent

```
POST /api/v1/agent/run
```

Run an agent and return the complete result.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request` | string | Yes | User message |
| `preset_id` | string | No | Agent ID to use |
| `skill_ids` | string[] | No | Skills to enable |
| `builtin_tools` | string[] | No | Tools to enable (null = all) |
| `mcp_servers` | string[] | No | MCP servers to enable |
| `model_provider` | string | No | LLM provider |
| `model_name` | string | No | Model name |
| `max_turns` | int | No | Max conversation rounds (default: 60) |
| `uploaded_files` | object[] | No | Uploaded files (`file_id`, `filename`, `path`, `content_type`). Image files (e.g., `image/png`) are sent as vision input to models that support it; other files are passed as paths. |
| `system_prompt` | string | No | Custom system prompt |
| `executor_id` | string | No | Executor ID for code execution (custom mode only, ignored when `preset_id` is set) |

**Response:** JSON with `answer`, `trace_id`, `steps`, `token_usage`, `duration`.

### Run Agent (Streaming)

```
POST /api/v1/agent/run/stream
```

Same request body as `/run`. Returns Server-Sent Events (SSE) with event types:

| Event | Description |
|-------|-------------|
| `run_started` | Contains `trace_id` |
| `turn_start` | New agent turn started |
| `text_delta` | Incremental text chunk from LLM (token-level streaming) |
| `tool_call` | Tool call started |
| `tool_result` | Tool call result |
| `output_file` | Auto-detected output file (`file_id`, `filename`, `size`, `content_type`, `download_url`) |
| `steering_received` | Steering message was injected by the user |
| `context_compressed` | History was compressed |
| `complete` | Agent finished (`answer`, `success`, `total_turns`, `skills_used`) |
| `trace_saved` | Trace saved to database |
| `error` | Error occurred |

Text arrives incrementally via `text_delta` events as the LLM generates tokens, enabling real-time display. Accumulate consecutive `text_delta` chunks to build the full assistant message. If the stream connection fails (e.g., API timeout), the system automatically retries with a non-streaming fallback.

### Steer Running Agent

```
POST /api/v1/agent/run/stream/{trace_id}/steer
```

Inject a steering message into a running agent stream. The agent picks up the message at the next tool boundary.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | Steering message (min 1 character) |

**Response:** `{"status": "injected", "trace_id": "..."}`

**Errors:**

| Code | Condition |
|------|-----------|
| `404` | No active run for this trace_id |
| `409` | Agent has already completed |
| `422` | Empty message |

**Multi-worker behavior:** If the stream runs on a different worker, the endpoint checks the database for a running trace and writes the message to a filesystem queue. The streaming worker polls the queue and injects the message.

---

## Skills

### List Skills

```
GET /api/v1/registry/skills
```

**Query Parameters:** `search`, `tags`, `category`, `skill_type` (`user` / `meta`), `sort_by` (`name` / `updated_at` / `created_at`), `sort_order` (`asc` / `desc`)

Pinned skills always appear first regardless of sort order.

### Get Skill

```
GET /api/v1/registry/skills/{name}
```

### Create Skill

```
POST /api/v1/registry/skills
```

Async operation. Returns `task_id` for polling.

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `description` | string | Yes |
| `prompt` | string | Yes |

### Delete Skill

```
DELETE /api/v1/registry/skills/{name}
```

Deletes the skill from the database and removes the disk directory.

### Export Skill

```
GET /api/v1/registry/skills/{name}/export
```

Returns a `.skill` (zip) file.

### Evolve Skill

```
POST /api/v1/registry/skills/{name}/evolve-via-traces
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_ids` | string[] | No* | Traces to analyze |
| `feedback` | string | No* | User feedback |

*At least one of `trace_ids` or `feedback` is required.

Async operation. Returns `task_id`.

### Sync Filesystem

```
POST /api/v1/registry/skills/{name}/sync-filesystem
```

Compares disk files with the database and creates a new version if different.

### Update Skill

```
PUT /api/v1/registry/skills/{name}
```

**Request Body:**

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Skill description |
| `tags` | string[] | Tags |
| `category` | string | Category (empty string clears it) |
| `status` | string | Status (`draft` / `active` / `deprecated`) |

### Toggle Pin

```
POST /api/v1/registry/skills/{name}/toggle-pin
```

Toggles the pinned state of a skill. Returns `{"name": "...", "is_pinned": true/false}`.

### List Categories

```
GET /api/v1/registry/categories
```

Returns a sorted list of distinct category strings (excludes meta skills).

### Update from GitHub

```
POST /api/v1/registry/skills/{name}/update-from-github
```

Pulls the latest version from the skill's recorded GitHub source.

### Update Version from Source

```
POST /api/v1/registry/skills/{name}/update-from-source-github
POST /api/v1/registry/skills/{name}/update-from-source-file
POST /api/v1/registry/skills/{name}/update-from-source-folder
```

Create a new version of an existing skill from an arbitrary GitHub URL, `.skill`/`.zip` file, or folder upload. Returns changes detected and the new version number, or a no-changes message if content is identical.

---

## Skill Versions

### List Versions

```
GET /api/v1/registry/skills/{name}/versions
```

### Get Version

```
GET /api/v1/registry/skills/{name}/versions/{version}
```

### Delete Version

```
DELETE /api/v1/registry/skills/{name}/versions/{version}
```

### Switch Version

```
POST /api/v1/registry/skills/{name}/switch-version
```

**Request Body:** `{"version": "0.0.2"}`

### Version Diff

```
GET /api/v1/registry/skills/{name}/diff?from_version=0.0.1&to_version=0.0.2
```

---

## Skill Import

### Import from File

```
POST /api/v1/registry/import
```

Multipart form upload of `.skill` or `.zip` file.

**Query Parameters:** `check_only` (boolean), `conflict_action` (`skip` / `copy`)

### Import from Folder

```
POST /api/v1/registry/import-folder
```

Multipart form upload of folder contents.

### Import from GitHub

```
POST /api/v1/registry/import-github
```

**Request Body:** `{"url": "https://github.com/owner/repo/tree/main/skills/my-skill"}`

### Import Local (Unregistered)

```
POST /api/v1/registry/import-local
```

**Request Body:** `{"skill_names": ["skill-a", "skill-b"]}`

### Detect Unregistered

```
GET /api/v1/registry/unregistered-skills
```

---

## Agents (Presets)

### List Agents

```
GET /api/v1/agents
```

**Query Parameters:** `is_system` (boolean)

### Get Agent

```
GET /api/v1/agents/{id}
GET /api/v1/agents/by-name/{name}
```

### Create Agent

```
POST /api/v1/agents
```

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `description` | string | No |
| `system_prompt` | string | No |
| `skill_ids` | string[] | No |
| `builtin_tools` | string[] | No |
| `mcp_servers` | string[] | No |
| `max_turns` | int | No |
| `model_provider` | string | No |
| `model_name` | string | No |
| `executor_id` | string | No |

### Update Agent

```
PUT /api/v1/agents/{id}
```

Same fields as create. System agents cannot be modified.

### Delete Agent

```
DELETE /api/v1/agents/{id}
```

System agents cannot be deleted.

### Publish

```
POST /api/v1/agents/{id}/publish
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_response_mode` | string | Yes | `"streaming"` or `"non_streaming"` |

Cannot publish system agents. Cannot re-publish without unpublishing first.

### Unpublish

```
POST /api/v1/agents/{id}/unpublish
```

Resets `api_response_mode` to `null`, allowing a different mode on re-publish.

---

## Published Agents

### Get Agent Info

```
GET /api/v1/published/{agent_id}
```

Returns public metadata for a published agent.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Agent ID |
| `name` | string | Agent name |
| `description` | string? | Agent description |
| `api_response_mode` | string? | `"streaming"` or `"non_streaming"` |

Returns `404` if the agent does not exist or is not published.

### Chat (Streaming)

```
POST /api/v1/published/{agent_id}/chat
```

SSE streaming chat. Only available when `api_response_mode` is `streaming` (returns `400` otherwise).

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request` | string | Yes | User message |
| `session_id` | string | No | Session ID for multi-turn. If provided and exists, loads history. If provided and new, creates session with that ID. If omitted, auto-generates a new session. |
| `uploaded_files` | object[] | No | Files to attach (`file_id`, `filename`, `path`, `content_type`) |

**SSE Event Types:**

| Event | Description |
|-------|-------------|
| `run_started` | Contains `trace_id` and `session_id` |
| `turn_start` | New agent turn started |
| `text_delta` | Incremental text chunk from LLM (token-level streaming) |
| `tool_call` | Tool call started |
| `tool_result` | Tool call result |
| `output_file` | Auto-detected output file |
| `steering_received` | Steering message was injected by the user |
| `complete` | Agent finished (`answer`, `success`, `total_turns`, `skills_used`) |
| `context_compressed` | History was compressed |
| `trace_saved` | Trace saved to database |
| `error` | Error occurred |

**Message persistence:** After the stream completes (unless cancelled), the agent's complete internal messages (including all `tool_use` and `tool_result` blocks) replace the session's messages array, preserving full context for subsequent turns.

### Chat (Non-Streaming)

```
POST /api/v1/published/{agent_id}/chat/sync
```

Synchronous chat. Only available when `api_response_mode` is `non_streaming` (returns `400` otherwise).

**Request Body:** Same as streaming chat above.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the agent completed successfully |
| `answer` | string | Agent's final answer |
| `total_turns` | int | Number of conversation turns |
| `steps` | object[] | Execution steps (`role`, `content`, `tool_name`, `tool_input`) |
| `error` | string? | Error message if failed |
| `trace_id` | string? | Trace ID for debugging |
| `session_id` | string? | Session ID (useful when auto-generated) |

**Message persistence:** When `success` is `true`, the agent's complete internal messages (including all `tool_use` and `tool_result` blocks) replace the session's messages array.

### Steer Published Agent

```
POST /api/v1/published/{agent_id}/chat/{trace_id}/steer
```

Inject a steering message into a running published agent stream. Same behavior as the [agent steer endpoint](#steer-running-agent).

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | Steering message (min 1 character) |

**Response:** `{"status": "injected", "trace_id": "..."}`

**Errors:** `404` (no active run), `409` (already completed), `422` (empty message).

### Get Session

```
GET /api/v1/published/{agent_id}/sessions/{session_id}
```

Returns the full message history for a session.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session ID |
| `agent_id` | string | Agent ID |
| `messages` | object[] | Full conversation messages in Anthropic API format. Each object has `role` and `content` (string or array of content blocks including `text`, `tool_use`, `tool_result`). |
| `created_at` | string | ISO 8601 timestamp |
| `updated_at` | string | ISO 8601 timestamp |

Returns `404` if the agent is not published or the session does not exist.

---

## Traces

### List Traces

```
GET /api/v1/traces
```

**Query Parameters:** `skill_name`, `preset_id`, `limit`, `offset`

### Get Trace

```
GET /api/v1/traces/{id}
```

### Delete Trace

```
DELETE /api/v1/traces/{id}
```

---

## MCP

### List MCP Servers

```
GET /api/v1/mcp/servers
```

### Create MCP Server

```
POST /api/v1/mcp/servers
```

### Update MCP Server

```
PUT /api/v1/mcp/servers/{name}
```

### Delete MCP Server

```
DELETE /api/v1/mcp/servers/{name}
```

### Discover Tools

```
POST /api/v1/mcp/servers/{name}/discover-tools
```

Spawns the MCP server process, queries `session.list_tools()`, and saves discovered tools to `config/mcp.json`.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether discovery succeeded |
| `server_name` | string | Server name |
| `tools` | object[] | Discovered tools (`name`, `description`, `inputSchema`) |
| `tools_count` | int | Number of tools found |
| `error` | string? | Error message if failed |

### Get/Set Secrets

```
GET /api/v1/mcp/servers/{name}/secrets
POST /api/v1/mcp/servers/{name}/secrets
```

---

## Executors

Executor endpoints are read-only (except kernel shutdown). Executors are predefined in `docker-compose.yaml` and their lifecycle is managed via Docker Compose profiles. Each executor uses a persistent IPython kernel per workspace for Python execution.

### List Executors

```
GET /api/v1/executors
```

Returns all executors with online/offline status (determined by HTTP health check).

### Get Executor

```
GET /api/v1/executors/{name}
```

### Health Check

```
GET /api/v1/executors/{name}/health
GET /api/v1/executors/health/all
```

### Shutdown Kernel (Executor Internal)

```
POST /kernel/shutdown?workspace_id={workspace_id}
```

Shuts down the IPython kernel for a specific workspace inside the executor container. Called internally during workspace cleanup.

---

## Files

### Upload

```
POST /api/v1/files/upload
```

Multipart form upload.

### File Info

```
GET /api/v1/files/{file_id}
```

### Download

```
GET /api/v1/files/{file_id}/download
```

---

## File Browser

### List Directory

```
GET /api/v1/browser/list?path=
```

### Preview File

```
GET /api/v1/browser/preview?path=
```

### Download File

```
GET /api/v1/browser/download?path=
```

### Download as Zip

```
GET /api/v1/browser/download-zip?path=
```

### Upload to Directory

```
POST /api/v1/browser/upload?path=
```

### Delete

```
DELETE /api/v1/browser/delete?path=
```

---

## Environment Variables

### List All

```
GET /api/v1/settings/env
```

### Create

```
POST /api/v1/settings/env
```

### Update

```
PUT /api/v1/settings/env
```

### Delete

```
DELETE /api/v1/settings/env/{key}
```

### Batch Update

```
PUT /api/v1/settings/env/batch
```

---

## Backup & Restore

### Create Backup

```
POST /api/v1/backup/create
```

**Query Parameters:** `include_env` (boolean)

Returns a zip file stream.

### List Backups

```
GET /api/v1/backup/list
```

### Download Backup

```
GET /api/v1/backup/download/{filename}
```

### Restore from Upload

```
POST /api/v1/backup/restore
```

Multipart form upload of zip file.

### Restore from Server

```
POST /api/v1/backup/restore/{filename}
```

---

## System Export / Import

### Export

```
POST /api/v1/system/export
```

Returns a zip file with skills and agents.

### Import

```
POST /api/v1/system/import
```

Multipart form upload. Skips existing items.

---

## Async Tasks

### Get Task Status

```
GET /api/v1/registry/tasks/{task_id}
```

**Response:**

```json
{
  "task_id": "uuid",
  "status": "running",
  "result": null,
  "error": null
}
```

Status values: `pending`, `running`, `completed`, `failed`.

---

## Health Check

```
GET /api/v1/health
```

Returns `{"status": "ok"}`.
