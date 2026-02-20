# Common Issue Patterns and Solutions

Reference guide for identifying and fixing common skill issues based on trace analysis.

## Table of Contents
1. [Execution Failures](#execution-failures)
2. [Efficiency Issues](#efficiency-issues)
3. [Token Usage Issues](#token-usage-issues)
4. [Tool-Related Issues](#tool-related-issues)
5. [Trigger Issues](#trigger-issues)

---

## Execution Failures

### Pattern: Script Errors
**Indicators in traces:**
- `tool_result` contains "error", "failed", "exception"
- `success: false` with error message

**Common causes:**
- Missing dependencies
- Incorrect file paths
- Input validation failures
- Environment differences

**Solutions:**
1. Add input validation in scripts
2. Add try/except with clear error messages
3. Check file existence before operations
4. Document required dependencies in SKILL.md

### Pattern: Incomplete Responses
**Indicators in traces:**
- `stop_reason: max_tokens` in llm_calls
- Answer appears truncated

**Common causes:**
- Task too complex for single response
- Output format too verbose

**Solutions:**
1. Break complex tasks into steps
2. Use scripts for large outputs instead of inline generation
3. Reduce verbosity in instructions

---

## Efficiency Issues

### Pattern: High Turn Count
**Indicators in traces:**
- `total_turns > 5`
- Repeated similar tool calls
- Back-and-forth clarification

**Common causes:**
- Vague instructions in SKILL.md
- Missing decision trees
- Lack of examples

**Solutions:**
1. Add clear decision trees for common scenarios
2. Provide concrete examples in SKILL.md
3. Use scripts for multi-step operations
4. Add "quick start" patterns for common cases

### Pattern: Retry Loops
**Indicators in traces:**
- Same tool called multiple times with identical input
- Error followed by retry

**Common causes:**
- Poor error handling
- Unclear success criteria
- Transient failures without backoff

**Solutions:**
1. Add explicit success/failure conditions
2. Improve error messages to guide recovery
3. Add retry logic with different approaches

---

## Token Usage Issues

### Pattern: High Input Tokens
**Indicators in traces:**
- `total_input_tokens > 30000`
- Large gap between first and subsequent turns

**Common causes:**
- Verbose SKILL.md (>500 lines)
- Large reference files loaded unnecessarily
- Redundant context

**Solutions:**
1. Reduce SKILL.md to essentials (<500 lines)
2. Move details to references/ with conditional loading
3. Use progressive disclosure patterns
4. Remove redundant examples

### Pattern: High Output Tokens
**Indicators in traces:**
- `total_output_tokens` much higher than expected
- Verbose explanations in steps

**Common causes:**
- No output format guidance
- Skill encourages verbose responses

**Solutions:**
1. Add output format guidelines
2. Specify "be concise" where appropriate
3. Use structured output formats (JSON, tables)

---

## Tool-Related Issues

### Pattern: Wrong Tool Selection
**Indicators in traces:**
- Tools called that shouldn't be used for the task
- Multiple tool attempts before finding right one

**Common causes:**
- Unclear tool documentation in SKILL.md
- Missing "when to use" guidance

**Solutions:**
1. Add clear "when to use" for each tool/script
2. Provide decision tree for tool selection
3. Add negative examples ("don't use X for Y")

### Pattern: Tool Input Errors
**Indicators in traces:**
- Tool errors about invalid parameters
- Type mismatches

**Common causes:**
- Unclear parameter documentation
- Missing examples

**Solutions:**
1. Add input examples for each script
2. Document parameter types and constraints
3. Add validation in scripts with helpful messages

---

## Trigger Issues

### Pattern: Skill Not Triggering
**Indicators:**
- User reports skill doesn't activate
- Traces show skill_used is empty or different

**Common causes:**
- Description doesn't cover trigger phrases
- Description too vague

**Solutions:**
1. Add more trigger phrases to description
2. Include specific keywords users might say
3. Add file type triggers if applicable

### Pattern: Wrong Skill Triggered
**Indicators:**
- Skill triggered for unrelated requests
- Overlap with other skills

**Common causes:**
- Description too broad
- Conflicting with other skills

**Solutions:**
1. Make description more specific
2. Add exclusions ("not for X")
3. Coordinate with related skills

---

## Analysis Checklist

When analyzing traces, check:

- [ ] Success rate across all traces
- [ ] Average turn count (should be <5)
- [ ] Token usage patterns
- [ ] Common error messages
- [ ] Tool usage patterns
- [ ] Retry patterns
- [ ] Response quality in successful traces
