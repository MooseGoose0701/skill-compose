# Skills API MCP Integration Guide

## Overview

This guide explains how to integrate MCP servers with the Skills API project. The project uses a specific configuration format and only supports stdio transport.

**⚠️ IMPORTANT: After creating an MCP server, you MUST register it in `config/mcp.json` for it to be available. This is a required step, not optional.**

---

## Quick Checklist

1. ✅ Create MCP server code (Phase 1-3)
2. ✅ Build with `npm run build` or equivalent
3. ✅ **Register in `config/mcp.json`** (Phase 4 - REQUIRED)
4. ✅ Restart API server
5. ✅ Test in Agent Chat

---

## Configuration Format

MCP servers are configured in `config/mcp.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "name": "My Server",
      "description": "Description for Agent to understand when to use this server",
      "command": "node",
      "args": ["./path/to/dist/index.js"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      },
      "defaultEnabled": false,
      "tools": [
        {
          "name": "my_tool",
          "description": "Tool description for Agent",
          "inputSchema": {
            "type": "object",
            "properties": {
              "param1": {
                "type": "string",
                "description": "Parameter description"
              }
            },
            "required": ["param1"]
          }
        }
      ]
    }
  }
}
```

### Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name shown in UI |
| `description` | Yes | Helps Agent understand when to use this server |
| `command` | Yes | Command to run (e.g., `node`, `python`, `uvx`) |
| `args` | Yes | Command arguments (path to server script) |
| `env` | No | Environment variables. Use `${VAR_NAME}` for secrets |
| `defaultEnabled` | No | If true, enabled by default in Agent Chat |
| `tools` | Yes | Pre-declared tool definitions for the Agent |

### Tools Array

Each tool must be pre-declared with:
- `name`: Tool name (snake_case)
- `description`: What the tool does
- `inputSchema`: JSON Schema for parameters

**Important**: The tools array must match what your MCP server actually implements.

---

## Integration Checklist

### 1. Create MCP Server

```bash
# TypeScript project structure
my-mcp-server/
├── package.json
├── tsconfig.json
├── src/
│   └── index.ts
└── dist/
    └── index.js
```

### 2. Implement with stdio Transport

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "my-mcp-server",
  version: "1.0.0"
}, {
  capabilities: { tools: {} }
});

// Register tools...

const transport = new StdioServerTransport();
await server.connect(transport);
```

### 3. Build the Server

```bash
cd my-mcp-server
npm install
npm run build  # Compiles to dist/index.js
```

### 4. Auto-Register in config/mcp.json (REQUIRED)

**This step is mandatory.** The MCP server won't be available until it's registered in the config.

**Step 4.1: Read current config**
```bash
cat config/mcp.json
```

**Step 4.2: Generate tool definitions**

For each tool in your MCP server, create a matching entry:
```json
{
  "name": "tool_name",
  "description": "What the tool does",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param1": {"type": "string", "description": "..."},
      "param2": {"type": "number", "description": "..."}
    },
    "required": ["param1"]
  }
}
```

**Step 4.3: Write updated config**

Use a heredoc to write the complete updated config:
```bash
cat > config/mcp.json << 'EOF'
{
  "mcpServers": {
    "fetch": { ... existing ... },
    "time": { ... existing ... },
    "my-new-server": {
      "name": "My New Server",
      "description": "Description for Agent",
      "command": "node",
      "args": ["./my-mcp-server/dist/index.js"],
      "env": {},
      "defaultEnabled": false,
      "tools": [
        {
          "name": "my_tool",
          "description": "...",
          "inputSchema": { ... }
        }
      ]
    }
  }
}
EOF
```

**Important**: The tools array in config MUST match the tools implemented in your server.

### 5. Restart API

```bash
# Docker
docker compose restart api

# Local development
# Restart uvicorn
```

### 6. Verify in UI

1. Open http://localhost:62600
2. Go to MCP page or Agent Chat
3. Check that your server appears in the list
4. Enable it and test

---

## Example: Gemini MCP Server

**Config**:
```json
{
  "gemini": {
    "name": "Gemini AI",
    "description": "Google Gemini multimodal AI for image analysis",
    "command": "node",
    "args": ["./gemini-mcp-server/dist/index.js"],
    "env": {
      "GEMINI_API_KEY": "${GEMINI_API_KEY}"
    },
    "defaultEnabled": false,
    "tools": [
      {
        "name": "gemini_analyze_image",
        "description": "Analyze an image using Gemini AI",
        "inputSchema": { ... }
      }
    ]
  }
}
```

**Key patterns from gemini-mcp-server:**
- Uses `@modelcontextprotocol/sdk` for server
- stdio transport only
- JSON responses with structured data
- Error handling returns `isError: true`

---

## Environment Variables

For secrets (API keys), use the `${VAR_NAME}` syntax in the config:

```json
"env": {
  "API_KEY": "${MY_API_KEY}"
}
```

Set the actual value in:
- `.env` file (local development)
- `docker/.env` file (Docker deployment)

---

## Transport: stdio Only

This project only supports **stdio transport**. Do not use:
- Streamable HTTP transport
- SSE transport
- WebSocket transport

The MCP client communicates with servers via subprocess stdin/stdout.

---

## Debugging

### Check if server starts
```bash
node ./my-mcp-server/dist/index.js
# Should output to stderr, not crash
```

### Check API logs
```bash
docker logs skills-api --tail 50
```

### Test via API
```bash
curl http://localhost:62610/api/v1/mcp/servers
```

---

## Common Issues

### Server not appearing
- Check `config/mcp.json` syntax (valid JSON)
- Restart API after config changes
- Check API logs for errors

### Tools not working
- Ensure `tools` array matches server implementation
- Check environment variables are set
- Verify server can be executed standalone

### Environment variables not working
- Use `${VAR_NAME}` syntax in config
- Set actual values in `.env` file
- Docker: set in `docker/.env`
