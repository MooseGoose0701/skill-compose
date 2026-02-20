---
name: skills-planner
description: Plan which skills are needed to fulfill user requirements. Use when the user wants to design an agent workflow, plan skill composition, or determine what skills are needed for a task. Input includes user requirements and existing skills list. Output includes recommended existing skills, new skills to create, and a system prompt for the composed agent.
---

# Skills Planner

Plan and compose skills to fulfill user requirements efficiently.

## Workflow

1. **Analyze Requirements** - Understand user goals and constraints
2. **Evaluate Existing Skills** - Match requirements to available skills
3. **Identify Gaps** - Determine what capabilities are missing
4. **Design New Skills** - Specify requirements for missing skills (if any)
5. **Compose Agent** - Design system prompt for the agent using all skills
6. **Present Plan** - Output structured plan for user confirmation

## Input Requirements

Before planning, gather:
- **User Requirements**: What the user wants to accomplish
- **Existing Skills List**: Available skills with their descriptions

## Planning Process

### Step 1: Analyze Requirements

Break down user requirements into discrete capabilities:

```
User Request: "Build an agent that can analyze financial reports"

Required Capabilities:
1. PDF reading/parsing
2. Data extraction (tables, numbers)
3. Financial metrics calculation
4. Report generation
5. Visualization (charts)
```

### Step 2: Evaluate Existing Skills

For each capability, check if an existing skill covers it:

```
Capability: PDF reading/parsing
Existing Skill Match: pdf (extracts text/tables from PDFs) ✓

Capability: Financial metrics calculation
Existing Skill Match: None found ✗
```

**Selection Criteria:**
- Prefer skills that directly match the capability
- Consider skill scope (narrow and focused > broad and generic)
- Check for overlapping functionality to avoid redundancy

### Step 3: Identify Gaps

List capabilities not covered by existing skills. These become candidates for new skills.

**Gap Analysis Questions:**
- Is this capability truly necessary, or can existing skills be combined?
- Can the base model handle this without a skill?
- Is this capability reusable across other tasks?

### Step 4: Design New Skills (if needed)

For each gap, specify:

```yaml
skill_name: financial-analyzer
skill_requirements: |
  Purpose: Calculate and interpret financial metrics from extracted data

  Core Capabilities:
  - Calculate common ratios (P/E, ROE, debt-to-equity, etc.)
  - Identify trends across time periods
  - Flag anomalies or concerns
  - Generate insights in plain language

  Input: Structured financial data (revenue, expenses, assets, etc.)
  Output: Analysis report with metrics, trends, and recommendations

  Workflow:
  1. Validate input data completeness
  2. Calculate standard financial ratios
  3. Compare to industry benchmarks (if provided)
  4. Identify significant changes or outliers
  5. Generate narrative summary
```

**Principles for New Skills:**
- **Minimal**: Only create skills that provide significant value
- **Focused**: Each skill should do one thing well
- **Reusable**: Design for use beyond the immediate task
- **Claude-aware**: Only include knowledge Claude doesn't already have

### Step 5: Compose Agent System Prompt

Design a system prompt that orchestrates all selected skills:

```markdown
## System Prompt Template

You are a [AGENT_ROLE] agent specialized in [DOMAIN].

### Workflow
When processing requests:
1. [First step - e.g., understand the input]
2. [Second step - e.g., invoke relevant skill]
3. [Third step - e.g., process results]
4. [Final step - e.g., present output]

### Guidelines
- [Guideline 1 - e.g., always validate inputs first]
- [Guideline 2 - e.g., handle errors gracefully]
- [Guideline 3 - e.g., provide clear explanations]

### Output Format
[Specify expected output structure if applicable]
```

## Output Format

Present the plan in this structure:

```markdown
# Skills Plan for [User Task]

## 1. Existing Skills to Include

| Skill Name | Purpose in This Agent | Key Capabilities Used |
|------------|----------------------|----------------------|
| [name] | [why needed] | [specific features] |
| [name] | [why needed] | [specific features] |

> If no existing skills apply, write: "None - all required capabilities need new skills."

## 2. New Skills to Create

**Skills needed**: [skill-a], [skill-b], [skill-c] (or "None - existing skills cover all requirements")

### 2.1 [skill-a]

(Continue for each new skill...)

---

## 3. Proposed System Prompt

[Complete system prompt for the agent]

---

## 4. Additional Recommendations

- [Recommendation 1 - e.g., consider adding X capability later]
- [Recommendation 2 - e.g., this skill combination may have limitation Y]
- [Recommendation 3 - e.g., suggested testing approach]

---

**Please review and confirm this plan, or provide feedback for adjustments.**
```

## Example

**User Request**: "I need an agent that can process customer support tickets, categorize them, and draft responses"

**Existing Skills**: web-search, email-sender, sentiment-analyzer

**Output**:

```markdown
# Skills Plan for Customer Support Agent

## 1. Existing Skills to Include

| Skill Name | Purpose in This Agent | Key Capabilities Used |
|------------|----------------------|----------------------|
| sentiment-analyzer | Assess ticket urgency and customer mood | Sentiment scoring, emotion detection |

## 2. New Skills to Create

**Skills needed**: ticket-categorizer, response-drafter

### 2.1 ticket-categorizer

**Purpose**: Classify support tickets into predefined categories

**Requirements**:
- Parse ticket content (subject + body)
- Match against category definitions
- Handle multi-category tickets
- Provide confidence scores

**Workflow**:
1. Extract key phrases from ticket
2. Match against category keywords and patterns
3. Assign primary and secondary categories
4. Return categorization with confidence

**Input/Output**:
- Input: Ticket text (subject, body, metadata)
- Output: { category: string, subcategory: string, confidence: float }

### 2.2 response-drafter

**Purpose**: Generate contextual draft responses for support tickets

**Requirements**:
- Use ticket category and sentiment as context
- Apply company tone guidelines
- Include relevant knowledge base references
- Support multiple response templates

**Workflow**:
1. Analyze ticket intent and key issues
2. Select appropriate response template
3. Customize with specific details
4. Add relevant links/resources
5. Apply tone adjustments based on sentiment

**Input/Output**:
- Input: Ticket content, category, sentiment, knowledge base context
- Output: Draft response text with placeholders for review

---

## 3. Proposed System Prompt

You are a Customer Support Agent specialized in processing and responding to support tickets efficiently.

### Your Capabilities
You have access to the following skills:
- **sentiment-analyzer**: Use to assess customer mood and ticket urgency before categorizing
- **ticket-categorizer**: Use to classify tickets into appropriate categories
- **response-drafter**: Use to generate initial response drafts

### Workflow
When processing a support ticket:
1. Analyze sentiment to understand customer mood and urgency
2. Categorize the ticket to determine the issue type
3. Draft an appropriate response based on category and sentiment
4. Present the draft for human review before sending

### Guidelines
- Prioritize high-urgency tickets (negative sentiment + billing/account issues)
- Always maintain a helpful, empathetic tone
- Escalate complex technical issues to specialists
- Include relevant self-help resources when applicable

### Output Format
For each ticket, provide:
- Sentiment Assessment: [score and summary]
- Category: [primary] / [secondary if applicable]
- Urgency: [Low/Medium/High]
- Draft Response: [response text]
- Recommended Actions: [any escalation or follow-up needed]

---

## 4. Additional Recommendations

- Consider adding a knowledge-base-search skill for FAQ matching
- The ticket-categorizer should be trained on historical ticket data
- Test with edge cases: multi-issue tickets, non-English tickets, spam
- Monitor response quality and adjust tone guidelines as needed

---

**Please review and confirm this plan, or provide feedback for adjustments.**
```

## Key Principles

1. **Minimize skill count**: Fewer, well-designed skills > many narrow skills
2. **Leverage Claude's base capabilities**: Don't create skills for things Claude already knows
3. **Prefer existing skills**: Only create new skills when truly necessary
4. **Design for reusability**: New skills should be useful beyond the immediate task
5. **Clear boundaries**: Each skill should have a distinct, non-overlapping purpose
