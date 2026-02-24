# Structural Patterns in AI-Generated Text

Comprehensive reference for sentence, paragraph, and document-level structural patterns that indicate AI authorship.

## Sentence-Level Patterns

### Uniformity (Low Burstiness)

**What it means**: AI produces sentences of similar length and complexity throughout.

**Human pattern**: Mix of short punchy sentences with long complex ones. Varying rhythm.

**AI pattern**: Consistent 12-18 word sentences. Uniform complexity. Predictable rhythm.

**How to measure**:
1. Calculate word count for each sentence
2. Compute standard deviation
3. Low SD = AI signal; High SD = human signal

**Example - AI (low burstiness)**:
```
The research methodology was carefully designed to ensure accurate results.
Data collection involved multiple sources to provide comprehensive coverage.
Analysis procedures followed established protocols from previous studies.
Results were validated through rigorous statistical testing methods.
```
(All sentences: 10-12 words, similar structure)

**Example - Human (high burstiness)**:
```
We tried everything. The methodology section took three rewrites before
anyone was happy with it - and even then, Dr. Chen had reservations about
the sampling approach. But what could we do? The deadline was Thursday.
```
(Sentences: 3, 22, 4, 5 words - varied)

### Tricolon Structures

**What it is**: Three-part parallel phrases, often with escalating significance.

**AI pattern**: Frequent use of tricolons, especially in lists.

```
"research, collaboration, and problem-solving"
"engaging, informative, and thought-provoking"
"planning, execution, and evaluation"
"clear, concise, and compelling"
```

**Why it's a signal**: AI defaults to three items for rhetorical balance. Humans vary between 2, 3, 4+ items naturally.

### Correlative Constructions

**What they are**: Paired conjunctions creating balanced structures.

**AI overuses**:
- "Not only...but also..."
- "Whether...or..."
- "Both...and..."
- "Either...or..."
- "Neither...nor..."

**Example**:
```
"Not only does this approach improve efficiency, but it also reduces costs."
```

Humans use these too, but AI uses them disproportionately.

### Negative Parallelisms

**What they are**: Constructions involving "not", "but", or "however" that appear balanced and thoughtful.

**Common patterns**:
- "Not only ... but ..."
- "It is not just about X, it's about Y"
- "It's not X; it's Y"
- "No X, no Y, just Z"

**Examples**:
```
"It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere."

"He hailed from the esteemed Duse family. However, Eugenio's life took a path that intertwined both personal ambition and familial complexities."
```

**Explicit negation of primary properties**:
```
"Not a career, not a body of work, not sustained relevance — just an algorithmic moment."
```

### Rule of Three (Tricolon Overuse)

**What it is**: AI overuses the rhetorical "rule of three" - lists of exactly three items.

**Forms**:
- "adjective, adjective, adjective"
- "short phrase, short phrase, and short phrase"

**Examples**:
```
"engaging, informative, and thought-provoking"
"research, collaboration, and problem-solving"
"keynote sessions, panel discussions, and networking opportunities"
```

**Why it's a signal**: AI defaults to three items for rhetorical balance. Humans naturally vary between 2, 3, 4+ items.

### Elegant Variation (Synonym Cycling)

**What it is**: AI has repetition-penalty code that discourages reusing words. This causes cycling through synonyms when referring to the same entity.

**Example - Character reference variation**:
```
Text introduces: "the protagonist"
Later refers to: "the key player"
Then: "the eponymous character"
Then: "our central figure"
```

All referring to the same person, but never repeating the same term.

**Example - Concept variation**:
```
"Soviet artistic constraints"
"Non-conformist artists"
"Their creativity"
"artistic aspirations"
"artistic norms"
"artistic expression"
```

**Detection**: Note when entities are introduced, then track how they're referenced. Excessive synonym variation = AI signal.

**Caveat**: If a user adds multiple pieces of AI-generated content in separate edits, this pattern may not appear (each generation starts fresh).

### False Ranges

**What they are**: "From X to Y" constructions where X and Y don't form a coherent scale or range.

**Legitimate ranges**:
- Quantitative: "from 1990 to 2000", "from 15 to 20 ounces"
- Qualitative: "from mild to severe", "from head to toe"
- Merisms: "from soup to nuts" (time-based), "from cradle to grave"

**False ranges (AI pattern)**:
- Endpoints don't share a scale
- No meaningful middle ground exists
- Figurative usage that is actually meaningless

**Example**:
```
"Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars that forge the elements of life, to the enigmatic dance of dark matter and dark energy..."
```

The "from...to" construction sounds impressive but the endpoints aren't actually opposite ends of a scale.

**Detection**: Ask "What would be the middle of this range?" If answering requires switching scales, it's a false range.

### Em Dash Overuse

**Pattern**: AI uses em dashes more frequently than typical human writing, and uses them in places where humans would more likely use commas, parentheses, colons, or (misused) hyphens.

**Why AI does this**: LLMs use em dashes in a formulaic, pat way, often mimicking "punched up" sales-like writing by over-emphasizing clauses or parallelisms. The dashes add a kind of dramatic flair that AI has learned from marketing copy and persuasive writing.

**AI examples**:
```
"The solution—which many experts have praised—offers several advantages."
"This approach—unlike traditional methods—provides better results."
```

**Real-world examples** (from detected AI text):
```
"This isn't 'imagining' what policy should be — it's recognizing how community consensus has shaped its application."
"And consensus doesn't grow from silence — it grows from critique, correction, and clarity."
"If we disagree on that, then yes — we're speaking different languages."
```

Note the pattern: em dashes used to create dramatic pauses, set off emphatic parallelisms ("it's not X — it's Y"), and add rhetorical punch. This "punched up" quality is the tell.

**Human tendency**: Em dashes used sparingly; humans typically use commas or parentheses for parenthetical asides, or restructure sentences to avoid mid-sentence insertions entirely.

**Important context**: This signal is most useful when taken in combination with other indicators, not by itself. Em dashes alone don't prove AI authorship—but em dashes PLUS tricolons PLUS uniform sentence length PLUS vocabulary patterns creates a strong signal.

**Why punctuation swapping doesn't help**: Simply replacing em dashes with commas or parentheses doesn't fix the underlying pattern:

```
Same "punched up" parallelism, different punctuation:
"This isn't X — it's Y"         (em dashes)
"This isn't X, it's Y"          (comma)
"This isn't X; it's Y"          (semicolon)
```

All three have the same rhetorical structure. The tell isn't the punctuation mark—it's the formulaic emphasis pattern.

**To write naturally**:
- Vary your sentence structures (don't always use parallelisms)
- Use em dashes sparingly and only when truly needed for emphasis
- Restructure sentences to eliminate mid-sentence insertions
- Don't mimic "punched up" sales writing rhythm

**Detection**: Count em dashes per 100 words as a heuristic, but weight more heavily when combined with other structural patterns (tricolons, parallelisms, uniform sentence lengths).

### Semicolon Patterns

**AI pattern**: Semicolons connecting simple statements that could be separate sentences.

```
"The results were promising; the team decided to continue."
"Users appreciate simplicity; complexity creates confusion."
```

**Why it's a signal**: AI sees semicolons as sophisticated; humans use them more sparingly and for more complex clause connections.

## Paragraph-Level Patterns

### Structural Uniformity

**AI pattern**: All paragraphs approximately the same length.

**Human pattern**: Varied paragraph lengths based on content needs.

**How to measure**:
1. Count sentences per paragraph
2. Calculate standard deviation
3. Low SD across paragraphs = AI signal

### Topic Sentence Templates

**AI pattern**: Each paragraph begins with an explicit thesis statement.

```
Paragraph 1: "The first important consideration is..."
Paragraph 2: "Another key factor involves..."
Paragraph 3: "A third significant aspect relates to..."
```

**Human pattern**: Topic sentences vary in explicitness. Some paragraphs start with context, examples, or transitions.

### New Idea = New Paragraph

**AI pattern**: Strict separation of ideas into discrete paragraphs.

**Human pattern**: Ideas flow across paragraph breaks; paragraphs sometimes contain multiple related points.

### List-Like Organization

**AI pattern**: Content naturally falls into enumerable points, even in prose.

```
"There are several key benefits. First, it improves efficiency.
Second, it reduces costs. Third, it enhances user experience."
```

**Human pattern**: More organic argumentation that doesn't enumerate explicitly.

## Document-Level Patterns

### Introduction Patterns

**AI templates**:
- "Have you ever wondered..."
- "In today's fast-paced world..."
- "When it comes to [topic], many people..."
- "[Topic] has become increasingly important in..."

**Human variation**: Personal anecdotes, provocative claims, in medias res openings.

### Conclusion Patterns

**AI templates**:
- "In conclusion..."
- "To summarize..."
- "In summary..."
- "All in all..."
- [Restatement of thesis in slightly different words]

**Human variation**: Calls to action, future implications, personal reflections, open questions.

### Problem-Solution Structure

**AI pattern**: Explicit problem statement → solution presentation → benefits enumeration

**Why it's a signal**: AI defaults to this structure; humans use it but also use narrative, comparison, chronological, and other structures.

### Section Organization

**AI pattern**: Over-organized with explicit headings and subheadings even when unnecessary.

**Human pattern**: Headings used when genuinely helpful; prose flows without constant sectioning.

## Discourse Patterns

### Rhetorical Structure Theory (RST) Findings

**AI patterns**:
- Elaboration and Temporal motifs increase as generation length grows
- More explicit discourse markers
- Linear, predictable discourse flow

**Human patterns**:
- Joint relation motifs (evenly branching structures)
- Implicit discourse relations
- Non-linear argumentation

### Syntactic Template Repetition

**Research finding**: 76% of AI syntactic templates also appear in training data vs 35% for human text.

**AI pattern**: Repeated dual-adjective patterns
- "unique and intense"
- "magical and thought-provoking"
- "simple yet effective"
- "complex but manageable"

### Metadiscourse Differences

**AI pattern**: Lower frequency of interactional metadiscourse
- Fewer hedges in argumentation
- Fewer boosters (emphasis markers)
- Fewer attitude markers

**Human pattern**: Higher rhetorical engagement with reader

## Coherence Patterns

### Local vs Global Coherence

**AI pattern**: Sentences make sense individually; may not build a coherent argument.

**How to detect**:
- Read each paragraph in isolation - makes sense
- Read entire document - lacks clear throughline or builds circular argument

### Repetitive Concepts

**AI pattern**: Same idea restated with different words across paragraphs.

**Example**:
```
Paragraph 1: "Communication is essential for team success."
Paragraph 3: "Effective teams rely on strong communication."
Paragraph 5: "Success depends on how well team members communicate."
```

### Non-Sequitur Transitions

**AI pattern**: Smooth-sounding transitions that don't actually connect ideas logically.

```
"Furthermore, the study examined user preferences."
"Moreover, implementation costs were considered."
```

The transitions sound connected but ideas may be unrelated.

### Entity Reference Distance

**Research finding**:
- Human text: Refers back to introduced entities across long distances
- AI text: Clusters same-entity mentions closer together

**How to check**: Note when entities are introduced, see how far apart subsequent references appear.

## Formatting Patterns

### Bullet Points in Essays

**AI pattern**: Bullet points appear in contexts where prose would be more natural.

**Human pattern**: Bullet points reserved for genuinely list-like content.

### Excessive Parallelism

**AI pattern**: Every element in a list follows identical grammatical structure.

```
- Improving efficiency
- Reducing costs
- Enhancing quality
- Increasing satisfaction
```

**Human pattern**: Some parallel structure but with natural variation.

### Over-Use of Bold/Headers

**AI pattern**: Frequent bolding of key terms; many section headers.

**Human pattern**: Formatting used purposefully; prose allowed to flow.

## Detection Implementation

### Sentence Analysis
```
For each text:
1. Calculate sentence length variance
2. Count tricolon structures
3. Count correlative constructions
4. Count em dashes per 100 words
5. Assess uniformity score
```

### Paragraph Analysis
```
For each text:
1. Calculate paragraph length variance
2. Check for template topic sentences
3. Look for enumerated structure in prose
4. Assess introduction/conclusion templates
```

### Document Analysis
```
For each text:
1. Map discourse structure
2. Check for circular reasoning
3. Identify repeated concepts
4. Assess global coherence
```

## Caveats

- Technical and academic writing is naturally more structured
- Some humans write in organized, parallel patterns
- Format expectations vary by genre (reports vs essays vs blog posts)
- Always combine structural analysis with vocabulary and statistical signals
