---
name: skill-evolver
description: Analyze skill execution traces to identify issues and automatically evolve/improve skills. Use when users provide trace files (JSON) from skill runs and want to improve skill performance based on real execution data. Triggers on requests like "analyze traces", "evolve skill based on traces", "improve skill from execution history", "find issues in skill traces", or when working with skill trace/log files.
---

# Skill Evolver

Analyze skill execution traces to discover issues, identify improvement opportunities, and apply fixes to skill files.

## Trace Format

Traces are JSON with this structure:

```json
{
  "id": "uuid",
  "request": "user's original request",
  "skills_used": ["skill-name"],
  "success": true/false,
  "total_turns": 2,
  "total_input_tokens": 5000,
  "total_output_tokens": 200,
  "duration_ms": 7000,
  "steps": [
    {"role": "assistant", "content": "...", "tool_name": null},
    {"role": "tool", "tool_name": "...", "tool_input": {}, "tool_result": "..."}
  ],
  "llm_calls": [
    {"turn": 1, "stop_reason": "tool_use", "input_tokens": 2500, "output_tokens": 50}
  ]
}
```

## Workflow

This skill can receive two types of input (at least one required):
- **Traces**: Execution trace data from real skill runs — provides data-driven problem discovery
- **Feedback**: User-written improvement suggestions — provides directed guidance for changes

When both are provided, combine insights: use traces to validate/discover issues and feedback to prioritize and guide fixes.

### Step 1: Analyze Inputs

**If traces are provided**, run the analysis script:

```bash
scripts/analyze_traces.py <traces.json> [--skill <name>] [--format json|text]
```

Output includes:
- Success rate
- Average turns, duration, tokens
- Common issues and warnings
- Recommendations

**If feedback is provided**, identify the user's improvement goals and map them to actionable changes.

**If both are provided**, cross-reference: does the feedback align with trace-discovered issues? Use feedback to prioritize which trace-identified problems to fix first.

### Step 2: Extract Issue Details

For failed or problematic traces, extract full context:

```bash
scripts/extract_issue_context.py <traces.json> --failed
scripts/extract_issue_context.py <traces.json> --trace-id <id> --show-llm
scripts/extract_issue_context.py <traces.json> --high-turns
```

Skip this step if only feedback was provided (no traces).

### Step 3: Identify Root Causes

Map issues to skill components using [references/issue-patterns.md](references/issue-patterns.md):

| Issue Type | Likely Fix Location |
|------------|-------------------|
| execution_failure | scripts/, error handling |
| high_turn_count | SKILL.md clarity, add examples |
| tool_errors | scripts/, input validation |
| high_token_usage | SKILL.md verbosity, progressive disclosure |
| repeated_tool_calls | SKILL.md decision trees |

For feedback-only input, map the user's suggestions directly to the appropriate skill components.

### Step 4: Apply Fixes

Read the target skill and apply changes based on analysis:

1. **For script errors**: Fix scripts, add validation, improve error messages
2. **For efficiency issues**: Add examples, decision trees, clearer instructions
3. **For token issues**: Reduce SKILL.md, move content to references/
4. **For trigger issues**: Update frontmatter description
5. **For feedback-guided changes**: Apply the user's specific suggestions

**Scope constraints — strictly follow:**
- Only modify the target skill's **existing files** (SKILL.md, scripts/, references/)
- Do NOT create new reference files, templates, or guides
- Do NOT search the web for domain-specific content
- Do NOT generate CHANGELOG, improvement reports, or other extra deliverables
- The evolved skill files themselves are the sole deliverable

## Quick Reference

### Issue Severity Levels

- **high**: Failures, max_tokens, tool errors → Fix immediately
- **medium**: High turns, high tokens, retries → Optimize
- **low**: Long duration → Consider optimization

### Key Metrics Thresholds

| Metric | Warning | Action |
|--------|---------|--------|
| success_rate | <90% | Review failures |
| avg_turns | >4 | Simplify workflow |
| avg_tokens | >30000 | Reduce context |
| duration_ms | >60000 | Optimize scripts |

### Common Fixes

**Low success rate:**
- Add error handling in scripts
- Add input validation
- Clarify ambiguous instructions

**High turn count:**
- Add decision tree
- Provide more examples
- Use scripts for multi-step operations

**High token usage:**
- Reduce SKILL.md lines (<500)
- Move details to references/
- Remove redundant examples
