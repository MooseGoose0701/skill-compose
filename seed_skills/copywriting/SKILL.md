---
name: copywriting
description: >
  Generate brand-aligned copy with precise constraints for every touchpoint. Use this skill when a user
  needs a tagline, brand philosophy statement, brand voice definition, business card text, social media
  bio, social media cover text, brand manifesto, or any short-form copy that must fit strict character
  and word limits within a brand identity context.
---

# Brand Copywriting Constraints

A lightweight constraint reference for brand copy. The LLM already knows how to write — this skill provides the specific limits, structures, and rules that turn generic copy into brand-precise copy.

---

## TAGLINE RULES

A tagline is the single most compressed expression of a brand. It appears on logos, business cards, social covers, and packaging.

### Structure

- **Length**: 3-5 words maximum. No exceptions.
- **No period** at the end (taglines are not sentences).
- **No brand name** in the tagline (it appears alongside, not inside).

### Approved Patterns

| Pattern | Example | When to Use |
|---------|---------|-------------|
| Imperative verb | "Think Different" | Action-oriented brands |
| Statement | "Beauty Outside. Beast Inside." | Dual-nature positioning |
| Noun phrase | "The Ultimate Driving Machine" | Category ownership |
| Question | "What's in Your Wallet?" | Engagement / curiosity |

### Memorability Test

Before finalizing, check:
1. Can you say it in one breath without pausing?
2. Does it sound natural spoken aloud, not just on paper?
3. Does it work without context — would someone understand the vibe even without seeing the brand?

### Avoid

- Generic superlatives ("The Best", "World-Class", "Premium")
- Puns that require explanation
- Industry jargon the target audience wouldn't use casually
- More than one clause or conjunction

---

## BRAND VOICE SPECTRUM

Define the brand voice along four axes. Each axis is a continuum — pick a position for the brand.

| Axis | Left Pole | Right Pole | What It Governs |
|------|-----------|------------|-----------------|
| **Formality** | Formal | Casual | Vocabulary, contractions, sentence structure |
| **Tone** | Serious | Playful | Humor, metaphor, punctuation style |
| **Complexity** | Technical | Accessible | Jargon level, explanation depth |
| **Energy** | Reserved | Bold | Exclamation, caps, directness |

### Example Voice Profile

```
Brand: Aether Coffee
Formality:  ████████░░  (8/10 — leans formal, no slang)
Tone:       ███░░░░░░░  (3/10 — mostly serious, quiet confidence)
Complexity: ██░░░░░░░░  (2/10 — very accessible, no jargon)
Energy:     █████░░░░░  (5/10 — balanced, neither loud nor whispered)

Voice summary: Calm authority. Speaks like a knowledgeable barista
who respects your time — precise, unhurried, no fluff.
```

### Applying Voice

Once defined, the voice profile governs ALL copy: tagline tone, philosophy register, business card formality, social bio energy. Never break character across touchpoints.

---

## BRAND PHILOSOPHY MANIFESTO

The brand philosophy is a 3-5 paragraph statement (150-300 words) that articulates WHY the brand exists and WHAT it believes. This is distinct from the *design* philosophy (which governs visual aesthetics).

### Structure

| Paragraph | Content | Purpose |
|-----------|---------|---------|
| 1 | The tension or problem | Why does this brand need to exist? |
| 2 | The brand's core belief | What does it stand for? What principle drives it? |
| 3 | How the belief manifests | How does this belief shape what the brand does? |
| 4 (optional) | The vision | Where is this heading? What future does the brand enable? |
| 5 (optional) | The invitation | Bring the reader in — "This is for people who..." |

### Writing Rules

- First person plural ("We believe...") or third person ("The brand exists to...")
- Present tense throughout — philosophies are timeless, not historical
- No bullet points — flowing prose only
- Every sentence must pass the "so what?" test: if it could apply to any brand, cut it
- Concrete over abstract: "We roast in 12-gram batches" beats "We pursue quality"

### Avoid

- Mission-statement clichés ("leveraging synergies", "empowering stakeholders")
- Vague values ("innovation", "excellence", "passion") without concrete grounding
- More than 300 words — a manifesto that needs scrolling has lost its power

---

## BUSINESS CARD COPY

### Content Slots

| Slot | Content | Max Length | Example |
|------|---------|-----------|---------|
| **Name** | Full name (or placeholder) | 30 chars | `[Your Name]` |
| **Title** | Role / position | 2-4 words | `Founder & Head Roaster` |
| **Email** | Contact email | — | `[email@example.com]` |
| **Phone** | Phone number | — | `[+1 (555) 000-0000]` |
| **Website** | URL without protocol | — | `[yoursite.com]` |
| **Address** | City + Country or full | 1 line | `[City, Country]` |
| **Tagline** | Brand tagline | 3-5 words | From tagline rules above |

### Hierarchy

The name is always the largest text element. Title is subordinate (smaller size, lighter weight). Contact details are grouped, smallest text, consistent alignment.

### Placeholder Convention

When creating a template (not for a specific person), use square-bracket placeholders:
- `[Your Name]`, `[Your Title]`, `[email@example.com]`, `[+1 (555) 000-0000]`, `[yoursite.com]`

---

## SOCIAL MEDIA COPY

### Bio (Profile Description)

- **Maximum**: 160 characters (Twitter/X limit; works everywhere)
- **Structure**: `[What you do] + [For whom or how] + [Optional tagline]`
- **Example**: `Small-batch coffee roasted for design professionals. Fuel for focus.`
- No hashtags in the bio — they look desperate
- No emojis unless the brand voice is ≥7/10 on the Playful axis

### Cover Text

The social media cover image contains minimal text — the visual does the heavy lifting.

- **Brand name**: always present, prominent
- **Tagline**: one line, 3-5 words (from tagline rules)
- **Supporting line** (optional): max 10 words, descriptive not promotional
- **Total text on cover**: never more than 15 words combined
- **Minimum font size**: 24pt (must be legible on mobile at 375px screen width)

---

## CONTEXT-SPECIFIC LENGTH LIMITS

Quick reference for maximum copy lengths across all brand touchpoints:

| Context | Max Words | Max Characters | Notes |
|---------|-----------|---------------|-------|
| Tagline | 5 | 35 | No period, no brand name |
| Brand philosophy | 300 | — | 3-5 paragraphs |
| Business card name | 4 | 30 | Full name only |
| Business card title | 4 | 30 | Role descriptor |
| Social bio | 25 | 160 | Single line |
| Social cover tagline | 5 | 35 | Same as tagline |
| Social cover support line | 10 | 60 | Optional descriptor |
| Brand spec section headers | 4 | — | Short and scannable |

---

## NAMING CONVENTIONS

When the user has not provided a brand name, generate one following these principles:

- **1-2 words** maximum (compounds like "Airbnb" count as one)
- **Easy to spell** after hearing it once
- **Easy to pronounce** in English (and ideally internationally)
- **Domain-friendly**: avoid special characters, hyphens, numbers
- **Not generic**: must feel ownable, not like a dictionary word alone

### Name Generation Approaches

| Approach | Example | When to Use |
|----------|---------|-------------|
| Coined word | Spotify, Hulu | Tech / digital brands |
| Compound | Airbnb, YouTube | Descriptive + memorable |
| Real word (recontextualized) | Apple, Amazon | Bold category disruption |
| Foreign word | Audi (Latin: "listen") | Sophistication, heritage |
| Abbreviation | IBM, BMW | Only if full name is established |

Propose 2-3 name options with brief rationale. Let the user choose or say "surprise me" to pick the strongest.
