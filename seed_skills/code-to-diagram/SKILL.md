---
name: code-to-diagram
description: "Generate architecture diagrams, ER diagrams, sequence diagrams, flowcharts, and class diagrams from codebases using Mermaid.js. Use when users ask to visualize code structure, draw architecture diagrams, create ER diagrams from database models, generate sequence diagrams from API flows, or produce any diagram from source code. Triggers on: 'draw architecture', 'generate diagram', 'visualize code', 'ER diagram', 'sequence diagram', 'class diagram', 'flowchart from code', 'module dependency graph'."
---

# Code to Diagram

Generate production-quality diagrams from source code via Mermaid.js, rendered to SVG/PNG with `mmdc`.

## Environment

**Executor required:** This skill needs the `diagram` executor (Chromium + Node.js + mmdc pre-installed).
If `mmdc` is not available, install first:
```bash
npm install -g @mermaid-js/mermaid-cli
```

Puppeteer config for headless environments — create at `/tmp/puppeteer-config.json` if missing:
```json
{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
```

## Workflow

1. **Analyze** — Read the codebase to understand structure (`glob`, `grep`, `read`)
2. **Plan** — Decide diagram type(s) based on user request and code patterns
3. **Generate** — Write `.mmd` file with Mermaid syntax
4. **Render** — Run `mmdc` to produce SVG and PNG
5. **Verify** — Read the output image and check correctness

## Diagram Type Selection

| User Intent | Diagram Type | Mermaid Keyword |
|-------------|-------------|-----------------|
| System overview, module layout | Architecture | `graph TD` + `subgraph` |
| Database tables, ORM models | ER Diagram | `erDiagram` |
| API flow, request lifecycle | Sequence Diagram | `sequenceDiagram` |
| Inheritance, interfaces | Class Diagram | `classDiagram` |
| Business logic, conditionals | Flowchart | `flowchart TD` |
| Task states, lifecycle | State Diagram | `stateDiagram-v2` |
| Import/dependency tree | Dependency Graph | `graph LR` |
| Timeline, project phases | Gantt Chart | `gantt` |

## Analysis Strategy

Do NOT read every file. Use progressive analysis:

**Step 1 — Directory scan:**
`glob("**/*.py")` or `glob("**/*.ts")` to understand module structure.

**Step 2 — Entry points:**
- Python: `main.py`, `app.py`, `__init__.py`, `pyproject.toml`
- Node.js: `package.json`, `index.ts`, `app.ts`
- Java: `pom.xml`, `Application.java`

**Step 3 — Targeted reads by diagram type:**
- **ER** → ORM models (`models.py`, `schema.prisma`, `*.entity.ts`)
- **Architecture** → Router registrations, dependency injection, config
- **Sequence** → Specific endpoint handler + service call chain
- **Class** → Class definitions via `grep("class ")`

**Step 4 — GitHub repos:**
```bash
git clone --depth 1 <url> /tmp/repo-name
```
Then apply the same progressive scan.

## Rendering

```bash
# SVG (transparent background, good for docs)
mmdc -i diagram.mmd -o diagram.svg -b transparent -p /tmp/puppeteer-config.json

# PNG (white background, 2x scale for sharpness)
mmdc -i diagram.mmd -o diagram.png -b white -s 2 -p /tmp/puppeteer-config.json
```

Always generate both formats. Use `-s 2` for PNG (sharp at any zoom level).

## Mermaid Syntax Reference

For detailed patterns and examples per diagram type, see [references/mermaid-patterns.md](references/mermaid-patterns.md).

Key rules:
- Short IDs, descriptive labels: `DB[("PostgreSQL 16")]`
- Use `subgraph` for logical grouping in architecture diagrams
- Limit ER diagrams to ~10 entities — split by domain if larger
- `participant` aliases in sequence diagrams for short names
- Quote labels with special chars: `A["Node (v1)"]`
- Max ~20 nodes per diagram — split into multiple if larger

## Output Conventions

- Write `.mmd` source + rendered files to workspace
- Descriptive names: `architecture.mmd`, `er-diagram.png`, `api-sequence.svg`
- Multiple diagrams → create `diagrams/` folder with index

## Quality Checklist

- All entities/modules from the code are represented
- Relationships and data flow directions are correct
- Labels readable, not truncated or overlapping
- No Mermaid syntax errors
- Output image visually verified
