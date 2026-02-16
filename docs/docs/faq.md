---
sidebar_position: 20
---

# FAQ

## General

### What is Skill Compose?

A platform for building AI agents through natural conversation. Describe what you need, and it creates your agent along with any required skills automatically.

### Do I need coding experience?

No. You can create and use agents entirely through the web UI using natural language. Knowledge of Python helps if you want to write custom skill scripts.

### Which LLM providers are supported?

Moonshot (Kimi K2.5, default), Anthropic (Claude), OpenAI (GPT-4o), Google (Gemini), DeepSeek, and OpenRouter. You need at least one API key. See [Models](/concepts/models) for the full list.

### Where is my data stored?

| Data | Location |
|------|----------|
| Chat history, skills, agents, traces | PostgreSQL database |
| Uploaded files | `uploads/` directory |
| Skill files | `skills/` directory and database |
| API keys | `.env` file only (never logged) |

---

## Installation

### Docker containers won't start

```bash
# Check port availability
lsof -i :62600 && lsof -i :62610 && lsof -i :62620

# View logs
docker compose logs -f

# Restart
docker compose down && docker compose up -d
```

### "API key not found" error

Verify your `.env` file contains at least one valid key:

```bash
grep API_KEY .env
```

Keys should look like: `ANTHROPIC_API_KEY=sk-ant-api03-...`

### Database connection failed

**Docker:** Check if the `db` container is healthy with `docker compose ps`.

**Local:** Verify PostgreSQL is running:

```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql
```

---

## Agents

### Agent isn't using the skills I selected

The agent decides which skills are relevant based on your request. Be more specific:

- Instead of: *"Analyze this file"*
- Try: *"Use the csv-data-analyzer skill to analyze this sales data"*

### Agent stops before completing the task

Increase **Max Turns** in the agent configuration. Default is 60. For complex multi-step tasks, try 100.

### Agent is too slow

1. **Use a faster model** — GPT-4o-mini or Gemini Flash
2. **Reduce skills** — fewer skills means less context to process
3. **Be specific** — vague requests require more agent rounds

### Can I redirect the agent while it's running?

Yes. While the agent is executing, the input field stays active. Type a message and press Enter to send a **steering message**. The agent picks it up at the next tool boundary and adjusts its behavior — no need to stop and restart. See [Agents — Steering](/concepts/agents#steering-mid-execution-intervention).

### Agent stuck in a loop

1. Send a steering message to redirect it (e.g., "Stop repeating and try a different approach")
2. Click **Stop** to halt execution
3. Rephrase your request more specifically
4. Try a different model
5. Review traces for the repeated pattern

---

## Skills

### How are skills different from tools?

Skills provide *knowledge* ("how to analyze CSV data"). Tools provide *actions* (`execute_code`, `read`). Skills tell the agent how to do things; tools let it actually do them.

### Can I edit skills manually?

Yes. Edit `skills/my-skill/SKILL.md` directly. The system detects changes on the next page load and creates a new version automatically.

### How does skill evolution work?

1. You use a skill (agent calls `get_skill`)
2. The system logs the execution trace
3. You click **Evolve** and select traces or provide feedback
4. The skill-evolver analyzes and improves the skill
5. A new version is created

See [How to: Evolve Skills](/how-to/evolve-skills).

### Imported skill doesn't appear

1. Verify the skill has a valid `SKILL.md` file
2. Go to **Skills** page — look for the blue "unregistered skills" banner
3. Click to import detected skills

---

## MCP

### What MCP servers are available?

Tavily (web search), Time (timezone), Git (version control), Gemini (image analysis). See [MCP](/concepts/mcp).

### MCP server not connecting

1. Verify the server is enabled in your agent configuration
2. Check that required API keys are set (e.g., `TAVILY_API_KEY`)
3. View status on the **MCP** page

### Can I add custom MCP servers?

Yes. Ask the agent: *"Create an MCP server that can query my database"*, or add configuration manually to `config/mcp.json`. See [How to: Configure MCP](/how-to/configure-mcp).

---

## Files

### Can the agent see my uploaded images?

Yes, for vision-capable models (Kimi K2.5, Claude, GPT-4o, Gemini, etc.). Upload an image in the chat panel and the agent will receive it as a visual input — no extra configuration needed. For models without vision support (e.g., DeepSeek), images are passed as file paths instead, so the agent can still process them via code but cannot "see" them directly.

### Where are uploaded files?

In `uploads/` organized by session ID:

```
uploads/
└── session-id/
    └── your-file.csv
```

### How do I download agent-generated files?

Look for download links in the chat response. Or go to **Files** in the navigation to browse all files.

### File upload failed

Max size is 50MB per file. For larger files, place them directly in the workspace.

---

## Troubleshooting

### Streaming shows "peer closed connection" error

The LLM API dropped the connection mid-stream (e.g., network instability, API timeout). The system automatically retries with a non-streaming fallback call. If the retry also fails, a partial response is shown along with an error. This is a transient issue — try again.

### "Context window exceeded" error

The conversation is too long. The system auto-compresses history when input tokens exceed 70% of the model's context limit — identifying logical turn boundaries and keeping recent turns within a dynamic token budget (up to 3 turns). If compression fails, start a new chat and summarize your previous context in the first message.

### Responses are being cut off

The output hit the `max_tokens` limit (16384). The system auto-recovers by asking the agent to continue in smaller steps. If it persists, ask the agent to break the task into smaller pieces.

### Agent repeats "Missing required parameter: code"

Usually caused by `max_tokens` truncation. The system detects this and asks the agent to retry with smaller code blocks. If it persists, check `app/agent/agent.py` for the `max_tokens` setting.

### Variables lost between execute_code calls

By default, `execute_code` uses a persistent IPython kernel so variables, imports, and state carry across calls. If you see `NameError`, the kernel may have crashed and fallen back to subprocess mode. Check the API logs for "IPython kernel failed" warnings. Restarting the agent session starts a fresh kernel.

### Agent-generated files don't show up as downloads

Output files are auto-detected by scanning the per-session workspace directory (`/app/workspaces/{workspace_id}`) before and after each `execute_code`/`bash` call. Files appear as download links in the chat UI. If files don't show up:

1. Ensure code writes files using **relative paths** (e.g., `df.to_csv('output.csv')`), which resolve to the workspace directory
2. Check that files aren't filtered by the blacklist (compiled files like `.pyc`, config files like `.toml`, hidden files)
3. For remote executors, verify the `workspaces` Docker volume is shared between the API and executor containers

### API keys not available in remote executor

Environment variables (API keys, etc.) are automatically forwarded from the API server to executors at runtime — you do not need to add them to the executor's `docker-compose.yaml` environment section. The API reads keys from the `.env` file and sends them with each execution request. If a key is still missing, verify it is set on the **Environment** page or in `config/.env`.

### Execution trace shows errors

1. Go to **Traces** > find the failed trace
2. Expand to see error details
3. If it's a skill issue, [evolve the skill](/how-to/evolve-skills)
4. If it's a configuration issue, check agent settings

---

## Performance

### How to reduce token usage?

1. **Be concise** — shorter prompts use fewer tokens
2. **Limit skills** — only enable skills the agent needs
3. **Use efficient models** — GPT-4o-mini or DeepSeek Chat

### Skill evolution is slow

Skill creation and evolution run as background tasks. They involve a full agent execution (the skill-creator or skill-evolver), which takes 30-120 seconds depending on complexity and model.

### Hot reload interrupts skill evolution

Start the backend with reload exclusions:

```bash
uvicorn app.main:app --reload \
  --reload-exclude 'skills/**' --reload-exclude 'logs/**'
```

Or use `./scripts/restart-dev.sh`.
