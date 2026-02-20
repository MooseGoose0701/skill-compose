---
name: storyboard-to-slides
description: >
  Assemble a PPTX slide deck from a storyboard CSV and images using python-pptx.
  Supports multiple slide layouts (full background, left-image-right-text, two-column, etc.),
  custom themes, fonts, and cover design. Use when the user wants to build a PowerPoint
  presentation from a structured plan, compose slides from images and text, or create a
  polished deck from a storyboard CSV. Triggers: "build slides", "create pptx", "assemble
  presentation", "make PowerPoint", "storyboard to slides", "generate deck".
---

# Storyboard to Slides

Assemble a polished PPTX from a storyboard CSV + image files using `python-pptx`.

## Dependencies

```python
# pip install python-pptx Pillow
```

## Input Format

Expects `storyboard.csv` with columns:
`slide_no, slide_type, title, bullet_points, image_prompt, speaker_notes, layout`

And image files named `slide_{no}.png` for each row.

## Workflow

### 1. Read the Storyboard

```python
import csv

with open("storyboard.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    slides = list(reader)
```

### 2. Initialize the Presentation

```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor

prs = Presentation()
prs.slide_width = Inches(13.333)   # 16:9
prs.slide_height = Inches(7.5)
```

For 4:3 slides: `Inches(10)` x `Inches(7.5)`.

### 3. Define Theme Constants

```python
# Customize per project
THEME = {
    "bg_color": RGBColor(0x1A, 0x1A, 0x2E),     # dark navy
    "title_color": RGBColor(0xFF, 0xFF, 0xFF),
    "text_color": RGBColor(0xE0, 0xE0, 0xE0),
    "accent_color": RGBColor(0x64, 0xB5, 0xF6),
    "title_font": "Arial",
    "body_font": "Arial",
    "title_size": Pt(36),
    "body_size": Pt(18),
}
```

Choose colors that contrast well with the generated images. For light images use dark text overlay with semi-transparent background; for dark images use white text.

### 4. Layout Implementations

#### `full_bg` — Full-screen background image + overlay text

```python
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

def add_full_bg_slide(prs, img_path, title, subtitle="", theme=THEME):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # Background image
    slide.shapes.add_picture(img_path, 0, 0, prs.slide_width, prs.slide_height)
    # Semi-transparent overlay
    overlay = slide.shapes.add_shape(
        1, 0, 0, prs.slide_width, prs.slide_height  # MSO_SHAPE.RECTANGLE = 1
    )
    overlay.fill.solid()
    overlay.fill.fore_color.rgb = RGBColor(0, 0, 0)
    overlay.shadow.inherit = False
    overlay.line.fill.background()
    # Set overlay transparency via XML (access the shape's XML element, not the fill object)
    from pptx.oxml.ns import qn
    solid = overlay._element.find(f'.//{qn("a:solidFill")}')
    if solid is not None:
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is not None:
            alpha = srgb.makeelement(qn("a:alpha"), {"val": "40000"})  # 40% opacity
            srgb.append(alpha)
    # Title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = theme["title_color"]
    p.alignment = PP_ALIGN.CENTER
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(24)
        p2.font.color.rgb = theme["text_color"]
        p2.alignment = PP_ALIGN.CENTER
    return slide
```

#### `left_img_right_text` — Image left, text right

```python
def add_left_img_right_text(prs, img_path, title, bullets, theme=THEME):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # Solid background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = theme["bg_color"]
    # Image on left (half width)
    slide.shapes.add_picture(img_path, 0, 0, Inches(6.5), prs.slide_height)
    # Title
    txBox = slide.shapes.add_textbox(Inches(7), Inches(0.5), Inches(5.8), Inches(1.2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = theme["title_size"]
    p.font.bold = True
    p.font.color.rgb = theme["title_color"]
    # Bullets
    txBox2 = slide.shapes.add_textbox(Inches(7), Inches(2), Inches(5.8), Inches(4.5))
    tf2 = txBox2.text_frame
    tf2.word_wrap = True
    for i, line in enumerate(bullets.split("\n")):
        line = line.strip().lstrip("•-").strip()
        if not line:
            continue
        p = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
        p.text = f"  {line}"
        p.font.size = theme["body_size"]
        p.font.color.rgb = theme["text_color"]
        p.space_after = Pt(12)
    return slide
```

#### `top_img_bottom_text` — Image top, text bottom

```python
def add_top_img_bottom_text(prs, img_path, title, bullets, theme=THEME):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = theme["bg_color"]
    # Image on top (60% height)
    slide.shapes.add_picture(img_path, 0, 0, prs.slide_width, Inches(4.5))
    # Title
    txBox = slide.shapes.add_textbox(Inches(0.8), Inches(4.8), Inches(11.5), Inches(0.8))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = theme["title_color"]
    # Bullets
    txBox2 = slide.shapes.add_textbox(Inches(0.8), Inches(5.7), Inches(11.5), Inches(1.5))
    tf2 = txBox2.text_frame
    tf2.word_wrap = True
    for i, line in enumerate(bullets.split("\n")):
        line = line.strip().lstrip("•-").strip()
        if not line:
            continue
        p = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
        p.text = f"  {line}"
        p.font.size = Pt(16)
        p.font.color.rgb = theme["text_color"]
    return slide
```

#### `center_text` — Section divider / title-only

```python
def add_center_text_slide(prs, img_path, title, subtitle="", theme=THEME):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    if img_path and os.path.exists(img_path):
        slide.shapes.add_picture(img_path, 0, 0, prs.slide_width, prs.slide_height)
        # Add overlay same as full_bg
    else:
        bg = slide.background
        bg.fill.solid()
        bg.fill.fore_color.rgb = theme["bg_color"]
    txBox = slide.shapes.add_textbox(Inches(2), Inches(2.8), Inches(9), Inches(2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = theme["title_color"]
    p.alignment = PP_ALIGN.CENTER
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(20)
        p2.font.color.rgb = theme["text_color"]
        p2.alignment = PP_ALIGN.CENTER
    return slide
```

#### `two_column` — Two-column text (for data slides)

```python
def add_two_column_slide(prs, img_path, title, bullets, theme=THEME):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = theme["bg_color"]
    # Title
    txBox = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.5), Inches(1))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = theme["title_size"]
    p.font.bold = True
    p.font.color.rgb = theme["title_color"]
    # Split bullets into two columns
    lines = [l.strip().lstrip("•-").strip() for l in bullets.split("\n") if l.strip()]
    mid = len(lines) // 2
    left_lines, right_lines = lines[:mid], lines[mid:]
    for col_idx, (col_lines, left_pos) in enumerate([(left_lines, 0.8), (right_lines, 7.0)]):
        txBox = slide.shapes.add_textbox(Inches(left_pos), Inches(1.8), Inches(5.5), Inches(5))
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, line in enumerate(col_lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"  {line}"
            p.font.size = theme["body_size"]
            p.font.color.rgb = theme["text_color"]
            p.space_after = Pt(10)
    if img_path and os.path.exists(img_path):
        slide.shapes.add_picture(img_path, Inches(9.5), Inches(4.5), Inches(3.5), Inches(2.5))
    return slide
```

### 5. Assembly Loop

```python
import os

LAYOUT_MAP = {
    "full_bg": add_full_bg_slide,
    "left_img_right_text": add_left_img_right_text,
    "top_img_bottom_text": add_top_img_bottom_text,
    "center_text": add_center_text_slide,
    "two_column": add_two_column_slide,
}

for row in slides:
    no = row["slide_no"]
    layout = row.get("layout", "left_img_right_text")
    img_path = f"slide_{no}.png"
    title = row.get("title", "")
    bullets = row.get("bullet_points", "")

    fn = LAYOUT_MAP.get(layout, add_left_img_right_text)

    if layout in ("full_bg", "center_text"):
        fn(prs, img_path, title, subtitle=bullets, theme=THEME)
    else:
        fn(prs, img_path, title, bullets, theme=THEME)

prs.save("presentation.pptx")
```

### 6. Post-Assembly Checks

After saving, verify:
- File size is reasonable (images embedded increase size)
- Slide count matches storyboard row count
- Report the output filename and size to the user

## Font Notes

- `python-pptx` embeds font name references, not font files
- Safe cross-platform fonts: Arial, Calibri, Helvetica
- For CJK content: specify "Microsoft YaHei", "Noto Sans CJK SC", or "PingFang SC"
- If the user specifies a custom font, check availability first

## Tips

- Always use `prs.slide_layouts[6]` (blank layout) for full control
- Images should match the slide aspect ratio to avoid stretching
- For dark themes, use light text; for light themes, use dark text
- Keep the overlay opacity between 30%–50% for readability over images
- Speaker notes: `slide.notes_slide.notes_text_frame.text = notes`
