---
name: remotion-best-practices
description: Best practices for Remotion - Video creation in React
metadata:
  tags: remotion, video, react, animation, composition
---

## Prerequisites

- **Executor**: Use the `remotion` executor (provides Node.js 20, Chromium, ffmpeg, yt-dlp, deno)
- **Do NOT** use `npx create-video` — it is interactive and will hang in automated environments

## Project Initialization (Non-interactive)

`npx create-video` uses interactive prompts that cannot be bypassed. Instead, manually initialize:

```bash
# 1. Create project and install dependencies
mkdir -p my-video && cd my-video
npm init -y

# 2. Install Remotion core + common packages
npm install remotion @remotion/cli @remotion/media-utils react react-dom

# 3. Optional: 3D / Three.js support
npm install @remotion/three @react-three/fiber @react-three/drei @react-three/postprocessing three

# 4. Optional: Zod schemas for parametrizable videos
npm install @remotion/zod-types zod@3.22.3  # zod version must match @remotion/zod-types peer dep
```

Minimal project structure:
```
my-video/
├── package.json
├── remotion.config.ts    # Config.setVideoImageFormat("jpeg"); Config.setOverwriteOutput(true);
├── tsconfig.json
├── public/               # Static assets (audio, images)
└── src/
    ├── index.ts          # registerRoot(Root)
    ├── Root.tsx           # <Composition> definitions
    └── MyVideo.tsx        # Video component
```

**Tip:** The remotion executor pre-caches common npm packages at `/opt/remotion-template/node_modules/`. You can copy them to skip download:
```bash
cp -r /opt/remotion-template/node_modules ./node_modules
```

**IMPORTANT — Do NOT run `tsc` or `npx tsc`:**
- `npx remotion render` handles TypeScript compilation internally via esbuild — it is much faster and more lenient than `tsc`.
- Running `tsc --noEmit` will produce spurious type errors (missing module declarations, JSX issues) that are irrelevant to Remotion rendering.
- If you see TypeScript errors, **ignore them and proceed directly to `npx remotion render`**. Fix only errors reported by the renderer itself.

**IMPORTANT — Project directory:**
- Always create projects using **relative paths** (e.g., `mkdir -p my-video && cd my-video`). Do NOT use absolute paths like `/app/workspace/` or `/app/my-project/`.
- The executor automatically sets the working directory to the correct workspace. Using absolute paths bypasses workspace isolation.

## Rendering Performance

**IMPORTANT:** Always use these flags for maximum rendering speed:

```bash
# Standard render (2D content — no --gl needed)
npx remotion render src/index.ts MyComposition out/video.mp4 \
  --concurrency=16

# 3D content (Three.js / WebGL) — MUST use --gl=swangle
npx remotion render src/index.ts MyComposition out/video.mp4 \
  --concurrency=16 \
  --gl=swangle
```

In `remotion.config.ts`, always set high concurrency:
```ts
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(16);      // Use 16 parallel browser tabs (NOT default 4)
// For 3D/WebGL content only:
Config.setChromiumOpenGlRenderer("swangle");  // SwiftShader software GL for headless containers
```

**GL renderer for 3D/WebGL content:**
- `--gl=swangle` — **Required for 3D.** Uses SwiftShader (bundled in Chrome). Works without GPU. Supports full concurrency=16.
- `--gl=angle` — Does NOT work in headless Docker without GPU. Do not use.
- Never omit `--gl` for Three.js content — default mode has no WebGL support in headless containers.

**Segment rendering for long videos (>60s):** Split into 30-second segments and render in parallel:
```bash
# Render segment (frames 0-899 = first 30s at 30fps)
npx remotion render src/index.ts MyComp out/seg_000.mp4 \
  --frames=0-899 --concurrency=16 --gl=swangle

# Merge all segments with ffmpeg
ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy out/final.mp4
```

## When to use

Use this skills whenever you are dealing with Remotion code to obtain the domain-specific knowledge.

## Captions

When dealing with captions or subtitles, load the [./rules/subtitles.md](./rules/subtitles.md) file for more information.

## Using FFmpeg

For some video operations, such as trimming videos or detecting silence, FFmpeg should be used. Load the [./rules/ffmpeg.md](./rules/ffmpeg.md) file for more information.

## Audio visualization

When needing to visualize audio (spectrum bars, waveforms, bass-reactive effects), load the [./rules/audio-visualization.md](./rules/audio-visualization.md) file for more information.

## How to use

Read individual rule files for detailed explanations and code examples:

- [rules/3d.md](rules/3d.md) - 3D content in Remotion using Three.js and React Three Fiber
- [rules/animations.md](rules/animations.md) - Fundamental animation skills for Remotion
- [rules/assets.md](rules/assets.md) - Importing images, videos, audio, and fonts into Remotion
- [rules/audio.md](rules/audio.md) - Using audio and sound in Remotion - importing, trimming, volume, speed, pitch
- [rules/calculate-metadata.md](rules/calculate-metadata.md) - Dynamically set composition duration, dimensions, and props
- [rules/can-decode.md](rules/can-decode.md) - Check if a video can be decoded by the browser using Mediabunny
- [rules/charts.md](rules/charts.md) - Chart and data visualization patterns for Remotion (bar, pie, line, stock charts)
- [rules/compositions.md](rules/compositions.md) - Defining compositions, stills, folders, default props and dynamic metadata
- [rules/extract-frames.md](rules/extract-frames.md) - Extract frames from videos at specific timestamps using Mediabunny
- [rules/fonts.md](rules/fonts.md) - Loading Google Fonts and local fonts in Remotion
- [rules/get-audio-duration.md](rules/get-audio-duration.md) - Getting the duration of an audio file in seconds with Mediabunny
- [rules/get-video-dimensions.md](rules/get-video-dimensions.md) - Getting the width and height of a video file with Mediabunny
- [rules/get-video-duration.md](rules/get-video-duration.md) - Getting the duration of a video file in seconds with Mediabunny
- [rules/gifs.md](rules/gifs.md) - Displaying GIFs synchronized with Remotion's timeline
- [rules/images.md](rules/images.md) - Embedding images in Remotion using the Img component
- [rules/light-leaks.md](rules/light-leaks.md) - Light leak overlay effects using @remotion/light-leaks
- [rules/lottie.md](rules/lottie.md) - Embedding Lottie animations in Remotion
- [rules/measuring-dom-nodes.md](rules/measuring-dom-nodes.md) - Measuring DOM element dimensions in Remotion
- [rules/measuring-text.md](rules/measuring-text.md) - Measuring text dimensions, fitting text to containers, and checking overflow
- [rules/sequencing.md](rules/sequencing.md) - Sequencing patterns for Remotion - delay, trim, limit duration of items
- [rules/tailwind.md](rules/tailwind.md) - Using TailwindCSS in Remotion
- [rules/text-animations.md](rules/text-animations.md) - Typography and text animation patterns for Remotion
- [rules/timing.md](rules/timing.md) - Interpolation curves in Remotion - linear, easing, spring animations
- [rules/transitions.md](rules/transitions.md) - Scene transition patterns for Remotion
- [rules/transparent-videos.md](rules/transparent-videos.md) - Rendering out a video with transparency
- [rules/trimming.md](rules/trimming.md) - Trimming patterns for Remotion - cut the beginning or end of animations
- [rules/videos.md](rules/videos.md) - Embedding videos in Remotion - trimming, volume, speed, looping, pitch
- [rules/parameters.md](rules/parameters.md) - Make a video parametrizable by adding a Zod schema
- [rules/maps.md](rules/maps.md) - Add a map using Mapbox and animate it
- [rules/voiceover.md](rules/voiceover.md) - Adding AI-generated voiceover to Remotion compositions using ElevenLabs TTS
