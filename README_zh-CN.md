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
Skill Compose 是一个开源的 Agent 构建和运行平台，基于技能驱动的 Agent 架构。<br>
无需工作流图。无需命令行。
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg" alt="Python" /></a>
  <a href="https://nextjs.org/"><img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js" /></a>
  <a href="https://discord.gg/uRDx9hJj"><img src="https://img.shields.io/badge/Discord-%235865F2.svg?style=flat&logo=discord&logoColor=white" alt="discord" /></a>
  <a href="https://x.com/SkillComposeAI/"><img src="https://img.shields.io/twitter/follow/SkillComposeAI" alt="twitter" /></a>
</p>

<p align="center">
  <img src="docs/images/screenshot.png" alt="Skill Compose 截图" width="800" />
</p>

## 核心能力

- 🧩 **技能作为一等公民** — 版本化、可审查的技能包（合约、参考资料、评分标准、辅助工具），而非脆弱的工作流图。
- 🧠 **"Skill-Compose My Agent" 工作流** — 描述你的需求；Skill Compose 自动查找/复用技能，起草缺失的技能，并组装 Agent。
- 🔌 **工具 + MCP 接入** — 连接工具和 MCP 服务器，无需手写胶水代码。
- 🚀 **一键发布** — 一键部署为 **Web 聊天**（可分享链接）和/或 **API**（可集成端点）。
- 🛡️ **容器优先隔离** — 在容器（或 K8s Pod）中运行 Agent，保持宿主机整洁，执行可复现。
- 🧱 **重型环境 Executor** — 为每个 Agent 分配自定义 Docker 镜像/K8s 运行时（GPU/ML/HPC 技术栈、自定义构建）。
- 📦 **技能生命周期管理** — GitHub 导入 + 一键更新、多格式导入/导出、版本历史、差异对比/回滚、本地同步。
- 🔄 **基于实际运行的技能进化** — 利用反馈和执行追踪改进技能，支持审查改写建议。
- 🗂️ **技能库管理** — 分类、置顶和轻量级发现功能，轻松管理 100+ 技能。

## 示例

<table>
<tr>
<td align="center">
<b>Skill-Compose 你的 Agent</b><br>
<sub>描述你的需求，让 Skill Compose 为你构建 Agent —— 查找已有技能、起草缺失技能，并将一切组装到一起。</sub><br><br>
<img src="docs/examples/skill-compose-your-agent.gif" alt="Skill-Compose 你的 Agent" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>进化你的 Agent</b><br>
<sub>基于执行追踪和用户反馈自动改进技能，审查修改建议，接受改写，见证你的 Agent 和技能不断变强。</sub><br><br>
<img src="docs/examples/evolve-your-agent.gif" alt="进化你的 Agent" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>示例 Agent：文章转幻灯片</b><br>
<sub>将任何文章或论文转换为精美的幻灯片。Agent 阅读内容、提取关键要点、起草故事板，并生成可直接演示的幻灯片。</sub><br><br>
<img src="docs/examples/article-to-slides-agent.gif" alt="文章转幻灯片 Agent" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>示例 Agent：ChemScout</b><br>
<sub>在隔离的执行环境中运行！一个化学研究助手，可搜索化合物数据库、分析分子结构，并将结果整理成结构化报告。</sub><br><br>
<img src="docs/examples/chemscout-agent.gif" alt="ChemScout Agent" width="100%" />
</td>
</tr>
</table>

## 架构

<p align="center">
  <img src="docs/images/architecture.png" alt="Skill Compose 架构" width="700" />
</p>

*部分展示的功能可能仍在开发中。*

## 快速开始

使用 Docker 快速启动：

```bash
git clone https://github.com/MooseGoose0701/skill-compose.git
cd skill-compose/docker
# 默认模型为 Kimi 2.5（API Key：MOONSHOT_API_KEY），至少添加一个 LLM API Key。
# 启动后也可以在 Web UI 的 "Environment" 页面手动设置 API Key。
cp .env.example .env
docker compose up -d
```

打开 **http://localhost:62600**，点击 **"Skill-Compose Your Agent"**。

停止服务：

```bash
cd skill-compose/docker
docker compose down
```

从源码构建（代码变更后）：

```bash
cd skill-compose/docker
cp .env.example .env  # 仅首次需要；填入你的 API Key
./rebuild.sh          # 重建所有服务
./rebuild.sh api      # 仅重建 API
./rebuild.sh web      # 仅重建 Web
```

<details>
<summary>清理（重置为初始状态）</summary>

```bash
cd skill-compose/docker
# '-v' 会删除所有存储在卷中的数据
docker compose down -v
```

</details>

## 资源

- 📚 [完整文档](docs/) — 入门指南、核心概念、操作指南和参考资料
- 🔧 [API 参考](docs/docs/reference/api.md) — 完整的 REST API 端点
- 🤖 [模型与提供商](docs/docs/concepts/models.md) — 支持的 LLM 和配置

## 贡献

发现 Bug 或有功能建议？欢迎贡献！

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)。
