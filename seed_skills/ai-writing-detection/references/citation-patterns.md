# Citation Patterns in AI-Generated Text

Reference and citation indicators that suggest AI involvement. These patterns range from clear hallucination to subtle formatting anomalies.

## Broken External Links

### The Pattern

If a new article has multiple citations with external links, and several return 404 errors or don't exist, this is a strong AI signal.

### Key Factors

Links are more likely AI-hallucinated if:
- They return 404 errors
- They're not found in Internet Archive or Archive Today
- The domain exists but the specific page doesn't
- Multiple citations from the same source are broken

### Why This Happens

AI generates plausible-sounding URLs based on patterns in training data, but the specific pages don't exist.

### Example Pattern

A draft cites three New York Times articles, all with realistic-looking URLs:
- `nytimes.com/2023/05/15/technology/ai-research.html` (404)
- `nytimes.com/2023/08/22/business/startup-funding.html` (404)
- `nytimes.com/2024/01/10/science/quantum-computing.html` (404)

The domain is real, the URL structure is correct, but the articles don't exist.

### Detection

1. Check all external links in new articles
2. Note how many return errors
3. Search Internet Archive for any trace
4. Multiple non-existent URLs = strong AI signal

## Invalid DOIs and ISBNs

### DOI Verification

DOIs (Digital Object Identifiers) should resolve to actual papers. Unresolvable DOIs suggest hallucination.

### ISBN Checksums

ISBNs have built-in checksums. Invalid checksums mean the ISBN is incorrect or fabricated.

**ISBN-10 checksum**: Sum of (digit × position) should be divisible by 11
**ISBN-13 checksum**: Alternating 1× and 3× multipliers, sum divisible by 10

Citation templates display warnings for invalid ISBNs.

### Example of Hallucinated Academic Citations

ChatGPT generated this passage about Ohm's Law with citations:

> "Ohm's Law applies to many materials and components that are 'ohmic'... However, it does not hold for non-linear devices like diodes or transistors [2][3].
>
> References:
> 2. M. E. Van Valkenburg, 'The validity and limitations of Ohm's law in non-linear circuits,' Proceedings of the IEEE, vol. 62, no. 6, pp. 769–770, Jun. 1974. doi:10.1109/PROC.1974.9547
> 3. C. L. Fortescue, 'Ohm's Law in alternating current circuits,' Proceedings of the IEEE, vol. 55, no. 11, pp. 1934–1936, Nov. 1967. doi:10.1109/PROC.1967.6033"

**Problems**:
- Both DOIs lead to completely different papers
- C. L. Fortescue died 30+ years before the supposed 1967 publication
- Vol 55, Issue 11 doesn't contain any matching article

### Detection

1. Click DOI links - do they resolve to the claimed paper?
2. Check ISBN checksums
3. Verify author names against publication dates
4. Cross-reference journal issue contents

## Hallucinated References

### Complete Fabrication Signs

- Author names that don't exist in academic records
- Book titles that return no search results
- Journals with plausible names that don't exist
- Page numbers that are obviously wrong (e.g., "pp. 1-500")

### Plausible But Wrong

AI often generates references that:
- Use real journal names with fake articles
- Cite real authors with papers they didn't write
- Have correct format but fictional content

### Book Citations Without Page Numbers

AI cites books without page numbers, making verification impossible:

> "Dorf, R. C., & Svoboda, J. A. (2010). Introduction to Electric Circuits (8th ed.). ISBN 9780470521571."

A real book exists, but which pages support the claim? This pattern suggests AI generated a "plausible" citation without actually reading the source.

## Named References Declared But Unused

### The Pattern

References defined in a `<references>` section but never called in the article body produce cite errors:

```
<references>
<ref name="source1">https://example.com/article</ref>
<ref name="source2">https://example.com/other</ref>
</references>
```

**Result**:
> Cite error: A list-defined reference named "source1" is not used in the content

### Why This Happens

AI may generate a list of sources separately from body text, without properly linking them. Or the user asked AI to "add citations" and it added the list without integrating them.

### Detection

Look for the cite error warnings that appear when references are declared but unused.

## Incorrect Reference Formatting

### Markdown-Style Links in Citations

```
According to a [G1 article](https://g1.globo.com/example) and as noted by [RG/UOL](https://siterg.uol.com.br/example)...
```

### Source-by-Source Attribution in Body

AI over-emphasizes sources in body text:

> "As highlighted by [EBC Rádios](url), she has been recognized as one of Brazil's emerging independent artists."

Human Wikipedia editors typically provide inline citations or no attribution for uncontroversial facts.

### Wrong Citation Template Syntax

AI may produce malformed citation templates:

```
<ref>{{cite web
 |title=Article Title
 |url=URL  <!-- Literal "URL" as placeholder -->
 |website=Website Name
 |date=2025-XX-XX  <!-- Placeholder date -->
 |access-date=2025-XX-XX
}}</ref>
```

### Escaped Quote Marks

AI may incorrectly escape quote marks in reference names:

```
<ref name=\"source\">...</ref>
```

Instead of:
```
<ref name="source">...</ref>
```

## URL Placeholder Patterns

### Literal "URL" Placeholder

AI leaves "URL" as literal text:

```
|url=URL
|website=Example Website
```

### Placeholder Dates

Incomplete date fields:

```
|date=2025
|access-date=2025-XX-XX
```

### Detection Searches

```
insource:"2022-xx-xx" OR "2024-xx-xx" OR "2025-xx-xx"
```

## Footnote Marker Patterns

### ↩ Character

Some AI interfaces use the ↩ character for footnotes:

```
KLAS Research. (2024). Top Performing RCM Vendors 2024. https://klasresearch.com ↩ ↩2
```

### Numbered Brackets Without Links

AI may output `[1]`, `[2]` markers that don't actually link to references:

> "The results were significant [1] and confirmed previous findings [2]."

But [1] and [2] are plain text, not linked to any references.

## Non-Existent Templates and Categories

### Hallucinated Infoboxes

AI creates plausible-sounding but non-existent infobox templates:

```
{{Infobox ancient population
| name = Example Culture
...
}}
```

When the actual template is:
```
{{Infobox archaeological culture
...
}}
```

### Category Name Errors

AI hallucinates slightly wrong category names:

**AI outputs**: `[[Category:American hip hop musicians]]`
**Actual**: `[[Category:American hip-hop musicians]]`

The hyphen difference makes it a red link.

### Detection

- Check for red-linked templates in drafts
- Check for red-linked categories
- Early revisions may show deleted broken categories

## Over-Attribution Pattern

### The Pattern

AI painstakingly attributes every fact to named sources in body text, even for trivial information:

> "The restaurant has also been mentioned in ABC News coverage relating to incidents in the surrounding precinct, underscoring its role as a well-known late-night venue."

Human editors would typically just cite this with a footnote, not emphasize the source in prose.

### Why This Happens

AI models trained on Wikipedia content see citation-heavy text and over-generalize the pattern, attributing even minor facts explicitly.

## Citation Verification Checklist

When checking citations:

- [ ] Do external links resolve to actual pages?
- [ ] Are broken URLs archived anywhere?
- [ ] Do DOIs resolve to the claimed papers?
- [ ] Do ISBN checksums validate?
- [ ] Are there declared references that produce cite errors?
- [ ] Are there placeholder values (URL, XX-XX dates)?
- [ ] Are templates and categories real or red-linked?
- [ ] Is there over-attribution of minor facts?
- [ ] Are book citations missing page numbers?
- [ ] Are reference names properly formatted (no escaped quotes)?

## Confidence Levels

| Pattern | Confidence |
|---------|-----------|
| Multiple non-existent URLs | High |
| Invalid DOI/ISBN checksums | High |
| Unused declared references | High |
| Literal "URL" placeholder | Very High |
| 2025-XX-XX date format | Very High |
| Red-linked templates | Medium |
| Over-attribution in prose | Medium |
| Missing page numbers | Low (alone) |
