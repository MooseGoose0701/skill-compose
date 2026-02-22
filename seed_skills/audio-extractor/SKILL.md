---
name: audio-extractor
description: Extract audio from videos and download audio-only content from 1500+ websites using yt-dlp. Converts to MP3, M4A, FLAC, WAV, or OPUS with embedded metadata and cover art. Use when the user wants to extract audio from videos, download podcasts, download music from YouTube/SoundCloud/Bandcamp, convert video to audio, or batch download playlist audio. Triggers on requests like 'extract audio', 'download as MP3', 'get the audio from this video', 'download this podcast', 'download music', 'convert to FLAC'.
---

# Audio Extractor

Extract pure audio from videos and download audio content. Supports format conversion, metadata embedding, and batch playlist processing.

## Prerequisites

- **Executor**: Must use the `remotion` executor (provides yt-dlp, ffmpeg, deno)
- **JS Runtime**: deno is required for YouTube extraction (yt-dlp 2025+ default). The remotion executor includes deno.
- **ffmpeg**: Required for audio format conversion and metadata embedding. Included in remotion executor.

## Limitations

| Issue | Detail |
|-------|--------|
| **YouTube rate limiting** | Server IPs are frequently rate-limited by YouTube. If you get "This content isn't available, try again later", wait ~1 hour or ask the user to upload the audio file directly. |
| **YouTube JS runtime** | yt-dlp requires deno for YouTube. Without it: `No supported JavaScript runtime could be found`. |
| **Geo-restrictions** | Some content may be region-locked. Use `--geo-bypass` flag. |
| **Authentication** | Some platforms require cookies. Use `--cookies-from-browser` or `--cookies cookies.txt`. |

**Fallback strategy**: If YouTube download fails, suggest the user upload the audio file directly or provide a direct audio URL.

## Quick Start

```bash
# Extract audio (best quality, original format)
yt-dlp -x "URL"

# Extract as MP3
yt-dlp -x --audio-format mp3 "URL"

# MP3 with metadata and cover art
yt-dlp -x --audio-format mp3 --embed-metadata --embed-thumbnail "URL"
```

## Audio Formats

### Format Selection

| Format | Command | Use Case |
|--------|---------|----------|
| MP3 | `--audio-format mp3` | Universal compatibility |
| M4A/AAC | `--audio-format m4a` | Apple devices, good quality/size |
| FLAC | `--audio-format flac` | Lossless, archival |
| WAV | `--audio-format wav` | Uncompressed, editing |
| OPUS | `--audio-format opus` | Best quality/size ratio |
| Vorbis | `--audio-format vorbis` | Open source, OGG container |
| Best | `--audio-format best` | Keep original (no conversion) |

### Quality Control

```bash
# VBR quality (0=best, 10=worst)
yt-dlp -x --audio-format mp3 --audio-quality 0 "URL"

# Specific bitrate
yt-dlp -x --audio-format mp3 --audio-quality 320K "URL"
yt-dlp -x --audio-format mp3 --audio-quality 192K "URL"

# FLAC (lossless - quality setting ignored)
yt-dlp -x --audio-format flac "URL"
```

## Metadata Embedding

### Embed All Metadata

```bash
# Metadata + thumbnail as cover art
yt-dlp -x --audio-format mp3 \
       --embed-metadata \
       --embed-thumbnail \
       "URL"
```

### What Gets Embedded

- Title
- Artist/Uploader
- Album (playlist name if applicable)
- Track number (playlist index)
- Upload date
- Description
- Thumbnail as cover art

### Custom Metadata

```bash
# Override artist
yt-dlp -x --audio-format mp3 \
       --embed-metadata \
       --parse-metadata "uploader:%(artist)s" \
       "URL"

# Set album name
yt-dlp -x --audio-format mp3 \
       --embed-metadata \
       --parse-metadata "playlist:%(album)s" \
       "URL"
```

## Playlist/Batch Processing

### Download Full Playlist as Audio

```bash
# Basic playlist extraction
yt-dlp -x --audio-format mp3 "PLAYLIST_URL"

# With numbering and organization
yt-dlp -x --audio-format mp3 \
       --embed-metadata --embed-thumbnail \
       -o "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" \
       "PLAYLIST_URL"

# Skip already downloaded
yt-dlp -x --audio-format mp3 \
       --download-archive downloaded.txt \
       "PLAYLIST_URL"
```

### Selective Download

```bash
# First 10 tracks
yt-dlp -x --audio-format mp3 -I 1:10 "PLAYLIST_URL"

# Specific tracks
yt-dlp -x --audio-format mp3 -I 1,5,10 "PLAYLIST_URL"

# Last 5 tracks
yt-dlp -x --audio-format mp3 -I -5: "PLAYLIST_URL"
```

## Output Naming

### Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `%(title)s` | Track title | Song Name |
| `%(uploader)s` | Artist/Channel | Artist Name |
| `%(playlist)s` | Album/Playlist | My Playlist |
| `%(playlist_index)s` | Track number | 1 |
| `%(upload_date)s` | Release date | 20231215 |
| `%(ext)s` | Extension | mp3 |

### Common Patterns

```bash
# Artist - Title
yt-dlp -x -o "%(uploader)s - %(title)s.%(ext)s" "URL"

# Album folder with track numbers
yt-dlp -x -o "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" "PLAYLIST_URL"

# Date-organized
yt-dlp -x -o "%(upload_date>%Y-%m)s/%(title)s.%(ext)s" "URL"
```

## Platform-Specific

### YouTube Music / YouTube

```bash
# Standard extraction
yt-dlp -x --audio-format mp3 --embed-metadata --embed-thumbnail "URL"

# For music videos, prefer audio stream
yt-dlp -f "bestaudio" -x --audio-format mp3 "URL"
```

### SoundCloud

```bash
# Direct audio (often already MP3)
yt-dlp -x "https://soundcloud.com/artist/track"

# Playlist/album
yt-dlp -x --audio-format mp3 \
       -o "%(uploader)s - %(album)s/%(playlist_index)02d - %(title)s.%(ext)s" \
       "https://soundcloud.com/artist/sets/album"
```

### Bandcamp

```bash
# Full album with metadata
yt-dlp -x --audio-format flac \
       --embed-metadata --embed-thumbnail \
       -o "%(album)s/%(track_number)02d - %(track)s.%(ext)s" \
       "https://artist.bandcamp.com/album/name"
```

### Podcasts

```bash
# Single episode
yt-dlp -x --audio-format mp3 --embed-metadata "EPISODE_URL"

# Full podcast feed (RSS)
yt-dlp -x --audio-format mp3 \
       -o "%(playlist)s/%(upload_date)s - %(title)s.%(ext)s" \
       --download-archive podcasts.txt \
       "RSS_FEED_URL"

# Apple Podcasts
yt-dlp -x --audio-format mp3 \
       --embed-metadata \
       "https://podcasts.apple.com/..."
```

### Bilibili

```bash
yt-dlp -x --audio-format mp3 \
       --cookies-from-browser chrome \
       "https://bilibili.com/video/BV..."
```

## Advanced Options

### Parallel Downloads

```bash
# Faster playlist downloads
yt-dlp -x --audio-format mp3 \
       --concurrent-fragments 4 \
       "PLAYLIST_URL"
```

### Post-Processing

```bash
# Normalize audio volume
yt-dlp -x --audio-format mp3 \
       --postprocessor-args "ffmpeg:-af loudnorm" \
       "URL"

# Trim silence
yt-dlp -x --audio-format mp3 \
       --postprocessor-args "ffmpeg:-af silenceremove=1:0:-50dB" \
       "URL"
```

### Split by Chapters

```bash
# Split video into separate audio files by chapter
yt-dlp -x --audio-format mp3 \
       --split-chapters \
       -o "chapter:%(section_title)s.%(ext)s" \
       "URL"
```

## Complete Examples

**Extract audio from YouTube playlist as high-quality MP3:**
```bash
yt-dlp -x --audio-format mp3 --audio-quality 0 \
       --embed-metadata --embed-thumbnail \
       -o "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" \
       --download-archive downloaded.txt \
       "https://youtube.com/playlist?list=..."
```

**Download podcast episode:**
```bash
yt-dlp -x --audio-format mp3 \
       --embed-metadata \
       -o "%(uploader)s - %(title)s.%(ext)s" \
       "https://podcasts.apple.com/..."
```

**Extract FLAC from Bandcamp album:**
```bash
yt-dlp -x --audio-format flac \
       --embed-metadata --embed-thumbnail \
       -o "%(album)s/%(track_number)02d - %(track)s.%(ext)s" \
       "https://artist.bandcamp.com/album/..."
```

**Extract audio from local video file:**
```bash
ffmpeg -i video.mp4 -vn -acodec libmp3lame -q:a 0 audio.mp3
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "ffmpeg not found" | Install ffmpeg: `brew install ffmpeg` / `apt install ffmpeg` |
| No cover art | Add `--embed-thumbnail` (requires ffmpeg) |
| Wrong metadata | Use `--parse-metadata` to remap fields |
| Poor quality | Use `--audio-quality 0` or lossless format |
