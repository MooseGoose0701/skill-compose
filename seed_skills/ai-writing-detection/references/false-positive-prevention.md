# False Positive Prevention

Critical guidance for avoiding false accusations of AI authorship. False positives cause real harm - academic penalties, professional damage, and eroded trust.

## The False Positive Problem

### Documented Rates

| Population | False Positive Rate | Source |
|------------|---------------------|--------|
| Non-native English speakers | 61.3% | Stanford HAI |
| Non-native (worst detector) | 98% | Stanford HAI |
| Technical writing | 30-40% (estimated) | Various studies |
| Pre-1990 scientific abstracts | 5% flagged >90% AI confidence | PMC study |

### High-Profile Failures

**U.S. Constitution**: One detector flagged it with 98.53% AI certainty.

**Significance**: If detectors flag the Constitution as AI, they will flag many legitimate human texts.

## High-Risk Groups

### Non-Native English Speakers

**Why they're flagged**:
- Simpler vocabulary = lower perplexity = AI signal
- Lower lexical richness and syntactic complexity
- Use of common words and phrases (also common in AI)
- Fewer idioms and colloquialisms
- More formal register

**Stanford research finding**: "Both AI and non-native speakers use common words and phrases. Detectors learned to flag simplicity, not AI specifically."

**Mitigation**:
- Increase detection threshold for ESL contexts
- Weight vocabulary signals lower
- Focus on structural patterns instead
- Never flag based on vocabulary alone

### Neurodivergent Writers

**Why they're flagged**:
- Some exhibit repetitive patterns
- May have consistent sentence structures
- Formal or systematic writing styles
- Fewer stylistic variations

**Mitigation**:
- Don't assume uniformity = AI
- Consider individual writing patterns
- Focus on content accuracy, not style
- Never use AI detection for accessibility accommodations

### Technical and Academic Writers

**Why they're flagged**:
- Formal vocabulary (Latinate words)
- Structured organization
- Standard terminology
- Citation-heavy prose
- Predictable formats (IMRaD structure)

**Mitigation**:
- Domain-specific thresholds
- Compare against domain baseline
- Weight formatting signals lower
- Recognize genre conventions

### Users of Writing Tools

**Grammar tools** (Grammarly, ProWritingAid):
- Erase contractions (don't → do not)
- Remove idioms
- Smooth rhythm quirks
- Standardize punctuation

**Autocorrect effects**:
- Minor corrections can raise AI scores to 80%+

**Mitigation**:
- Ask about tool usage
- Acknowledge editing doesn't equal AI
- Focus on content, not surface polish

## Minimum Requirements

### Text Length

| Length | Reliability |
|--------|-------------|
| <50 words | Unreliable - do not assess |
| 50-100 words | Very low confidence only |
| 100-200 words | Low confidence |
| 200-500 words | Moderate confidence possible |
| 500+ words | Higher confidence assessments |

**Rule**: Never make high-confidence claims on texts under 200 words.

### Signal Requirements

**Minimum for any flag**:
- At least 2-3 corroborating signals from different categories
- Evidence from vocabulary AND structure AND/OR statistical features
- No single indicator ever sufficient

**For "Likely AI" assessment**:
- 4+ strong signals across multiple categories
- High-confidence vocabulary patterns (multiple extreme-frequency terms)
- Structural uniformity evidence
- No strong mitigating factors

## Detection Thresholds

### Suggested Calibration

```
Assessment: Likely Human
- 0-1 weak signals
- High burstiness
- Personal anecdotes/experiences present
- Idiomatic language
- Natural errors/informality

Assessment: Inconclusive
- 2-3 signals present
- Mixed indicators
- Some AI patterns + some human patterns
- Insufficient text length

Assessment: Possibly AI
- 3-4 signals present
- Multiple vocabulary matches
- Low-to-moderate burstiness
- Some structural uniformity

Assessment: Likely AI
- 5+ signals across categories
- Multiple extreme-frequency terms
- Very low burstiness
- Strong structural uniformity
- No personal/experiential content
```

### Confidence Levels

| Confidence | Requirements |
|------------|--------------|
| High | 5+ signals, multiple categories, 500+ words, no mitigating factors |
| Medium | 3-4 signals, 200+ words, limited mitigating factors |
| Low | 2-3 signals, mixed evidence, some mitigating factors |

## Mitigating Factors

### Strong Human Signals

Presence of these reduces AI likelihood:

1. **Personal anecdotes**: "When I was working at..."
2. **Specific dated experiences**: "Back in 2019..."
3. **Emotional expression**: Genuine frustration, humor, uncertainty
4. **Idiomatic language**: "It's not rocket science"
5. **Colloquialisms**: Regional expressions, informal language
6. **Minor errors**: Typos, grammar slips, word choice quirks
7. **Non-standard formatting**: Unusual paragraph breaks, creative structure
8. **First-person narrative**: "I think...", "In my experience..."
9. **Specific local references**: Names, places, events known to author

### Context That Reduces Suspicion

- Known human author with established style
- Writing matches author's previous work
- Contains verifiable personal information
- References events/knowledge not in AI training
- Shows evolution of thought (crossed-out sections, revisions)

## What NOT To Do

### Never

1. **Flag based on single indicators**: "This says 'delve' so it's AI"
2. **Ignore context**: "This technical paper sounds formal = AI"
3. **Assume polished = AI**: "No typos therefore AI"
4. **Trust single tool scores**: "GPTZero says 80% so it's AI"
5. **Make certain claims**: "This is definitely AI-generated"
6. **Ignore mitigating factors**: "Despite personal stories, the vocab is AI-like"
7. **Apply same thresholds universally**: Same standards for blogs and academic papers

### Red Flags in Your Own Analysis

You may be making a false positive if:

- Your conclusion rests on vocabulary alone
- You're ignoring strong human signals
- The text length is under 200 words
- You're not considering the author's background
- You're applying generic thresholds to specialized content
- You feel certain (certainty is never warranted)

## Domain-Specific Guidance

### Academic Writing

**Expect**:
- Formal vocabulary
- Structured organization
- Hedging language ("may", "could", "suggests")
- Standard formats

**Adjust for**:
- Higher tolerance for formal terms
- Lower weight on structural uniformity
- Focus on content originality, not style

### Technical Documentation

**Expect**:
- Precise terminology
- Step-by-step structure
- Consistent formatting
- Low stylistic variation

**Adjust for**:
- Genre conventions
- Terminology requirements
- Format expectations

### Creative Writing

**Expect**:
- More stylistic variation
- Personal voice
- Idiomatic language

**Higher sensitivity to**:
- Flat affect
- Missing personal perspective
- Generic descriptions

### Business Communication

**Expect**:
- Professional tone
- Some formal vocabulary
- Clear structure

**Adjust for**:
- Professional writing training
- Corporate style guides
- Template usage (legitimate)

## Ensemble Approach

### Why Single Tools Fail

Each tool has blind spots:
- GPTZero: Non-native speaker bias
- Originality.ai: Technical writing bias
- Turnitin: Short text unreliability

### Recommended Process

```
1. Gather text context
   - Who wrote it?
   - What type of writing?
   - What's the stakes?

2. Apply multiple detection methods
   - Vocabulary analysis
   - Structural analysis
   - Statistical features
   - (Optional) Commercial tool

3. Weight results appropriately
   - Consider context biases
   - Apply domain adjustments
   - Require corroboration

4. Present findings appropriately
   - State confidence level
   - List specific evidence
   - Acknowledge limitations
   - Note mitigating factors
```

## Responsible Reporting

### Output Format

```
**Assessment**: [Likely AI / Possibly AI / Inconclusive / Likely Human]
**Confidence**: [Low / Medium / High]

**Evidence**:
- [Specific finding 1 with quote]
- [Specific finding 2 with quote]

**Mitigating Factors**:
- [Factors suggesting human authorship]

**Important Caveats**:
- [Limitations of this analysis]
- [Alternative explanations]
- [Context considerations]

**Recommendation**: [What action to take, if any]
```

### Language Guidelines

**Do say**:
- "This text shows patterns consistent with AI generation"
- "Several indicators suggest possible AI involvement"
- "The analysis is inconclusive"
- "With medium confidence, this may be AI-generated"

**Don't say**:
- "This is AI-generated" (certainty)
- "The author clearly used AI" (accusation)
- "This proves AI authorship" (overstatement)
- "No human would write this" (assumption)

## Ineffective Indicators

These are commonly cited "tells" that are actually NOT reliable for AI detection:

### Perfect Grammar

**Myth**: "AI has perfect grammar, so perfect grammar means AI."

**Reality**: Many skilled human writers produce grammatically flawless text. This is especially weak as an indicator.

### "Bland" or "Robotic" Prose

**Myth**: "AI writing is bland and robotic."

**Reality**: Modern LLMs tend toward **effusive and verbose** prose, not bland prose. The pattern is formulaic but not necessarily "robotic" to those unfamiliar with AI writing.

### "Fancy" or Unusual Words

**Myth**: "AI uses fancy vocabulary, so unusual words indicate AI."

**Reality**: **Low-frequency and unusual words are LESS likely in AI-generated text** because they are statistically less common in training data. AI regresses toward common vocabulary, not unusual words.

Exception: Specific overused AI vocabulary (delve, tapestry, etc.) is different from generally "fancy" vocabulary.

### Letter-Like Writing (Alone)

**Myth**: "If it has salutations and valedictions, it's AI."

**Reality**: Letters, emails, and formal messages have conventionally used these elements. New editors often format talk page comments formally, especially:
- Those accustomed to formal communication
- School assignment participants
- Those mistaking talk pages for email

AI-generated talk page messages do have other tells (vertical lists, placeholders, abrupt cutoffs).

### Conjunctions Starting Sentences (Alone)

**Myth**: "AI starts sentences with conjunctions like 'And' or 'But'."

**Reality**: While LLMs overuse connecting words, starting sentences with coordinating conjunctions has precedent and is accepted by many style guides. This alone proves nothing.

### Bizarre Wikitext

**Myth**: "Broken or bizarre wikitext indicates AI."

**Reality**: Bizarrely placed HTML tags like `<span>` are more often caused by:
- Browser extensions
- Known bugs with Wikipedia's content translation tool
- VisualEditor artifacts

Misplaced syntax like `''Catch-22 i''s` (rendering "Catch-22 is") is more indicative of VisualEditor mistakes than AI.

**AI wikitext errors** look different: Markdown syntax, non-existent templates, hallucinated categories.

## Obsolete Indicators (Historical)

These patterns were common in older AI models but are less frequent now:

### Didactic Disclaimers (2022-2024)

Older LLMs (~2023) often added disclaimers like:

```
"It's important to remember..."
"It's crucial to note..."
"It's worth noting that..."
```

These appeared especially around safety or controversial topics. By 2025, this pattern has declined significantly.

### Section Summaries and Conclusions (Older Models)

When generating longer outputs, older LLMs often:
- Added sections titled "Conclusion"
- Ended paragraphs by summarizing and restating core ideas

```
"In summary, the educational and training trajectory..."
"In conclusion, the research demonstrates..."
```

This pattern is less common in newer models.

## Signs of Human Writing

Positive indicators that suggest human authorship:

### Pre-ChatGPT Date

**ChatGPT launched November 30, 2022.** Text added to Wikipedia before this date is very unlikely to be AI-generated.

If an edit was made before November 30, 2022, AI use can be safely ruled out for that revision.

### Ability to Explain Editorial Choices

If an editor can explain why they made specific edits or how errors occurred (e.g., providing the correct link after a broken one was flagged), this suggests human authorship.

### Personal Anecdotes with Verifiable Details

Genuine first-person experiences with specific, verifiable details:
- "When I was working at [company] in [year]..."
- "Back in 2019, I..."
- Specific names, places, events known to the author

### Non-Standard Formatting

Creative or unusual structure that doesn't follow templates:
- Unconventional paragraph breaks
- Personal voice and style
- Idiomatic language and regional expressions

### Evolution of Thought

Signs of human drafting process:
- Crossed-out sections
- Revision marks
- Changed approaches within the same document

### Minor Errors and Quirks

Natural human imperfections:
- Typos
- Minor grammar slips
- Word choice quirks
- Inconsistent formatting

## Final Checklist

Before making any assessment:

- [ ] Text is 200+ words
- [ ] Multiple signals from different categories
- [ ] Considered author context
- [ ] Adjusted for domain/genre
- [ ] Checked for mitigating factors
- [ ] Checked for signs of human writing
- [ ] Not relying on ineffective indicators
- [ ] Stated appropriate confidence level
- [ ] Acknowledged limitations
- [ ] Used appropriate language
- [ ] Not making certainty claims
