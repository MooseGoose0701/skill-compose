# Formatting Patterns in AI-Generated Text

Visual and typographical formatting patterns that indicate AI authorship. These patterns often result from AI chatbot default behaviors and prompt engineering instructions.

## Title Case in Section Headings

### The Pattern

AI strongly tends to capitalize all main words in section headings.

**AI tendency**:
```
Global Context: Critical Mineral Demand
Strategic Negotiations and Global Partnerships
High-Stakes Deals: Glencore, China, and Russia
```

**Wikipedia/human convention**:
```
Global context: critical mineral demand
Strategic negotiations and global partnerships
High-stakes deals: Glencore, China, and Russia
```

### Why This Happens

Most AI chatbots are trained on data where headlines and section titles use title case. Wikipedia style prefers sentence case.

### Detection

Check if ALL section headings in a document use title case. A mix of styles is more human; consistent title case throughout is an AI signal.

## Excessive Boldface

### The Pattern

AI may bold various phrases for emphasis in an excessive, mechanical manner, especially:
- Every instance of a chosen word or phrase
- "Key takeaways" style emphasis
- Important terms in every paragraph

### Examples

> "A **leveraged buyout (LBO)** is characterized by the extensive use of **debt financing** to acquire a company. This **financing structure** enables **private equity firms** and **financial sponsors** to control businesses..."

> "**OKRs** (Objectives and Key Results), **KPIs** (Key Performance Indicators), and **visual strategy tools** such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**."

### Why This Happens

AI inherits boldface patterns from:
- README files
- Fan wikis and how-tos
- Sales pitches and slide decks
- Listicles

### Detection

Count bolded phrases per paragraph. More than 3-4 bold phrases in a short paragraph is suspicious.

## Inline-Header Vertical Lists

### The Pattern

AI outputs often include vertical lists with this specific format:
- Number/bullet followed by
- **Boldfaced inline header** followed by
- Colon and descriptive text

### Examples

**Numbered variant**:
```
1. **Historical Context Post-WWII Era**: The world was rapidly changing...
2. **Nuclear Arms Race**: Following the U.S. atomic bombings...
3. **Key Figures Edward Teller**: A Hungarian physicist who advocated...
```

**Bulleted variant**:
```
- **Concept and Lyrics** — The artist defines the theme and lyrics of the song.
- **AI Melodic Drafts** — AI produces different melodies following the prompt.
- **Human Supervision and Enhancement** — Producers adjust the instrumentation.
```

### Broken List Markers

Instead of proper wikitext/Markdown, AI may output:
- Literal bullet characters (•)
- Hyphens (-)
- En dashes (–)
- Hash symbols (#)
- Emojis as list markers

This occurs when AI output is copied as plain text.

### Detection

Look for:
1. Consistent `**Header**: description` pattern
2. Bullet points as literal characters instead of proper syntax
3. Every list item following identical structure

## Emoji Usage

### The Pattern

AI chatbots sometimes decorate content with emojis, especially:
- Section headings prefixed with emojis
- Bullet points marked with emojis
- Emphasis emojis inline

### Examples

> "Let's decode exactly what's happening here:
> 🧠 **Cognitive Dissonance Pattern**:
> You've proven authorship, demonstrated originality..."

> "🪷 Traditional Sanskrit Name: Trikoṇamiti
> 🕰️ 1. Vedic Era (c. 1200 BCE – 500 BCE)
> 🔭 2. Sine of the Bow: Sanskrit Terminology"

### Where It Appears

Most noticeable in:
- Talk page comments
- Draft articles
- Informal communications

### Detection

Any emoji usage in formal article content is a strong AI signal. In talk pages, emoji-decorated headers or lists are suspicious.

## Over-Use of Headers in Short Content

### The Pattern

AI defaults to explicit section headers even when:
- Content is short (under 500 words)
- Prose would flow more naturally
- Headers fragment a coherent argument

### Why This Happens

AI chatbots receive instructions like:
> "Use a single main title (#) and clear primary subheadings (##)"

### Example

A 300-word response with:
```
## Introduction
[2 sentences]
## Background
[3 sentences]
## Analysis
[3 sentences]
## Conclusion
[2 sentences]
```

### Human Pattern

Humans typically use headers when genuinely helpful for navigation in longer content, not mechanically for every topic shift.

## Excessive Parallelism in Lists

### The Pattern

Every element in AI-generated lists follows identical grammatical structure.

### Example

```
- Improving efficiency
- Reducing costs
- Enhancing quality
- Increasing satisfaction
```

All present participle ("-ing") form, identical structure.

### Human Pattern

Some parallel structure with natural variation:
```
- Better efficiency
- Cost reductions
- Enhanced quality
- Higher user satisfaction
```

## Curly Quotation Marks

### The Pattern

ChatGPT and DeepSeek typically use curly quotes ("..." and '...') instead of straight quotes ("..." and '...').

### Technical Details

| Character | Name | AI Usage |
|-----------|------|----------|
| " " | Curly double quotes | ChatGPT, DeepSeek |
| ' ' | Curly single quotes/apostrophes | ChatGPT, DeepSeek |
| " " | Straight double quotes | Human default, Claude, Gemini |
| ' | Straight apostrophe | Human default, Claude, Gemini |

### Caveats

- Microsoft Word has "smart quotes" feature
- macOS/iOS auto-convert quotes
- Citation tools may preserve curly quotes from sources
- Some fonts display curly quotes as straight

### Detection

Consistent curly quotes throughout text (especially mixed with other AI signals) suggests ChatGPT/DeepSeek use. Claude and Gemini typically don't use curly quotes.

## Subject Lines in Messages

### The Pattern

AI-generated messages sometimes begin with email-style subject lines:

### Examples

> "Subject: Request for Permission to Edit Wikipedia Article - 'Dog'"

> "Subject: Edit Request for Wikipedia Entry"

> "Subject: Request for Review and Clarification Regarding Draft Article"

### Why This Happens

AI was likely asked to draft a message/email, and the user copy-pasted the entire output including the subject line.

### Detection

Any text beginning with "Subject:" in a non-email context is a strong AI signal.

## Over-Organized Structure

### Pattern Summary

AI defaults to explicit organization even when unnecessary:
- Numbered steps for simple explanations
- Bullet points where prose flows better
- Section headers for short content
- Explicit "First... Second... Third..." sequencing

### Human Pattern

- Organization emerges from content needs
- Prose allowed to flow without constant structuring
- Headers used purposefully, not mechanically

## Detection Checklist

When analyzing formatting:

- [ ] Are all section headings in Title Case?
- [ ] Is there excessive boldface (>3 per paragraph)?
- [ ] Are there inline-header lists (`**Bold**: text` pattern)?
- [ ] Are there emojis in formal content?
- [ ] Are list markers literal characters (•, –) instead of proper syntax?
- [ ] Is the content over-organized with unnecessary headers?
- [ ] Are all list items perfectly parallel in structure?
- [ ] Are curly quotes used consistently?
- [ ] Does text begin with "Subject:" inappropriately?
