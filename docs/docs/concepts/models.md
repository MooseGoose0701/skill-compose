---
sidebar_position: 6
---

# Models

Skill Compose supports multiple LLM providers. Each provider requires its own API key, and you can switch models per agent or per conversation.

## Supported Models

### Direct Providers

| Provider | Model | Context | Tools | Vision | API Key |
|----------|-------|---------|-------|--------|---------|
| **Moonshot** | kimi-k2.5 | 256K | Yes | Yes | `MOONSHOT_API_KEY` |
| **Anthropic** | claude-sonnet-4-5-20250929 | 200K | Yes | Yes | `ANTHROPIC_API_KEY` |
| **OpenAI** | gpt-4o | 128K | Yes | Yes | `OPENAI_API_KEY` |
| **OpenAI** | gpt-4o-mini | 128K | Yes | Yes | `OPENAI_API_KEY` |
| **Google** | gemini-2.0-flash | 1M | Yes | Yes | `GOOGLE_API_KEY` |
| **DeepSeek** | deepseek-chat | 64K | Yes | No | `DEEPSEEK_API_KEY` |
| **DeepSeek** | deepseek-reasoner | 64K | Yes | No | `DEEPSEEK_API_KEY` |

:::info Default Model
**Kimi K2.5** is the default model. Set `MOONSHOT_API_KEY` in your `.env` file to use it.
:::

### OpenRouter

OpenRouter provides access to multiple providers through a single API key (`OPENROUTER_API_KEY`):

| Model | Context | Tools | Vision |
|-------|---------|-------|--------|
| anthropic/claude-sonnet-4.5 | 200K | Yes | Yes |
| anthropic/claude-opus-4.6 | 200K | Yes | Yes |
| deepseek/deepseek-chat-v3-0324 | 64K | Yes | No |
| moonshotai/kimi-k2.5 | 256K | Yes | Yes |
| google/gemini-3-flash-preview | 1M | Yes | Yes |
| google/gemini-2.5-flash | 1M | Yes | Yes |
| google/gemini-2.5-flash-lite | 1M | Yes | Yes |
| minimax/minimax-m2.1 | 1M | Yes | Yes |
| x-ai/grok-code-fast-1 | 131K | Yes | No |
| x-ai/grok-4.1-fast | 131K | Yes | Yes |

### Requesty

Requesty provides access to multiple providers through a single API key (`REQUESTY_API_KEY`) using the same `provider/model` naming as OpenRouter (e.g. `openai/gpt-4o-mini`). Set `REQUESTY_API_KEY` in your `.env` file and select the `requesty` provider to route requests through https://router.requesty.ai/v1.

## Vision Support

Models with **Vision: Yes** can directly see uploaded images. When you upload an image in Chat, the system:

1. Detects image files by content type (`image/png`, `image/jpeg`, etc.)
2. Encodes the image as base64 and sends it as an image content block to the LLM
3. The LLM can describe, analyze, or reason about the image contents

For models **without** vision support (e.g., DeepSeek), uploaded images fall back to file-path mode — the agent can still access the file via code execution, but the LLM cannot "see" the image directly.

## Configuring Models

### Per Agent

Set the model in the agent configuration:

1. Go to **Agents** > select an agent
2. Choose **Model Provider** and **Model Name**
3. Save

### In Chat

Switch models during a conversation:

1. Open the chat panel
2. Click the model selector dropdown
3. Choose a different model

:::note
Context is preserved when switching models, but different models may respond differently to the same conversation.
:::

### Via API

```bash
curl -X POST http://localhost:62610/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Hello",
    "model_provider": "anthropic",
    "model_name": "claude-sonnet-4-5-20250929"
  }'
```

## API Key Setup

Add keys to your `.env` file:

```bash title=".env"
# Direct providers
MOONSHOT_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
DEEPSEEK_API_KEY=...

# OpenRouter (access multiple providers with one key)
OPENROUTER_API_KEY=sk-or-...
```

You need at least one key. Additional keys are optional.

## Context Window Management

Each model has a fixed context window. When a conversation approaches the limit, the system automatically compresses history.

| Model | Context Limit | Compression Triggers At |
|-------|--------------|------------------------|
| Kimi K2.5 | 256K | ~179K tokens |
| Claude Sonnet 4.5 | 200K | ~140K tokens |
| GPT-4o | 128K | ~90K tokens |
| Gemini 2.0 Flash | 1M | ~700K tokens |
| DeepSeek Chat | 64K | ~45K tokens |

## Related

- [Agents](/concepts/agents) — Model selection in agent configuration
- [Configuration](/reference/configuration) — Environment variable reference
