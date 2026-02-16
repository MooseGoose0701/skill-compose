---
sidebar_position: 1
---

# Agents

An agent is a saved configuration that combines a system prompt, skills, tools, MCP servers, a model, and a turn limit into a reusable unit. Select an agent in the chat panel to instantly apply its configuration.

## Agent Components

| Component | Description | Default |
|-----------|-------------|---------|
| **System Prompt** | Custom instructions for behavior | None |
| **Skills** | Domain knowledge the agent can access | skill-creator, skill-evolver, skill-updater |
| **Built-in Tools** | Actions the agent can perform | All enabled |
| **MCP Servers** | External service connections | time, tavily |
| **Model** | LLM provider and model name | Kimi K2.5 |
| **Max Turns** | Maximum conversation rounds | 60 |
| **Executor** | Code execution environment | Local (API subprocess) |

## Creating Agents

### Automatic (Recommended)

Describe what you need in the chat panel:

```
Create an agent that converts PDF invoices to structured spreadsheets
```

The agent-builder analyzes your request, creates any needed skills, and saves the agent configuration.

### Manual

Go to **Agents** > **New Agent** and fill in each component. See [How to: Create an Agent](/how-to/create-agent) for a detailed walkthrough.

## Using Agents

### In the Chat Panel

1. Open the chat panel (bottom-right button)
2. Select an agent from the dropdown at the top
3. Start chatting — the agent's configuration applies immediately

:::note
Selecting an agent replaces your current configuration. If you have an active conversation, the system prompts you to confirm before switching.
:::

Manually changing any configuration item (skills, tools, executor, etc.) clears the agent selection and switches to **Custom Config** mode.

### Via API

```bash
# Non-streaming
curl -X POST http://localhost:62610/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Analyze this sales data",
    "preset_id": "your-agent-id"
  }'

# Streaming (SSE)
curl -X POST http://localhost:62610/api/v1/agent/run/stream \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Analyze this sales data",
    "preset_id": "your-agent-id"
  }'
```

## Agent Types

| Type | Description | Editable | Deletable |
|------|-------------|----------|-----------|
| **User Agents** | Created by you | Yes | Yes |
| **Meta Agents** | System agents (agent-builder, skill-evolver, etc.) | No | No |

Meta agents appear in a separate section in the UI with a "Meta" badge.

### Built-in Meta Agents

| Agent | Purpose |
|-------|---------|
| **agent-builder** | Creates custom agents by planning skills and configuring presets |
| **skill-evolve-helper** | Interactive skill evolution via conversational chat (used by the Evolve page) |

## Publishing Agents

Share an agent via a public URL:

1. Go to agent details
2. Click **Publish**
3. Copy the public link

Anyone with the link can chat with the agent using your configuration. Published agents support multi-turn conversations via server-side sessions.

See [How to: Publish an Agent](/how-to/publish-agent) for details.

## Steering (Mid-Execution Intervention)

While an agent is running, you can inject **steering messages** to redirect its behavior without stopping the run. The agent picks up your message at the next tool boundary and adjusts its approach.

### How It Works

1. Start a chat — the agent begins executing
2. While the agent is running, type a message and press Enter (or click **Steer**)
3. Your message is injected into the agent's context as a `[User Steering Message]`
4. The agent sees it before its next LLM call and adjusts accordingly
5. A `steering_received` event appears in the SSE stream

### Injection Points

The agent checks for steering messages at two points:

| Point | When | Effect |
|-------|------|--------|
| **After tool results** | Tool execution completes, before next LLM call | Agent sees tool results + your steering together |
| **Before finishing** | Agent is about to end (`end_turn`), but steering is pending | Agent continues instead of finishing |

### Multi-Worker Support

In Docker deployments with multiple uvicorn workers, steering uses a hybrid approach:

- **Same worker** — direct in-memory injection (fast path)
- **Cross worker** — filesystem queue (`/tmp/agent_steering/`) with atomic writes + polling (300ms interval)

### Via API

```bash
# Steer a running agent stream
curl -X POST http://localhost:62610/api/v1/agent/run/stream/{trace_id}/steer \
  -H "Content-Type: application/json" \
  -d '{"message": "Focus on the validation logic instead"}'

# Steer a published agent
curl -X POST http://localhost:62610/api/v1/published/{agent_id}/chat/{trace_id}/steer \
  -H "Content-Type: application/json" \
  -d '{"message": "Use a different approach"}'
```

**Response:** `{"status": "injected", "trace_id": "..."}`

**Error codes:**
- `404` — No active run for this trace_id
- `409` — Agent has already completed
- `422` — Empty message

## Execution Traces

Every agent run generates a trace containing:

- The original request
- Each tool call and its result
- Token usage per turn
- Total duration
- Skills actually used (tracked via `get_skill` calls)

View traces at **Traces** in the navigation, or from the agent details page.

## Best Practices

- **Name descriptively** — "Sales Data Analyst" instead of "Agent 1"
- **Keep focused** — one agent per domain works better than one super-agent
- **Start minimal** — add skills and tools as you discover needs
- **Test iteratively** — try the agent, review traces, refine configuration

## Related

- [Skills](/concepts/skills) — Domain knowledge modules
- [Tools](/concepts/tools) — Built-in actions
- [MCP](/concepts/mcp) — External service connections
- [Executors](/concepts/executors) — Code execution environments
- [How to: Create an Agent](/how-to/create-agent)
- [How to: Publish an Agent](/how-to/publish-agent)
