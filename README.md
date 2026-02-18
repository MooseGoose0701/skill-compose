<p align="center">
  <img src="scheader.png" alt="Skill Compose" width="50%" />
</p>

<p align="center">
  <a href="./README.md"><img alt="English" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./README_es.md"><img alt="Español" src="https://img.shields.io/badge/Español-d9d9d9"></a>
  <a href="./README_pt-BR.md"><img alt="Português (BR)" src="https://img.shields.io/badge/Português (BR)-d9d9d9"></a>
  <a href="./README_zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README_ja.md"><img alt="日本語" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
</p>

<p align="center">
Skill Compose is an open-source agent builder and runtime platform for skill-powered agents.<br>
No workflow graphs. No CLI.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg" alt="Python" /></a>
  <a href="https://nextjs.org/"><img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js" /></a>
  <a href="https://discord.gg/uRDx9hJj"><img src="https://img.shields.io/badge/Discord-%235865F2.svg?style=flat&logo=discord&logoColor=white" alt="discord" /></a>
  <a href="https://x.com/SkillComposeAI/"><img src="https://img.shields.io/twitter/follow/SkillComposeAI" alt="twitter" /></a>
</p>

<p align="center">
  <img src="docs/images/screenshot.png" alt="Skill Compose Screenshot" width="800" />
</p>

## Key Capabilities

- 🧩 **Skills as first-class artifacts** — versioned, reviewable skill packages (contracts, references, rubrics, helpers), not brittle graphs.
- 🧠 **"Skill-Compose My Agent" workflow** — describe what you want; Skill Compose finds/reuses skills, drafts missing ones, and composes an agent.
- 🔌 **Tool + MCP wiring** — connect tools and MCP servers without hand-writing glue code.
- 🚀 **Instant publishing** — one click to ship as **Web Chat** (shareable link) and/or **API** (integrations-ready endpoint).
- 🛡️ **Container-first isolation** — run agents in containers (or K8s pods) to keep hosts clean and execution reproducible.
- 🧱 **Executors for heavy environments** — assign custom Docker images/K8s runtimes per agent (GPU/ML/HPC stacks, custom builds).
- 📦 **Skill lifecycle management** — GitHub import + one-click updates, multi-format import/export, version history, diff/rollback, and local sync.
- 🔄 **Skill evolution from reality** — improve skills using feedback + execution traces, with proposed rewrites you can review.
- 🗂️ **Skill library organization** — categories, pinning, and lightweight discovery to stay sane at 100+ skills.

## Examples

<table>
<tr>
<td align="center">
<b>Skill-Compose Your Agent</b><br>
<sub>Describe what you want and let Skill Compose build the agent for you — finding existing skills, drafting missing ones, and wiring everything together.</sub><br><br>
<img src="docs/examples/skill-compose-your-agent.gif" alt="Skill-Compose Your Agent" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Evolve Your Agent</b><br>
<sub>Improve skills automatically from execution traces and user feedback, review proposed changes, accept the rewrite, and watch your agents and skills get smarter.</sub><br><br>
<img src="docs/examples/evolve-your-agent.gif" alt="Evolve Your Agent" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Demo Agent: Article to Slides</b><br>
<sub>Turn any article or paper into a polished slide deck. The agent reads the content, extracts key points, draft storyboards, and generates presentation-ready slides.</sub><br><br>
<img src="docs/examples/article-to-slides-agent.gif" alt="Article to Slides Agent" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Demo Agent: ChemScout</b><br>
<sub>Runs in an isolated execution environment! A chemistry research assistant that searches compound databases, analyzes molecular structures, and summarizes findings into structured reports.</sub><br><br>
<img src="docs/examples/chemscout-agent.gif" alt="ChemScout Agent" width="100%" />
</td>
</tr>
</table>

## Architecture

<p align="center">
  <img src="docs/images/architecture.png" alt="Skill Compose Architecture" width="700" />
</p>

*Some features shown may still be in development.*

## Quick Start

Get started with Docker:

```bash
git clone https://github.com/MooseGoose0701/skill-compose.git
cd skill-compose/docker
# Default model is Kimi 2.5 (thinking disabled, API key: MOONSHOT_API_KEY), add at least one LLM API key.
# You can also set API KEYs manually in the Web UI "Environment" after launch.
cp .env.example .env
docker compose up -d
```

Open **http://localhost:62600** and click **"Skill-Compose Your Agent"**.

Stop services:

```bash
cd skill-compose/docker
docker compose down
```

Build from source (after code changes):

```bash
cd skill-compose/docker
cp .env.example .env  # First time only; Add your own API keys
./rebuild.sh          # Rebuild all services
./rebuild.sh api      # Rebuild API only
./rebuild.sh web      # Rebuild Web only
```

<details>
<summary>Cleanup (reset to initial state)</summary>

```bash
cd skill-compose/docker
# '-v' will remove all data stored in volumes
docker compose down -v
```

</details>

## Resources

- 📚 [Full Documentation](docs/) — Getting started, concepts, how-to guides, and reference
- 🔧 [API Reference](docs/docs/reference/api.md) — Complete REST API endpoints
- 🤖 [Models & Providers](docs/docs/concepts/models.md) — Supported LLMs and configuration

## Contributing

Found a bug or have a feature idea? Contributions welcome!

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
