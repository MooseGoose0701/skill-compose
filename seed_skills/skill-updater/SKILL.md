---
name: skill-updater
description: Update existing skills based on feedback. Use when users want to improve or modify an existing skill by providing feedback about what needs to change. Triggers on requests like "update this skill", "improve the skill based on feedback", "fix the skill", or when users provide feedback about skill performance.
license: Complete terms in LICENSE.txt
---

# Skill Updater

This skill provides guidance for updating existing skills based on user feedback.

## When to Use

Use this skill when:
- User provides feedback about an existing skill's performance
- User wants to improve or modify a skill
- User reports issues or bugs with a skill
- User wants to add new functionality to an existing skill

## Required Inputs

1. **Skill Path**: Path to the skill directory or .skill file to update
2. **Feedback**: Description of what needs to change, improve, or be fixed

## Update Process

### Step 1: Load and Understand the Skill

Use the analyze_skill.py script to get a quick overview:

```bash
scripts/analyze_skill.py <skill-path>
```

This shows:
- Skill name and description
- SKILL.md line/word count
- All bundled resources (scripts/, references/, assets/)
- Any structural issues

Then read SKILL.md to understand the detailed instructions:

```bash
cat <skill-path>/SKILL.md
```

For .skill files (zip archives), extract first:

```bash
unzip <skill-path>.skill -d /tmp/skill-extract/
```

### Step 2: Analyze the Feedback

Categorize the feedback into one or more types:

| Type | Example Feedback | Typical Changes |
|------|-----------------|-----------------|
| Bug fix | "The script fails when..." | Fix scripts, add error handling |
| Missing feature | "It should also support..." | Add new functionality |
| Clarity | "Instructions are confusing" | Improve SKILL.md documentation |
| Performance | "Too slow/uses too much context" | Optimize scripts, reduce SKILL.md |
| Trigger | "Doesn't activate when I say..." | Update description in frontmatter |

### Step 3: Plan the Changes

Before making changes, create a clear plan:

1. List specific files to modify
2. Describe what changes each file needs
3. Identify any new files to create or files to delete
4. Consider impact on other parts of the skill

### Step 4: Implement Changes

Apply changes following skill design principles:

**For SKILL.md changes:**
- Keep body under 500 lines
- Use imperative form
- Move detailed content to references/ if approaching limit
- Ensure frontmatter description captures all trigger scenarios

**For script changes:**
- Test scripts after modification
- Maintain existing interfaces unless feedback requires changes
- Add error handling for reported edge cases

**For reference changes:**
- Keep references one level deep from SKILL.md
- Update SKILL.md to reference new files

### Step 5: Validate and Package

After implementing changes:

```bash
# Validate the skill
scripts/quick_validate.py <skill-path>

# Package if validation passes
scripts/package_skill.py <skill-path>
```

## Common Update Patterns

### Pattern 1: Fixing Script Bugs

1. Read the failing script
2. Identify the bug based on feedback
3. Apply fix
4. Test with the scenario from feedback
5. Package

### Pattern 2: Improving Trigger Accuracy

1. Review current frontmatter description
2. Identify missing trigger phrases from feedback
3. Update description to include new triggers
4. Ensure description remains concise (<100 words)

### Pattern 3: Adding New Functionality

1. Determine if new functionality needs:
   - New script in scripts/
   - New reference in references/
   - New asset in assets/
   - Updates to SKILL.md instructions
2. Implement required components
3. Update SKILL.md to document new functionality
4. Test end-to-end

### Pattern 4: Reducing Context Usage

1. Identify verbose sections in SKILL.md
2. Move detailed content to references/
3. Replace with concise summary + link
4. Remove redundant examples
5. Verify skill still functions correctly

## Best Practices

- **Minimal changes**: Only change what the feedback requires
- **Test after changes**: Run scripts and validate skill structure
- **Preserve intent**: Maintain the skill's original purpose
- **Document changes**: Update SKILL.md if behavior changes
- **Version awareness**: If the skill has users, consider backward compatibility
