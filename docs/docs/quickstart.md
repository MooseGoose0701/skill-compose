---
sidebar_position: 2
---

# Quick Start

Get Skill Compose running and build your first agent.

## Start with Docker

```bash
git clone https://github.com/MooseGoose0701/skill-compose.git
cd skill-compose/docker
# Default model is Kimi 2.5 (API key: MOONSHOT_API_KEY), add at least one LLM API key.
# You can also set API keys manually in the Web UI "Environment" after launch.
cp .env.example .env
docker compose up -d
```

Open **http://localhost:62600** and click **"Compose Your Agent"**.

:::info Three services start automatically
- **Web UI** — http://localhost:62600
- **API** — http://localhost:62610
- **PostgreSQL** — localhost:62620
:::

Stop services:

```bash
cd skill-compose/docker
docker compose down
```

:::caution
Do not use `docker compose down -v` — the `-v` flag deletes the database volume and all your data.
:::

## Build Your First Agent

### Step 1: Open the Chat Panel

Click the **Chat** button in the bottom-right corner. The agent chat panel slides open.

### Step 2: Describe Your Agent

Type a description of the agent you want to create:

```
Create an agent that can analyze CSV files and generate summary reports
with charts and statistics.
```

Press **Enter**.

### Step 3: Watch It Build

The agent-builder works through several stages:

1. **Analyzes your request** — determines what capabilities are needed
2. **Checks existing skills** — looks for reusable components
3. **Creates new skills** — builds any missing pieces
4. **Configures the agent** — sets up tools and settings

You see real-time progress as streaming output in the chat panel.

### Step 4: Review the Result

The agent-builder shows you what it created:

```
Agent "Data Analyst" created!

Skills:
  - csv-data-analyzer — Parse and analyze CSV data
  - chart-generator — Create visualizations

Tools enabled:
  - execute_code — Run Python code
  - read / write — File operations
  - bash — Run shell commands
```

### Step 5: Use Your Agent

Switch to your new agent and give it a task:

1. Select **Data Analyst** from the agent dropdown at the top of the chat panel
2. Upload a CSV file using the attachment button, or type a request:

```
Analyze the sales data and show me the top trends by region.
```

The agent reads your file, runs analysis code, generates charts, and provides downloadable reports.

### Step 6: Find Your Agent

Your agent is saved for reuse:

1. Go to **Agents** in the top navigation
2. Find **Data Analyst** in the list
3. Click to view or edit its configuration

## Using the API

You can also run agents programmatically:

```bash
# Non-streaming
curl -X POST http://localhost:62610/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"request": "Summarize this quarter sales trends"}'

# Streaming (SSE)
curl -X POST http://localhost:62610/api/v1/agent/run/stream \
  -H "Content-Type: application/json" \
  -d '{"request": "Summarize this quarter sales trends"}'
```

## Next Steps

| If you want to... | Read... |
|-------------------|---------|
| Understand how agents work | [Agents](/concepts/agents) |
| Learn about skills | [Skills](/concepts/skills) |
| Create agents manually | [How to: Create an Agent](/how-to/create-agent) |
| Improve skills over time | [How to: Evolve Skills](/how-to/evolve-skills) |
| Import skills from GitHub | [How to: Import & Export](/how-to/import-export-skills) |
| Set up local development | [Development Setup](/development-setup) |
