---
name: markdown-to-storyboard
description: >
  Convert markdown content into a structured storyboard CSV for slide decks, video scripts,
  or any sequential visual media. Use when the user wants to plan a presentation, break down
  an article into slides, create a shot list, or generate a scene-by-scene outline from text.
  Triggers: "plan slides", "create storyboard", "break this into slides", "plan presentation",
  "outline this as a deck", "article to slides", "text to storyboard".
---

# Markdown to Storyboard

Convert any markdown text into a structured storyboard CSV — the universal handoff format
for downstream tools (slide builders, video editors, image generators).

## Workflow

### 1. Analyze the Source Markdown

Read the markdown and identify:
- Title and subtitle
- Section headings (H2/H3) → natural slide boundaries
- Key arguments / data points / quotes per section
- Narrative arc: setup → development → climax → conclusion

### 2. Ask User Preferences

Prompt for (defaults in parentheses):
- **Slide count** (auto: 8–15 based on content length, ~1 slide per 150–300 words)
- **Audience** (general)
- **Tone** (professional)
- **Language** (same as source)

If user declines to specify, use defaults and proceed.

### 3. Assign Slide Types and Layouts

Available `slide_type` values:

| Type | Purpose | Typical layout |
|------|---------|---------------|
| `cover` | Opening slide | `full_bg` |
| `toc` | Table of contents (optional, 12+ slides) | `center_text` |
| `section` | Chapter divider | `center_text` |
| `content` | Core information | `left_img_right_text` or `top_img_bottom_text` |
| `quote` | Key quote or statistic | `full_bg` |
| `data` | Chart / number-driven | `two_column` |
| `summary` | Closing recap | `center_text` or `left_img_right_text` |
| `end` | Thank-you / Q&A / CTA | `full_bg` |

Available `layout` values:
`full_bg`, `left_img_right_text`, `top_img_bottom_text`, `center_text`, `two_column`

### 4. Write the Image Prompt for Each Slide

For each slide, write an `image_prompt` (English, regardless of content language) that:
- Describes a **concrete scene**, not an abstract concept
- Includes a **style keyword** consistent across all slides (e.g. "flat vector illustration, soft pastel palette")
- Specifies composition hints matching the layout (e.g. "wide shot, negative space on the right" for `left_img_right_text`)
- Cover and end slides get more dramatic / visually impactful prompts

### 5. Draft Speaker Notes

`speaker_notes` column: 1–3 sentences of what the presenter would say. Leave empty if not requested.

### 6. Output the CSV

Write the storyboard to `storyboard.csv` using `execute_code`:

```python
import csv

rows = [
    # [slide_no, slide_type, title, bullet_points, image_prompt, speaker_notes, layout]
]

header = ["slide_no", "slide_type", "title", "bullet_points", "image_prompt", "speaker_notes", "layout"]

with open("storyboard.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)
```

Column spec:

| Column | Type | Description |
|--------|------|-------------|
| `slide_no` | int | 1-indexed |
| `slide_type` | str | One of the types above |
| `title` | str | Slide headline, ≤ 10 words |
| `bullet_points` | str | Newline-separated (`\n`). Each ≤ 20 chars. Max 5 items |
| `image_prompt` | str | English prompt for image generation |
| `speaker_notes` | str | Optional presenter notes |
| `layout` | str | One of the layouts above |

### 7. Present for Review

Display the storyboard as a markdown table for the user to review.
Wait for confirmation before the next pipeline step.
If changes requested, update `storyboard.csv` and re-display.

## Pacing Guidelines

- **Opening** (slides 1–2): Hook — cover + bold opening statement or question
- **Body** (slides 3 to N-2): One idea per slide. Alternate `content` and `quote`/`data` to vary rhythm
- **Closing** (slides N-1 to N): Summary of key takeaways + end slide
- Avoid consecutive slides of the same type. Insert a `section` divider between major parts.

## Text Density Rules

- Title: imperative or question form, ≤ 10 words
- Bullets: ≤ 5 per slide, each ≤ 20 characters (CJK) / ≤ 12 words (Latin)
- Prefer fragments over full sentences
- Numbers stand alone: "3x faster" not "It is three times faster"
