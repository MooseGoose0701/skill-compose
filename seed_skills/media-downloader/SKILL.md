---
name: media-downloader
description: Download videos and audio from 1500+ websites including YouTube, Bilibili, TikTok, Twitter/X, Instagram, Vimeo, and more using yt-dlp. Use when the user wants to download videos, save media from social platforms, download with specific resolution (720p/1080p/4K), get subtitles, or download entire playlists. Triggers on requests like 'download this video', 'save this YouTube video', 'download in 1080p', 'download with subtitles', 'download this playlist'.
---

# Media Downloader

Download video/audio from 1500+ websites using yt-dlp. Supports format selection, subtitles, playlists, and custom output naming.

## Quick Start

```bash
# Basic download (best quality)
yt-dlp "URL"

# Specific resolution
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" "URL"

# With subtitles
yt-dlp --write-subs --sub-langs "en,zh" "URL"

# Audio only
yt-dlp -f "bestaudio" "URL"
```

## Format Selection

### Resolution Presets

| Request | Command |
|---------|---------|
| Best quality | `-f "bestvideo+bestaudio/best"` |
| 4K | `-f "bestvideo[height<=2160]+bestaudio/best"` |
| 1080p | `-f "bestvideo[height<=1080]+bestaudio/best"` |
| 720p | `-f "bestvideo[height<=720]+bestaudio/best"` |
| 480p | `-f "bestvideo[height<=480]+bestaudio/best"` |

### List Available Formats

```bash
yt-dlp -F "URL"  # Show all formats with codes
```

### Advanced Format Selection

```bash
# Prefer MP4 container
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" "URL"

# Specific format code (from -F output)
yt-dlp -f 137+140 "URL"

# Merge to specific container
yt-dlp --merge-output-format mkv "URL"
```

## Subtitles

### Download Subtitles

```bash
# Manual subtitles (human-created)
yt-dlp --write-subs --sub-langs "en,zh,ja" "URL"

# Auto-generated subtitles
yt-dlp --write-auto-subs --sub-langs "en" "URL"

# Both manual and auto
yt-dlp --write-subs --write-auto-subs --sub-langs "en,zh" "URL"

# Embed subtitles in video (MP4/MKV/WebM)
yt-dlp --write-subs --embed-subs "URL"
```

### List Available Subtitles

```bash
yt-dlp --list-subs "URL"
```

### Subtitle Format

```bash
# Convert to SRT
yt-dlp --write-subs --sub-format srt "URL"

# Available: srt, ass, vtt, lrc
```

## Output Naming

### Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `%(title)s` | Video title | My Video |
| `%(id)s` | Video ID | dQw4w9WgXcQ |
| `%(ext)s` | File extension | mp4 |
| `%(upload_date)s` | Upload date | 20231215 |
| `%(uploader)s` | Channel name | Rick Astley |
| `%(playlist)s` | Playlist name | Best Songs |
| `%(playlist_index)s` | Position in playlist | 01 |
| `%(resolution)s` | Video resolution | 1920x1080 |

### Common Patterns

```bash
# Default: title + extension
yt-dlp -o "%(title)s.%(ext)s" "URL"

# Date prefix
yt-dlp -o "%(upload_date)s - %(title)s.%(ext)s" "URL"

# Organized by uploader
yt-dlp -o "%(uploader)s/%(title)s.%(ext)s" "URL"

# Playlist with numbering
yt-dlp -o "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" "URL"

# Sanitize title (remove special chars)
yt-dlp -o "%(title).100B.%(ext)s" "URL"  # Limit to 100 bytes
```

## Playlist Handling

```bash
# Download entire playlist
yt-dlp "PLAYLIST_URL"

# Only video (not playlist)
yt-dlp --no-playlist "URL"

# Specific items (1-indexed)
yt-dlp -I 1:5 "PLAYLIST_URL"        # First 5
yt-dlp -I 1,3,5 "PLAYLIST_URL"      # Items 1, 3, 5
yt-dlp -I -3: "PLAYLIST_URL"        # Last 3

# Skip already downloaded
yt-dlp --download-archive downloaded.txt "PLAYLIST_URL"
```

## Platform-Specific Notes

### YouTube
- Supports: videos, playlists, channels, shorts, live streams
- Cookies may be needed for age-restricted/member content

### Bilibili
- Use `--cookies-from-browser` for premium content
- Subtitles: `--write-subs --sub-langs "zh-Hans"`

### TikTok / Douyin
- Direct URL download works
- Watermark may be present in some cases

### Twitter/X
- Supports video tweets and spaces
- Use `--cookies-from-browser` for private content

### Instagram
- Stories require login
- Use `--cookies-from-browser firefox` or `--cookies cookies.txt`

## Authentication

```bash
# Browser cookies (recommended)
yt-dlp --cookies-from-browser firefox "URL"
yt-dlp --cookies-from-browser chrome "URL"

# Cookie file
yt-dlp --cookies cookies.txt "URL"

# Username/password (limited support)
yt-dlp -u USERNAME -p PASSWORD "URL"
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Video unavailable" | Try `--cookies-from-browser` |
| Slow download | Add `--concurrent-fragments 4` |
| Format merge fails | Install ffmpeg |
| Geo-blocked | Use `--geo-bypass` or proxy |

### Update yt-dlp

```bash
yt-dlp -U  # Update to latest stable
```

## Complete Examples

**Download YouTube video in 1080p with Chinese subtitles:**
```bash
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best" \
       --write-subs --sub-langs "zh" \
       -o "%(title)s.%(ext)s" \
       "https://youtube.com/watch?v=..."
```

**Download TikTok video:**
```bash
yt-dlp -o "%(uploader)s - %(title)s.%(ext)s" \
       "https://tiktok.com/@user/video/..."
```

**Download Bilibili playlist:**
```bash
yt-dlp --cookies-from-browser chrome \
       -o "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" \
       "https://bilibili.com/video/BV..."
```

**Download Twitter video:**
```bash
yt-dlp --cookies-from-browser firefox \
       "https://twitter.com/user/status/..."
```
