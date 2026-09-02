---
sidebar_position: 3
---

# Configuration

Environment variables, configuration files, and system settings.

## Environment Variables

Set these in your `.env` file (root directory for local dev, `docker/.env` for Docker).

### LLM API Keys

At least one is required.

| Variable | Provider | Required |
|----------|----------|----------|
| `MOONSHOT_API_KEY` | Moonshot (Kimi K2.5) | No* |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) | No* |
| `OPENAI_API_KEY` | OpenAI (GPT-4o) | No* |
| `GOOGLE_API_KEY` | Google (Gemini) | No* |
| `DEEPSEEK_API_KEY` | DeepSeek | No* |
| `OPENROUTER_API_KEY` | OpenRouter (multiple providers) | No* |
| `ATLASCLOUD_API_KEY` | Atlas Cloud | No* |

*At least one API key is required.

### MCP Server Keys

| Variable | Used By | Required |
|----------|---------|----------|
| `TAVILY_API_KEY` | Tavily MCP server | No |
| `GEMINI_API_KEY` | Gemini MCP server | No |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_USER` | `skills` | PostgreSQL username |
| `DB_PASSWORD` | `skills123` | PostgreSQL password |
| `DB_NAME` | `skills_api` | Database name |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |

:::note Docker Database
In Docker, `DB_HOST` is automatically set to the `db` container name. You only need to set `DB_USER`, `DB_PASSWORD`, and `DB_NAME`.
:::

### Service Ports

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `62610` | Backend API port |
| `WEB_PORT` | `62600` | Frontend web port |

### Other

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `UTC` | Timezone |
| `LOG_LEVEL` | `info` | Logging level |

## Configuration Files

### config/mcp.json

MCP server definitions. See [MCP concepts](/concepts/mcp) for the full format.

```json
{
  "mcpServers": {
    "server-name": {
      "name": "Display Name",
      "description": "What it does",
      "command": "node",
      "args": ["./server/dist/index.js"],
      "env": {"KEY": "${ENV_VAR}"},
      "defaultEnabled": false,
      "tools": [{"name": "tool_name", "description": "..."}]
    }
  }
}
```

### .env.custom.keys

Tracks which environment variables were added via the UI (vs preset in `.env`). Used by the Environment page to categorize variables as "Custom" or "Preset".

### docker/docker-compose.yaml

Docker service definitions. Modified automatically when custom executors are registered or deleted.

## Managing Environment Variables

### Initial Setup

Edit `docker/.env` (Docker) or `.env` (local dev) before first startup:

```bash
# Docker
cd docker
cp .env.example .env
vim .env          # Add API keys
docker compose up -d

# Local development
cp .env.example .env
vim .env
```

### After Initial Setup

Once the system is running, environment variables are managed through `config/.env` (Docker: `docker/volumes/config/.env`). There are three ways to modify them:

### Via Web UI (Recommended)

Navigate to **Environment** (`/environment`):

- View all variables (sensitive values are masked)
- Add, edit, or delete variables
- Changes apply immediately and persist across restarts

### Via Host File

```bash
# Docker — edit the persistent config file directly
vim docker/volumes/config/.env
docker compose restart  # Restart to apply

# Local development
vim config/.env   # Or .env in project root
```

:::info Docker .env Architecture
On first startup, `docker/.env` is copied to `config/.env` (Docker volume) as a seed. After that, `config/.env` is the single source of truth — the Settings page and `load_dotenv` both read/write this file. Editing `docker/.env` after first startup has no effect on running configuration.
:::

### Via API

```bash
# List all
curl http://localhost:62610/api/v1/settings/env

# Add
curl -X POST http://localhost:62610/api/v1/settings/env \
  -H "Content-Type: application/json" \
  -d '{"key": "MY_VAR", "value": "my-value"}'

# Update
curl -X PUT http://localhost:62610/api/v1/settings/env \
  -H "Content-Type: application/json" \
  -d '{"key": "MY_VAR", "value": "new-value"}'

# Delete
curl -X DELETE http://localhost:62610/api/v1/settings/env/MY_VAR
```

## Data Directories

| Directory | Purpose | Docker Volume |
|-----------|---------|---------------|
| `skills/` | Skill files on disk | `./volumes/skills` |
| `config/` | Configuration files | `./volumes/config` |
| `logs/` | Agent execution logs | `./volumes/logs` |
| `uploads/` | User-uploaded files | `./volumes/uploads` |
| `data/` | Local development data | — |

## Related

- [Development Setup](/development-setup) — Setup guide
- [Models](/concepts/models) — LLM provider details
- [MCP](/concepts/mcp) — MCP server configuration
- [API Reference](/reference/api) — Complete endpoint documentation
