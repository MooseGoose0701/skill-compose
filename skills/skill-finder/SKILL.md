---
name: skill-finder
description: "Helps users discover and install agent skills from the open skills ecosystem (skills.sh). Use when users ask 'how do I do X', 'find a skill for X', 'is there a skill that can...', want to search for tools/templates/workflows, or express interest in extending agent capabilities."
---

# Skill Finder

Discover and install agent skills from the [skills.sh](https://skills.sh) open ecosystem into Skill Compose.

## When to Use This Skill

Activate when users:
- Ask "how do I do X?" where an existing skill might help
- Request "find a skill for X" or "is there a skill for X?"
- Ask "can you do X?" for specialized tasks (poster design, data analysis, etc.)
- Want to search for tools, templates, or workflows
- Mention needing help with a specific domain that might have a community skill

## Available Scripts

### 1. Search Skills — `find_skills.py`

Search the skills.sh ecosystem for skills matching a query.

```bash
python scripts/find_skills.py <query> [--limit N]
```

**Example:**
```bash
python scripts/find_skills.py "react performance"
python scripts/find_skills.py "docker" --limit 5
```

**Output:** JSON array of matching skills with `name`, `source` (owner/repo), `installs` count, and `url` (skills.sh link).

### 2. Install Skill — `add_skill.py`

Download a skill from GitHub and register it in Skill Compose.

```bash
python scripts/add_skill.py <owner/repo@skill-name>
```

**Example:**
```bash
python scripts/add_skill.py "vercel-labs/agent-skills@vercel-react-best-practices"
```

**What it does:**
1. Parses the `owner/repo@skill-name` identifier
2. Tries multiple GitHub paths to locate the skill (`skills/<name>/`, `<name>/`, root)
3. Downloads all skill files (SKILL.md, scripts/, references/, assets/)
4. Saves to the local `skills/` directory
5. Registers the skill in Skill Compose via the import-local API
6. The skill is immediately available for use in Agent Presets

## How to Help Users Find and Install Skills

### Step 1: Understand the Need
Identify what domain and specific task the user needs help with.

### Step 2: Search
Run `find_skills.py` with relevant keywords. Try multiple queries if the first doesn't yield good results.

### Step 3: Present Results
Show the user the found skills with:
- Skill name
- Source repository
- Install count (popularity indicator)
- skills.sh link for more details

### Step 4: Install
If the user wants a skill, run `add_skill.py` with the `source@name` identifier from the search results. Confirm the installation succeeded.

## Common Skill Categories

| Category | Example Queries |
|----------|----------------|
| Web Development | react, nextjs, vue, css, tailwind, html |
| Testing | testing, jest, playwright, cypress |
| DevOps | docker, kubernetes, ci-cd, terraform |
| Documentation | docs, readme, markdown, api-docs |
| Code Quality | lint, refactor, code-review, typescript |
| Design | ui, design, figma, accessibility |
| Data & ML | pandas, data-analysis, machine-learning |
| Productivity | git, automation, workflow |

## Tips for Effective Searches

- Use specific domain keywords: "react performance" instead of just "fast"
- Try alternative terms if first search yields few results: "testing" → "jest" → "playwright"
- Popular skill sources include: `vercel-labs/agent-skills`, `google-labs-code/stitch-skills`
- Check install counts — higher counts generally indicate more mature skills

## When No Skills Are Found

1. Acknowledge that no matching skill exists yet
2. Offer to help the user directly with their task
3. Suggest the user could create a custom skill for their use case using `skill-creator`
