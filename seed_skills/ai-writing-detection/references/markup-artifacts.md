# Markup Artifacts in AI-Generated Text

Technical markup patterns and artifacts that definitively indicate AI involvement. These are often the most objective and least contestable indicators.

## Markdown in Non-Markdown Contexts

### Why This Happens

Most AI chatbots are trained to output Markdown, not wikitext or plain text. Their system instructions include directives like:

> "All output uses GitHub-flavored Markdown."

When users copy AI output to contexts expecting different markup (Wikipedia, forums, documents), Markdown syntax appears as plain text.

### Common Markdown Contamination

| Markdown Syntax | Intended Result | What Appears |
|-----------------|-----------------|--------------|
| `## Heading` | Section heading | ## Heading (literal) |
| `**bold**` | Bold text | **bold** (literal asterisks) |
| `*italic*` | Italic text | *italic* (literal asterisks) |
| `[text](url)` | Hyperlink | [text](url) (literal) |
| `` `code` `` | Code formatting | \`code\` (literal backticks) |
| `---` | Horizontal rule | --- (literal dashes) |

### Fenced Code Blocks

AI may wrap its output in Markdown code fences:

```
```wikitext
{{Infobox person
| name = Example
}}
```
```

If you see triple backticks (```) in text, it's strong AI evidence.

### Mixed Markup

The most telling pattern is **both** Markdown and attempted wikitext in the same text:

```
## History

'''Bold text''' and [[Internal link]]

**Also bold** with [external link](http://example.com)
```

### Detection Searches

For Wikipedia contexts:
```
insource:/\*\*[^*]+\*\*/    (Markdown bold)
insource:/##+ /              (Markdown headers)
```

## ChatGPT-Specific Artifacts

### turn0search / turn0image

ChatGPT may include citation markers that render as broken text:

**Patterns**:
- `citeturn0search0`
- `citeturn0search1`, `citeturn0search2`, etc.
- `turn0image0`, `turn0image1`, etc.
- `citeturn0news0`
- `citeturn1file0`

**Example**:
> "The school is also a center for the US College Board examinations, SAT I & SAT II. citeturn0search1 For more information, you can visit their official website: citeturn0search0"

**Detection regex**:
```
insource:/turn0(search|image|news|file)[0-9]+/
```

### contentReference / oaicite

Due to bugs, ChatGPT may output broken reference markup:

**Patterns**:
- `:contentReference[oaicite:0]{index=0}`
- `:contentReference[oaicite:16]{index=16}`
- `[oai_citation:0‡website.com](url)`
- `[oai_citation:1‡en.wikipedia.org](url)`

**Example**:
> ":contentReference[oaicite:16]{index=16}
>
> 1. **Ethnicity clarification**
>
> - :contentReference[oaicite:17]{index=17}"

**Detection searches**:
```
insource:"contentReference"
insource:"oaicite"
insource:"oai_citation"
```

### Attribution JSON

ChatGPT may append JSON-formatted attribution data:

**Pattern**:
```
({"attribution":{"attributableIndex":"X-Y"}})
```

**Example**:
> "^[Evdokimova was born on 6 October 1939 in Osnova...]({"attribution":{"attributableIndex":"1009-1"}})"

### utm_source Tracking

ChatGPT adds tracking parameters to URLs it cites:

**Patterns**:
- `utm_source=chatgpt.com` (pre-August 2025)
- `utm_source=openai` (current)

**Example**:
> "[https://www.theguardian.com/sport/article?utm_source=chatgpt.com]"

**Detection**:
```
insource:"utm_source=chatgpt.com"
insource:"utm_source=openai"
```

**Important**: This definitively proves ChatGPT involvement, but not necessarily that ChatGPT wrote the text. Users may use AI tools to find citations for human-written content.

## Other AI Model Artifacts

### Grok (X/Twitter)

Grok may include XML-styled tags:

**Pattern**:
```
<grok_card data-id="e8ff4f" data-type="citation_card">
```

### Perplexity

Perplexity may include file/source tags:

**Patterns**:
- `[attached_file:1]`
- `[web:1]`

**Example**:
> "Philip Morris's reputation management and media relations brought together business and news interests in ways that later became controversial.[attached_file:1]"

### Footnote Markers

Some AI interfaces use special footnote characters:

**Pattern**: `↩` or `↩2` at end of citations

**Example**:
> "KLAS Research. (2024). Top Performing RCM Vendors 2024. https://klasresearch.com ↩ ↩2"

## Broken Wikitext from AI

### Why It Happens

AI chatbots are not proficient in wikitext. When told to generate Wikipedia content, they often produce faulty syntax.

### AFC Submission Bugs

New editors asking AI to submit drafts may see garbled AFC templates:

**Example of date parsing bug**:
```
[[Category:AfC submissions by date/<0030Fri, 13 Jun 2025 08:18:00 +0000202568...
```

### Pre-Declined Drafts

AI may output AFC templates with the "declined" parameter set:

```
{{AfC submission|d}}
```

This creates a pre-declined draft with no reviewer reasoning.

### Non-Existent Templates

AI hallucinates plausible-sounding templates:

**Example**:
```
{{Infobox ancient population
| name = Gangetic Hunter-Gatherer
...
}}
```

Instead of actual template:
```
{{Infobox archaeological culture
...
}}
```

### Incorrect Template Parameters

AI may use parameters that don't exist in the actual template:
```
| leader_name = <!-- Add if available with citation -->
```

### Non-Existent Categories

AI may hallucinate category names:
```
[[Category:American hip hop musicians]]
```

Instead of actual:
```
[[Category:American hip-hop musicians]]
```

(Note the hyphen difference)

## Placeholder Text Artifacts

### Template Placeholders

AI may output fill-in-the-blank templates the user forgot to complete:

**Example**:
> "Dear Wikipedia Editors,
>
> I hope this message finds you well. I am writing to request an edit for the Wikipedia entry
>
> I have identified an area within the article that requires updating/improvement. [Describe the specific section or content that needs editing...]"

### Placeholder Dates

AI may insert placeholder dates in citation fields:

**Patterns**:
- `access-date=2025-XX-XX`
- `date=2025-xx-xx`

### URL Placeholders

AI may use literal "URL" as a placeholder:

```
|url=URL
|website=Canadian Screen Music Awards
```

## Collaborative Communication Artifacts

### "I Hope This Helps"

Text meant as correspondence, not article content:

**Signal phrases**:
```
I hope this helps
Of course!
Certainly!
Would you like...
Is there anything else
Let me know
Here is a...
```

### Wikipedia-Specific Instructions

AI may explicitly mention Wikipedia guidelines in output:

> "If you plan to add this information to the Wikipedia page, ensure that the content is presented in a neutral tone, supported by reliable sources, and adheres to Wikipedia's guidelines on verifiability and neutrality."

### Submission Statements

AI may generate "reviewer notes" supposedly for AFC:

> "Reviewer note (for AfC): This draft is a neutral and well-sourced biography... It meets WP:RS and WP:BLP standards and demonstrates clear notability per WP:NBIO through..."

## Knowledge Cutoff Disclaimers

### Pattern

AI outputs stating information may be incomplete or outdated:

**Signal phrases**:
```
as of my last knowledge update
as of my last training update
While specific details are limited/scarce...
not widely available/documented/disclosed
in the provided/available sources/search results
based on available information
```

**Example**:
> "As of my last knowledge update in January 2022, I don't have specific information about the current status or developments related to the 'Chester Mental Health Center'..."

### Speculation About Gaps

When AI fails to find sources, it speculates:

> "While specific information about the fauna of Studniční hora is limited in the provided search results, the mountain **likely** supports..."

## Detection Priority

| Artifact Type | Confidence | Notes |
|--------------|------------|-------|
| turn0search/oaicite | Definitive | ChatGPT-specific bug |
| utm_source=chatgpt | Definitive | Proves ChatGPT use |
| Markdown + wikitext mix | Very High | Clear context mismatch |
| Submission statements | Very High | Meta-commentary |
| Knowledge cutoffs | Very High | Self-identification |
| Placeholder text | High | Forgot to fill in |
| Curly quotes consistent | Medium | ChatGPT/DeepSeek default |
| Non-existent templates | Medium | Could be human error |

## Detection Checklist

For technical artifacts:

- [ ] Any `turn0search`, `turn0image`, or similar markers?
- [ ] Any `contentReference`, `oaicite`, or `oai_citation`?
- [ ] Any `utm_source=chatgpt.com` or `utm_source=openai` in URLs?
- [ ] Any `<grok_card>` or `[attached_file:]` tags?
- [ ] Markdown syntax in non-Markdown context?
- [ ] Knowledge cutoff disclaimers?
- [ ] Submission statements or reviewer instructions?
- [ ] Placeholder text or template blanks?
- [ ] Non-existent templates or categories?
- [ ] Collaborative phrases like "I hope this helps"?
