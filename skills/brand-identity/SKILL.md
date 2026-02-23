---
name: brand-identity
description: >
  Create a complete brand visual identity system from a project description. Use this skill when a user
  asks to create a brand kit, logo system, business card design, social media cover, color palette,
  typography specification, brand guidelines document, or any combination of brand identity deliverables.
  Covers the full spectrum of brand collateral: primary/wordmark/icon logos with monochrome and reversed
  variants, color systems with primary/secondary/neutral palettes, typographic hierarchies with heading/body/accent
  scales, business card layouts, social media assets, and compiled brand specification documents.
---

# Brand Identity System

A structured reference for producing a cohesive brand visual identity package. Every section provides concrete specifications — pixel dimensions, color ratios, spacing rules — so that generated code (Pillow, reportlab) outputs professional-grade deliverables on the first attempt.

---

## BRAND KIT DELIVERABLE CHECKLIST

A complete brand kit contains these artifacts. Generate them in order; each builds on the decisions of the previous.

| # | Deliverable | Format | Key Spec |
|---|------------|--------|----------|
| 1 | Brand Philosophy | `.md` | 3-5 paragraphs, 150-300 words |
| 2 | Design Philosophy | `.md` | 4-6 paragraphs, aesthetic movement |
| 3 | Color Palette | defined in spec | Primary + Secondary + Neutral, HEX/RGB |
| 4 | Typography Scale | defined in spec | Heading / Body / Accent, 3 font families max |
| 5 | Logo — Primary | `.png` | 1024×1024, transparent background |
| 6 | Logo — Dark variant | `.png` | For light backgrounds |
| 7 | Logo — Light variant | `.png` | For dark backgrounds |
| 8 | Business Card | `.pdf` | 1050×600pt (3.5"×2" @300dpi) |
| 9 | Social Media Cover | `.png` | 1500×500px |
| 10 | Brand Specification | `.md` | Compiled reference document |

---

## COLOR SYSTEM

### Palette Structure

Every brand uses a three-tier palette:

| Tier | Role | Usage Ratio | Typical Application |
|------|------|-------------|---------------------|
| **Primary** | Brand signature | ~60% | Logo, headings, CTAs |
| **Secondary** | Supporting accent | ~30% | Illustrations, highlights, hover states |
| **Neutral** | Background & text | ~10% accent / rest bg | Body text, borders, backgrounds |

### Specification Format

Define each color with all three notations:

```
Primary:    #2D5BFF  →  rgb(45, 91, 255)
Secondary:  #FF6B35  →  rgb(255, 107, 53)
Neutral-900: #1A1A2E →  rgb(26, 26, 46)    ← text
Neutral-100: #F5F5F7 →  rgb(245, 245, 247)  ← background
Neutral-50:  #FFFFFF →  rgb(255, 255, 255)  ← white
```

### Contrast Rules

- Text on background must meet WCAG AA: contrast ratio ≥ 4.5:1 for body, ≥ 3:1 for large text (≥18pt)
- Logo must remain legible at minimum size on both light and dark backgrounds
- Never place primary color text on secondary color background without testing contrast

---

## TYPOGRAPHY HIERARCHY

### Font Selection

Choose a maximum of 3 font families from the `canvas-fonts/` directory:

| Role | Characteristics | Typical Families |
|------|----------------|-----------------|
| **Heading** | High impact, distinctive | BigShoulders, Outfit, YoungSerif, Gloock |
| **Body** | Highly readable at small sizes | InstrumentSans, WorkSans, CrimsonPro, Lora |
| **Accent** | Decorative or monospaced, for labels/captions | DMMono, GeistMono, JetBrainsMono, Italiana |

### Size Scale (pt)

| Level | Size | Weight | Line Height | Use |
|-------|------|--------|-------------|-----|
| H1 | 48-64pt | Bold | 1.1× | Hero / cover title |
| H2 | 32-40pt | Bold | 1.2× | Section headings |
| H3 | 24-28pt | Medium/Bold | 1.25× | Sub-headings |
| H4 | 18-22pt | Medium | 1.3× | Card titles |
| Body | 14-16pt | Regular | 1.5× | Paragraphs |
| Caption | 10-12pt | Regular/Light | 1.4× | Labels, footnotes |

### Font Loading (Pillow)

```python
from PIL import ImageFont

FONT_DIR = "/app/skills/canvas-design/canvas-fonts"
heading_font = ImageFont.truetype(f"{FONT_DIR}/Outfit-Bold.ttf", 48)
body_font = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Regular.ttf", 16)
accent_font = ImageFont.truetype(f"{FONT_DIR}/DMMono-Regular.ttf", 12)
```

---

## LOGO DESIGN SPECIFICATIONS

### Geometric Construction

- Build from a maximum of 3-4 primitive shapes (circles, rectangles, triangles, custom paths)
- Use proportional relationships: golden ratio (1:1.618) or simple ratios (1:1, 1:2, 2:3)
- Maintain optical balance — geometric center ≠ visual center; adjust by eye
- Icon should be recognizable at 64×64px (favicon test)

### Logo Variants

| Variant | Content | Background | Use Case |
|---------|---------|------------|----------|
| **Primary** | Icon + Wordmark | Transparent | Default usage |
| **Dark** | Dark-colored mark | Transparent | On light backgrounds |
| **Light** | Light/white mark | Transparent | On dark backgrounds |
| **Icon-only** | Icon without text | Transparent | Favicon, app icon, small spaces |

### Export Specifications

| Property | Value |
|----------|-------|
| Canvas size | 1024×1024px minimum |
| Background | Transparent (RGBA) |
| Format | PNG-24 with alpha |
| Color mode | sRGB |
| Padding | 10-15% of canvas on each side (icon centered) |

### Wordmark Rules

- Letter-spacing: +2% to +8% of font size for brand names (track out for elegance)
- Weight: Medium to Bold (never Thin for wordmarks — must be legible at small size)
- Alignment with icon: baseline-aligned or center-aligned, maintain consistent gap

### Style Constraints

- **No gradients** in the primary logo — solid colors only for maximum versatility
- **No photorealistic elements** — geometric/abstract only
- **No more than 3 colors** in the logo (primary + secondary + neutral or white)
- **Minimum clear space**: 0.5× the logo height on all sides, free of other elements

---

## BUSINESS CARD SPECIFICATIONS

### Dimensions

| Property | Value |
|----------|-------|
| Standard size | 3.5" × 2" (89mm × 51mm) |
| Pixel size @300dpi | 1050 × 600px |
| reportlab points | 1050pt × 600pt (1pt = 1px at 72dpi, use 252pt × 144pt for true size, or scale up) |
| Bleed area | 3mm (9px @300dpi) beyond trim on all sides |
| Safety margin | 6mm (18px @300dpi) inside trim — all text/logos within this |

### Information Hierarchy

Arrange content in this priority order:

1. **Logo** — occupies 20-30% of card width, positioned top-left or centered-top
2. **Name** — largest text element on card, 14-18pt
3. **Title/Role** — 2-4 words maximum, 10-12pt
4. **Contact details** — ordered: email → phone → website → address, 8-10pt
5. **Tagline** (optional) — bottom edge or back, 8-9pt italic

### Layout Rules

- Use one side only (single-sided design) unless explicitly requested otherwise
- Maintain clear spatial zones: identity zone (top) + contact zone (bottom)
- Horizontal rule or whitespace to separate zones
- All contact info left-aligned for scan-ability
- Logo and name can be on opposite sides (left/right) for visual balance

### reportlab Output

```python
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm

# Business card size
CARD_WIDTH = 89 * mm   # 3.5 inches
CARD_HEIGHT = 51 * mm  # 2 inches
BLEED = 3 * mm
SAFETY = 6 * mm
```

---

## SOCIAL MEDIA COVER SPECIFICATIONS

### Dimensions

| Platform | Size | Safe Zone |
|----------|------|-----------|
| Universal cover | 1500×500px | Center 1080×360px |
| LinkedIn banner | 1584×396px | Center 1080×360px |
| Twitter/X header | 1500×500px | Center 1080×360px |

Use **1500×500px** as the universal size — works across platforms with minimal cropping.

### Safe Zone

The outer 15% on each side may be cropped or obscured by profile pictures and UI elements. All critical content (brand name, tagline, key visuals) must fit within the center safe zone:

```
┌──────────────────────────────────┐
│ ░░░░░░ CROP ZONE ░░░░░░░░░░░░░░ │
│ ░░ ┌────────────────────────┐ ░░ │
│ ░░ │    SAFE ZONE           │ ░░ │
│ ░░ │  1080 × 360px          │ ░░ │
│ ░░ └────────────────────────┘ ░░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
└──────────────────────────────────┘
```

### Content Guidelines

- **Brand name**: prominent, centered or left-aligned within safe zone
- **Tagline**: one line, positioned below or beside brand name
- **Visual elements**: geometric patterns, color blocks, or abstract shapes from the design philosophy — extend to full bleed
- **No small text**: minimum 24pt for any text on cover (reads on mobile)
- Background should use brand colors; avoid busy photographs that compete with text

---

## CROSS-DELIVERABLE CONSISTENCY RULES

These rules ensure visual coherence across all brand artifacts:

1. **Color values are immutable** — define once in Phase 4, copy-paste exact HEX values everywhere. Never approximate.

2. **Font families are shared** — the same heading/body/accent fonts appear on logo wordmark, business card, social cover, and spec document.

3. **Logo placement scaling**:
   - Business card: logo width = 20-30% of card width
   - Social cover: logo height = 40-60% of safe zone height
   - Spec document: logo displayed at 200px wide in header

4. **Spacing system** — derive all spacing from a base unit (e.g., 8px grid):
   - `xs`: 4px, `sm`: 8px, `md`: 16px, `lg`: 24px, `xl`: 32px, `xxl`: 48px

5. **Visual weight balance** — if the logo uses thick geometric shapes, business card and cover should echo that weight (bold fonts, solid color blocks). If the logo is delicate/thin, other deliverables match (light fonts, fine lines, ample whitespace).

---

## BRAND SPECIFICATION DOCUMENT FORMAT

The final `.md` document compiles all brand decisions into a referenceable guide:

```markdown
# [Brand Name] — Brand Specification

## Brand Philosophy
[3-5 paragraphs from Phase 2]

## Design Philosophy
[Movement name and description from Phase 3]

## Color Palette
| Role | Name | HEX | RGB | Usage |
|------|------|-----|-----|-------|
| Primary | [name] | #XXXXXX | rgb(r,g,b) | Logo, headings |
| Secondary | [name] | #XXXXXX | rgb(r,g,b) | Accents |
| Neutral Dark | [name] | #XXXXXX | rgb(r,g,b) | Text |
| Neutral Light | [name] | #XXXXXX | rgb(r,g,b) | Background |

## Typography
| Role | Family | Weight | Sizes |
|------|--------|--------|-------|
| Heading | [font] | Bold | H1:48pt H2:32pt H3:24pt |
| Body | [font] | Regular | 14-16pt |
| Accent | [font] | Regular | 10-12pt |

## Logo Usage
- Minimum size: 64px width
- Clear space: 0.5× logo height on all sides
- Approved variants: Primary, Dark, Light, Icon-only
- Never stretch, rotate, or recolor the logo

## Deliverable Files
| File | Format | Dimensions |
|------|--------|-----------|
| logo-dark.png | PNG | 1024×1024 |
| logo-light.png | PNG | 1024×1024 |
| business-card.pdf | PDF | 3.5"×2" |
| social-cover.png | PNG | 1500×500 |
```
