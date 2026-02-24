---
name: ai-writing-detection
description: Comprehensive AI writing detection patterns and methodology. Provides vocabulary lists, structural patterns, model-specific fingerprints, and false positive prevention guidance. Use when analyzing text for AI authorship or understanding detection patterns.
allowed-tools: Read, Grep, Glob, WebFetch, WebSearch
---

# AI Writing Detection Reference

Expert-level knowledge base for detecting AI-generated text, compiled from academic research, commercial detection tools, and empirical analysis.

## Quick Reference: High-Confidence Signals

These indicators strongly suggest AI authorship when found together:

### Vocabulary Red Flags
**High-signal words** (50-700x more common in AI text):
- "delve", "tapestry", "nuanced", "multifaceted", "underscore"
- "intricate interplay", "played a crucial role", "complex and multifaceted"
- "paramount", "pivotal", "meticulous", "holistic", "robust"
- "stands/serves as", "marking a pivotal moment", "underscores its importance"

**Overused phrases**:
- "It's important to note that..."
- "In today's fast-paced world..."
- "At its core..."
- "Without further ado..."
- "Let me explain..."

See [reference/vocabulary-patterns.md](reference/vocabulary-patterns.md) for complete lists.

### Structural Red Flags
- **Uniform sentence lengths**: 12-18 words consistently (low burstiness)
- **Tricolon structures**: "research, collaboration, and problem-solving"
- **Em dash overuse**: AI uses em dashes in a formulaic way to mimic "punched up" sales writing, especially in parallelisms ("it's not X — it's Y"); swapping punctuation doesn't fix the underlying emphasis pattern
- **Perfect paragraph uniformity**: All paragraphs same approximate length
- **Template conclusions**: "In summary...", "In conclusion..."
- **Negative parallelisms**: "It's not about X; it's about Y"
- **Elegant variation**: Cycling through synonyms to avoid repetition
- **False ranges**: "From X to Y" with incoherent endpoints

See [reference/structural-patterns.md](reference/structural-patterns.md) for details.

### Content Red Flags
- **Importance puffery**: "marking a pivotal moment in history"
- **Ecosystem/conservation claims** without citations
- **"Challenges and Future" sections** following rigid formula
- **Promotional language**: "nestled in", "stunning natural beauty", "boasts"
- **Superficial analyses**: "-ing" phrases attributing significance to facts

See [reference/content-patterns.md](reference/content-patterns.md) for details.

### Formatting Red Flags
- **Title Case** in all section headings
- **Excessive boldface** (every key term bolded)
- **Inline-header lists**: `**Bold Header**: description` pattern
- **Emojis** in formal content or headings
- **Subject lines** in non-email contexts

See [reference/formatting-patterns.md](reference/formatting-patterns.md) for details.

### Markup Red Flags (Definitive)
- **turn0search0, turn0image0**: ChatGPT reference markers
- **contentReference[oaicite:]**: ChatGPT reference bugs
- **utm_source=chatgpt.com**: URL tracking (definitive)
- **Markdown in wikitext**: ## headers, **bold**, [text](url)
- **grok_card XML tags**: Grok/X specific

See [reference/markup-artifacts.md](reference/markup-artifacts.md) for details.

### Citation Red Flags
- **Broken external links** that never existed (no archive)
- **Invalid DOIs/ISBNs**: Checksum failures
- **Declared but unused references**: Cite errors
- **Placeholder values**: `url=URL`, `date=2025-XX-XX`

See [reference/citation-patterns.md](reference/citation-patterns.md) for details.

### Tone Red Flags
- Passive and detached voice throughout
- Absence of first-person pronouns where expected
- Consistent formality with no stylistic variation
- Over-politeness and excessive hedging

## Detection Methodology

### Multi-Layer Analysis Approach

**Layer 1: Technical Artifact Scan (Definitive)**
- Check for turn0search/oaicite markers (ChatGPT)
- Check for utm_source=chatgpt.com in URLs
- Check for grok_card tags (Grok)
- Check for Markdown in non-Markdown contexts
- If found: Definitive AI involvement

**Layer 2: Vocabulary Pattern Matching**
- Scan for overused AI words/phrases
- Count frequency of flagged terms
- Look for clusters of high-signal vocabulary
- Check for importance/symbolism phrases

**Layer 3: Structural Analysis**
- Observe sentence length variation (uniform = AI signal)
- Check paragraph uniformity
- Identify repetitive syntactic templates (tricolons, negative parallelisms)
- Look for elegant variation (synonym cycling)
- Check for false ranges

**Layer 4: Content Pattern Analysis**
- Check for importance puffery and promotional language
- Look for "Challenges and Future" formula
- Check for ecosystem/conservation claims without citations
- Identify superficial analyses with "-ing" attributions

**Layer 5: Citation Verification**
- Test external links - do they exist?
- Verify DOI/ISBN checksums
- Check for declared but unused references
- Look for placeholder values

**Layer 6: Formatting Analysis**
- Check heading capitalization (Title Case = signal)
- Count bold phrases per paragraph
- Look for inline-header list patterns
- Check for emojis in formal content

**Layer 7: Stylometric Observation**
- Pronoun usage patterns (missing first-person?)
- Tone consistency (too uniform = AI signal)
- Punctuation patterns (em dash overuse? curly quotes?)

**Layer 8: Coherence Check**
- Do paragraphs build a coherent argument?
- Are concepts repeated with different words?
- Do transitions actually connect ideas?

**Layer 9: Confidence Scoring**
- Weight multiple signals together
- Require corroborating evidence (3+ signals minimum)
- Apply context-specific adjustments
- Check for mitigating factors (human signals)
- Consider ineffective indicators (don't use them)

## Model-Specific Patterns

Different AI models have distinct "fingerprints":

| Model | Key Tells | Technical Artifacts |
|-------|-----------|---------------------|
| ChatGPT/GPT-4 | "delve" (pre-2025), "tapestry", tricolons, em dashes, curly quotes | turn0search, oaicite, utm_source=chatgpt.com |
| Claude | Analytical structure, extended analogies, cautious qualifications | None (uses straight quotes, no tracking) |
| Gemini | Conversational synthesis, fact-dense paragraphs | None (uses straight quotes, no tracking) |
| DeepSeek | Similar to ChatGPT, curly quotes | Curly quotation marks |
| Grok | X/Twitter integration | `<grok_card>` XML tags |
| Perplexity | Source-focused output | `[attached_file:1]`, `[web:1]` tags |

**Important dates**:
- ChatGPT launched: **November 30, 2022** (text before this is almost certainly human)
- "delve" usage dropped: **2025** (still signals pre-2025 ChatGPT)

See [reference/model-fingerprints.md](reference/model-fingerprints.md) for detailed model patterns.

## False Positive Prevention

**Critical requirements**:
- Minimum 200 words for reliable analysis
- Never flag on single indicators alone
- Use ensemble scoring (multiple signals required)

**High false-positive risk groups**:
- Non-native English speakers (61% false positive rate in research)
- Technical/formal writing
- Neurodivergent writers
- Content using grammar correction tools

**Ineffective indicators** (do NOT rely on these):
- Perfect grammar alone
- "Bland" or "robotic" prose
- "Fancy" or unusual vocabulary
- Letter-like formatting alone
- Conjunctions starting sentences

**Signs of human writing**:
- Text from before November 30, 2022
- Ability to explain editorial choices
- Personal anecdotes with verifiable details
- Minor errors and natural quirks

See [reference/false-positive-prevention.md](reference/false-positive-prevention.md) for detailed guidance.

## Analysis Output Format

Structure findings as:

```
**Overall Assessment**: [Likely AI / Possibly AI / Likely Human / Inconclusive]
**Confidence**: [Low / Medium / High]

**Summary**: 2-3 sentence overview

**Evidence Found**:
- [Category]: [Specific indicator] - "[Quote from text]"
- [Category]: [Specific indicator] - "[Quote from text]"

**Mitigating Factors**: [Elements suggesting human authorship]

**Caveats**: [Limitations, alternative explanations]
```

## Key Principles

1. **No certainty claims** - AI detection is probabilistic
2. **Multiple signals required** - Single indicators prove nothing
3. **Context matters** - Academic writing differs from blogs
4. **Stakes awareness** - False accusations cause real harm
5. **Evolving field** - Detection methods require constant updates

## Reference Files

- [vocabulary-patterns.md](reference/vocabulary-patterns.md) - Complete word/phrase lists with frequencies
- [structural-patterns.md](reference/structural-patterns.md) - Sentence, paragraph, and discourse patterns
- [content-patterns.md](reference/content-patterns.md) - Importance puffery, promotional language, content tells
- [formatting-patterns.md](reference/formatting-patterns.md) - Title case, boldface, emojis, visual patterns
- [markup-artifacts.md](reference/markup-artifacts.md) - Technical artifacts: turn0search, oaicite, Markdown, tracking
- [citation-patterns.md](reference/citation-patterns.md) - Broken links, invalid identifiers, hallucinated references
- [model-fingerprints.md](reference/model-fingerprints.md) - GPT, Claude, Gemini, Grok, Perplexity specific tells
- [false-positive-prevention.md](reference/false-positive-prevention.md) - Avoiding false accusations, ineffective indicators

## Sources

This knowledge base synthesizes research from:
- Stanford HAI (DetectGPT, bias studies)
- GPTZero, Originality.ai, Turnitin, Pangram methodologies
- Academic papers on stylometry and discourse analysis
- Empirical studies on detection accuracy and limitations
- Wikipedia:WikiProject AI Cleanup field guide (2025)
- Community-documented patterns from Wikipedia editing
