---
name: gemini-imagegen
description: >
  Generate and edit images using Google Gemini's native image generation models
  (Nano Banana / Nano Banana Pro). Supports text-to-image, image editing with reference
  images, multi-image composition, and character consistency. Use when the user asks to
  generate images via Gemini, create AI illustrations, edit photos with Gemini, or needs
  high-quality image generation with the Google API. Requires GEMINI_API_KEY.
  Triggers: "generate image with gemini", "nano banana", "gemini image", "create illustration",
  "AI generate picture", "text to image".
---

# Gemini Image Generation

Generate and edit images via Google Gemini's native multimodal image generation.

## Model Selection

| Model ID | Codename | Best for | Max resolution |
|----------|----------|----------|---------------|
| `gemini-2.5-flash-image` | Nano Banana | Fast drafts, high-volume, low-latency | 1K |
| `gemini-3-pro-image-preview` | Nano Banana Pro | Studio-quality, text rendering, complex prompts | 4K |

Default: `gemini-3-pro-image-preview` (Pro) unless speed/cost is a concern.

## Setup

```python
# Install (once)
# pip install google-genai

from google import genai
import os, base64

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
```

If `GEMINI_API_KEY` is missing, instruct the user to set it as an environment variable.
Never ask the user to paste the key in chat.

## Text-to-Image

```python
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents="A photorealistic cat on a rainbow sofa",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)

# Extract and save
for part in response.candidates[0].content.parts:
    if part.inline_data is not None:
        with open("output.png", "wb") as f:
            f.write(part.inline_data.data)
        break
```

## Aspect Ratio

Set via `image_config`:

```python
config=types.GenerateContentConfig(
    response_modalities=["TEXT", "IMAGE"],
    image_config=types.ImageConfig(
        aspect_ratio="16:9",  # for slides / widescreen
    ),
)
```

Supported ratios: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`

Common choices:
- Slides / presentations → `16:9`
- Social media / portraits → `9:16` or `4:5`
- Square thumbnails → `1:1`

## Image Editing (with reference image)

```python
from google.genai import types
from pathlib import Path
import base64

ref_bytes = Path("input.jpg").read_bytes()

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[
        types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64encode(ref_bytes).decode())),
        types.Part(text="Remove the background and replace with a sunset gradient"),
    ],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)
```

Pro supports up to 14 reference images for multi-image composition and up to 5 human
reference images for character/identity consistency.

## Batch Generation (for slides)

When generating multiple images (e.g. one per slide), loop sequentially
and save with numbered filenames:

```python
import os, time
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompts = [...]  # list of prompt strings

for i, prompt in enumerate(prompts, 1):
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9"),
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            with open(f"slide_{i}.png", "wb") as f:
                f.write(part.inline_data.data)
            break
    time.sleep(1)  # rate limit courtesy
```

## Error Handling

- **Safety filter block**: The model may refuse prompts it deems unsafe. Adjust the prompt
  to be less ambiguous (remove violent/adult/medical imagery language) and retry.
- **Empty response**: If `response.candidates` is empty or has no image parts, the prompt
  may be too vague. Add concrete scene details and retry.
- **Rate limit (429)**: Back off with exponential delay. Default: `time.sleep(2 ** attempt)`.
- **Timeout**: Set a reasonable timeout; Pro model may take 10–30s for complex prompts.

## Prompt Best Practices

- Structure: **scene → subject → style → composition → constraints**
- Always specify art style: "flat vector illustration", "watercolor painting", "3D render", "photorealistic photograph"
- Include lighting and mood: "soft diffused lighting", "dramatic rim light", "golden hour"
- For text in images: quote exact text, specify font style and placement
- For slide illustrations: add "negative space on [side]" to leave room for text overlay
- Use English prompts even for non-English content (better generation quality)
- Keep prompts under 500 words; be specific but not verbose

## Style Consistency for Multi-Image Sets

When generating a series (e.g. slide deck), prepend a **style prefix** to every prompt:

```
Style prefix: "flat vector illustration, soft pastel color palette, clean lines, minimal detail, 16:9 widescreen"

Slide 1 prompt: "{style_prefix}, a wide establishing shot of a modern office building at sunrise"
Slide 2 prompt: "{style_prefix}, a close-up of hands typing on a laptop keyboard"
```

This ensures visual coherence across all generated images.
