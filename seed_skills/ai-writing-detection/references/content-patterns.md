# Content Patterns in AI-Generated Text

Content-level indicators focus on WHAT AI writes, not just HOW it writes. These patterns reveal how LLMs conceptualize and present information.

## Undue Emphasis on Symbolism, Legacy, and Importance

**Why this happens**: LLMs are trained on text where famous topics are described with positive, important-sounding language. This causes statistical regression to the mean - specific facts fade into generic, exaggerated descriptions.

### Signal Words and Phrases

```
stands/serves as
is a testament/reminder
plays a vital/significant/crucial/pivotal role
underscores/highlights its importance/significance
impactful, important to social cohesion
reflects broader
symbolizing its ongoing/enduring/lasting impact
key turning point
promotes collaboration
indelible mark
deeply rooted
profound heritage
revolutionary
reinforces good habits
healthy relationship
steadfast dedication
```

### Pattern Description

AI writing often "puffs up" importance by adding statements about how arbitrary aspects represent broader topics. The subject becomes simultaneously less specific and more exaggerated.

### Examples

**Original fact**: "inventor of the first train-coupling device"
**AI transforms to**: "a revolutionary titan of industry"

**Example from Wikipedia draft**:
> "The Statistical Institute of Catalonia was officially established in 1989, **marking a pivotal moment in the evolution of regional statistics in Spain**. [...] The founding of Idescat represented a **significant shift** toward regional statistical independence..."

**Another example**:
> "This etymology **highlights the enduring legacy** of the community's resistance and the **transformative power of unity** in shaping its identity."

Even mundane topics like etymology or population data get this treatment.

## Biology and Ecosystem Puffery

When discussing plants, animals, or species, AI tends to:
- Over-emphasize connections to the "broader ecosystem"
- Belabor conservation status (even when unknown)
- Claim importance for "research and preservation efforts" (even when none exist)

### Example

> "It plays a role in the ecosystem and contributes to Hawaii's rich cultural heritage. [...] Preserving this endemic species is vital not only for ecological diversity but also for sustaining the cultural traditions connected to Hawaii's native flora."

### Red Flag Pattern

If text about a species includes:
1. Generic ecosystem importance claims
2. Conservation concerns without specific IUCN data
3. Cultural significance without cited sources

...it's likely AI-generated.

## Undue Emphasis on Notability and Media Coverage

### Pattern Description

AI acts as if the best way to prove notability is to hit readers over the head with claims of coverage, often:
- Listing sources without context of what they said
- Attributing superficial analyses to sources that don't say them
- Using Wikipedia guideline language like "independent coverage"

### Signal Phrases

```
independent coverage
local/regional/national/[country name] media outlets
music/business/tech outlets
written by a leading expert
active social media presence
maintains a strong digital presence
```

### Examples

> "She spoke about AI on CNN, and was featured in Vogue, Wired, Toronto Star, and other media."

> "Its significance is documented in archived school event programs and regional press coverage, including the *Mesabi Daily News*, which regularly reviewed performances held there."

### "Media Coverage" Sections

AI may create entire sections asserting notability with source-by-source breakdowns:

```
**Media coverage**
**IRNA** – Coverage of his inter-city marathon events.
**ISNA** – Report on an 80 km provincial peace run.
**IFRC** – Feature on his humanitarian campaigns.
```

This format - listing sources without summarizing their content - is highly characteristic of AI.

## Superficial Analyses with Participial Phrases

### What It Is

AI inserts superficial analysis by attaching present participle ("-ing") phrases at sentence ends, often with vague attributions.

### Signal Patterns

```
ensuring...
reflecting...
conducive/tantamount/contributing to...
cultivating... (figurative)
encompassing...
essentially/fundamentally is...
highlighting/underscoring its importance
```

### Key Tell

When the **subject of these verbs is an inanimate thing** (a fact, event, building), it's synthesis or unattributed opinion. Facts cannot "highlight" or "underscore" anything - that's a narrator's claim.

### Examples

> "Douera enjoys close proximity to the capital city, Algiers, **further enhancing its significance** as a dynamic hub of activity and culture."

> "These citations, spanning more than six decades and appearing in recognized academic publications, **illustrate Blois' lasting influence** in computational linguistics, grammar, and neology."

## Promotional and Advertisement-Like Language

### Neutral Tone Problems

AI has serious problems maintaining neutral tone, especially for "cultural heritage" topics.

### Signal Words

```
continues to captivate
groundbreaking (figurative)
stunning natural beauty
enduring/lasting legacy
nestled
in the heart of
boasts a [feature]
rich cultural heritage
vibrant
breathtaking
fascinating glimpse
diverse tapestry
```

### Examples

> "Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage..."

### Commercial/Business Puffery

For companies and products, AI sounds like a TV commercial transcript:

> "These projects align with KQ's goals of reducing its environmental footprint, improving operational efficiency, and fostering community development through job creation."

> "The SOLLEI's exterior design communicates a powerful emotional presence, staying true to Cadillac's signature bold proportions..."

## "Challenges and Future Prospects" Sections

### The Formula

AI often includes a "Challenges" section that follows this rigid pattern:

1. "Despite its [positive things], [subject] faces challenges..."
2. List of generic challenges
3. Positive/hopeful conclusion about future

### Signal Phrases

```
Despite its... faces several challenges...
Despite these challenges
Challenges and Legacy
Future Outlook
Future Prospects
ongoing initiatives
continued to thrive
```

### Examples

> "Despite its industrial and residential prosperity, Korattur faces challenges typical of urban areas, including[...] With its strategic location and ongoing initiatives, Korattur continues to thrive..."

> "Despite their promising applications, pyroelectric materials face several challenges that must be addressed for broader adoption. One key limitation is[...] Despite these challenges, the versatility of pyroelectric materials positions them as critical components..."

### The Tell

This is about the **rigid formula**, not simply mentioning challenges. The "despite challenges → hopeful future" arc is mechanical.

## Improper Leads for List Articles

### Pattern

When an article title isn't a proper noun (e.g., a list or concept), AI introduces it as if it were a standalone entity.

### Examples

> "'The Effects of Foreign language anxiety on Learning' **refers to** the feelings of tension..."

> "The 'List of songs about Mexico' **is** a curated compilation of musical works..."

Proper list leads integrate the title naturally, not as a defined entity.

## Vague See-Also Sections

AI fills see-also sections with broad, generic topics rather than specific related articles.

### Example

A see-also section on a startup article might link to "Financial technology" rather than specific companies or technologies.

May link to:
- Non-existent articles (red links)
- Overly broad topics
- Unlinked plain text

## Detection Checklist

When analyzing content, check for:

- [ ] Does it claim importance without specific evidence?
- [ ] Are there "-ing" phrases attached to inanimate subjects?
- [ ] Does it sound like promotional material?
- [ ] Is there a formulaic "challenges → future" section?
- [ ] Are media sources listed without summarizing their content?
- [ ] Are ecosystem/conservation claims made without citations?
- [ ] Does the lead treat a descriptive title as a proper noun?
