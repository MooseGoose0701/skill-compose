#!/usr/bin/env python3
"""
Media download helper script using yt-dlp.

Usage:
    python download.py URL [options]

Options:
    --resolution RESOLUTION   Target resolution (best/4k/1080p/720p/480p)
    --subtitles LANGS         Subtitle languages (comma-separated, e.g., "en,zh")
    --auto-subs               Include auto-generated subtitles
    --embed-subs              Embed subtitles in video
    --output TEMPLATE         Output filename template
    --playlist-items ITEMS    Specific playlist items (e.g., "1:5" or "1,3,5")
    --cookies-from BROWSER    Extract cookies from browser (firefox/chrome)
    --format FORMAT           Specific format or format selector

Examples:
    python download.py "https://youtube.com/watch?v=..." --resolution 1080p
    python download.py "https://youtube.com/watch?v=..." --subtitles "en,zh" --embed-subs
    python download.py "https://youtube.com/playlist?list=..." --playlist-items "1:10"
"""

import subprocess
import sys
import argparse
from pathlib import Path


RESOLUTION_FORMATS = {
    "best": "bestvideo+bestaudio/best",
    "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
}


def build_command(args):
    """Build yt-dlp command from arguments."""
    cmd = ["yt-dlp"]

    # Format selection
    if args.format:
        cmd.extend(["-f", args.format])
    elif args.resolution:
        format_str = RESOLUTION_FORMATS.get(args.resolution.lower(), args.resolution)
        cmd.extend(["-f", format_str])

    # Subtitles
    if args.subtitles:
        cmd.append("--write-subs")
        cmd.extend(["--sub-langs", args.subtitles])

    if args.auto_subs:
        cmd.append("--write-auto-subs")

    if args.embed_subs:
        cmd.append("--embed-subs")

    # Output template
    if args.output:
        cmd.extend(["-o", args.output])

    # Playlist handling
    if args.playlist_items:
        cmd.extend(["-I", args.playlist_items])

    if args.no_playlist:
        cmd.append("--no-playlist")

    # Authentication
    if args.cookies_from:
        cmd.extend(["--cookies-from-browser", args.cookies_from])

    # Performance
    if args.concurrent:
        cmd.extend(["--concurrent-fragments", str(args.concurrent)])

    # Download archive
    if args.archive:
        cmd.extend(["--download-archive", args.archive])

    # URL
    cmd.append(args.url)

    return cmd


def main():
    parser = argparse.ArgumentParser(
        description="Download media from various platforms using yt-dlp"
    )
    parser.add_argument("url", help="URL to download")
    parser.add_argument(
        "--resolution", "-r",
        choices=["best", "4k", "1080p", "720p", "480p"],
        default="best",
        help="Target resolution (default: best)"
    )
    parser.add_argument(
        "--format", "-f",
        help="Custom format selector (overrides --resolution)"
    )
    parser.add_argument(
        "--subtitles", "-s",
        help="Subtitle languages (comma-separated)"
    )
    parser.add_argument(
        "--auto-subs",
        action="store_true",
        help="Include auto-generated subtitles"
    )
    parser.add_argument(
        "--embed-subs",
        action="store_true",
        help="Embed subtitles in video file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output filename template"
    )
    parser.add_argument(
        "--playlist-items", "-I",
        help="Playlist items to download (e.g., '1:5' or '1,3,5')"
    )
    parser.add_argument(
        "--no-playlist",
        action="store_true",
        help="Download only the video, not the playlist"
    )
    parser.add_argument(
        "--cookies-from",
        choices=["firefox", "chrome", "chromium", "edge", "safari"],
        help="Browser to extract cookies from"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Number of concurrent fragment downloads"
    )
    parser.add_argument(
        "--archive",
        help="Download archive file to skip already downloaded videos"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print command without executing"
    )

    args = parser.parse_args()
    cmd = build_command(args)

    if args.dry_run:
        print("Command:", " ".join(cmd))
        return 0

    print(f"Downloading: {args.url}")
    print(f"Resolution: {args.resolution}")
    if args.subtitles:
        print(f"Subtitles: {args.subtitles}")
    print()

    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
