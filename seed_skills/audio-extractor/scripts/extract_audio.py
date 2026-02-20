#!/usr/bin/env python3
"""
Audio extraction helper script using yt-dlp.

Usage:
    python extract_audio.py URL [options]

Options:
    --format FORMAT        Audio format (mp3/m4a/flac/wav/opus/vorbis/best)
    --quality QUALITY      Audio quality (0-10 for VBR, or bitrate like 320K)
    --embed-metadata       Embed metadata in audio file
    --embed-thumbnail      Embed thumbnail as cover art
    --output TEMPLATE      Output filename template
    --playlist-items ITEMS Specific playlist items (e.g., "1:5" or "1,3,5")
    --split-chapters       Split by chapters into separate files

Examples:
    python extract_audio.py "https://youtube.com/watch?v=..." --format mp3
    python extract_audio.py "https://youtube.com/playlist?list=..." --format mp3 --embed-metadata
    python extract_audio.py "https://soundcloud.com/artist/track" --format flac
"""

import subprocess
import sys
import argparse


AUDIO_FORMATS = ["mp3", "m4a", "flac", "wav", "opus", "vorbis", "aac", "alac", "best"]


def build_command(args):
    """Build yt-dlp command from arguments."""
    cmd = ["yt-dlp", "-x"]  # -x for extract audio

    # Audio format
    if args.format:
        cmd.extend(["--audio-format", args.format])

    # Audio quality
    if args.quality:
        cmd.extend(["--audio-quality", args.quality])

    # Metadata
    if args.embed_metadata:
        cmd.append("--embed-metadata")

    if args.embed_thumbnail:
        cmd.append("--embed-thumbnail")

    # Output template
    if args.output:
        cmd.extend(["-o", args.output])

    # Playlist handling
    if args.playlist_items:
        cmd.extend(["-I", args.playlist_items])

    # Split by chapters
    if args.split_chapters:
        cmd.append("--split-chapters")
        if not args.output:
            cmd.extend(["-o", "chapter:%(section_title)s.%(ext)s"])

    # Authentication
    if args.cookies_from:
        cmd.extend(["--cookies-from-browser", args.cookies_from])

    # Download archive
    if args.archive:
        cmd.extend(["--download-archive", args.archive])

    # Performance
    if args.concurrent:
        cmd.extend(["--concurrent-fragments", str(args.concurrent)])

    # Post-processing
    if args.normalize:
        cmd.extend(["--postprocessor-args", "ffmpeg:-af loudnorm"])

    # URL
    cmd.append(args.url)

    return cmd


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio from videos using yt-dlp"
    )
    parser.add_argument("url", help="URL to extract audio from")
    parser.add_argument(
        "--format", "-f",
        choices=AUDIO_FORMATS,
        default="mp3",
        help="Audio format (default: mp3)"
    )
    parser.add_argument(
        "--quality", "-q",
        default="0",
        help="Audio quality: 0-10 for VBR (0=best), or bitrate like 320K"
    )
    parser.add_argument(
        "--embed-metadata", "-m",
        action="store_true",
        default=True,
        help="Embed metadata (default: enabled)"
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Disable metadata embedding"
    )
    parser.add_argument(
        "--embed-thumbnail", "-t",
        action="store_true",
        default=True,
        help="Embed thumbnail as cover art (default: enabled)"
    )
    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="Disable thumbnail embedding"
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
        "--split-chapters",
        action="store_true",
        help="Split into separate files by chapter"
    )
    parser.add_argument(
        "--cookies-from",
        choices=["firefox", "chrome", "chromium", "edge", "safari"],
        help="Browser to extract cookies from"
    )
    parser.add_argument(
        "--archive",
        help="Download archive file to skip already downloaded"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Number of concurrent fragment downloads"
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize audio volume using loudnorm filter"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print command without executing"
    )

    args = parser.parse_args()

    # Handle negation flags
    if args.no_metadata:
        args.embed_metadata = False
    if args.no_thumbnail:
        args.embed_thumbnail = False

    cmd = build_command(args)

    if args.dry_run:
        print("Command:", " ".join(cmd))
        return 0

    print(f"Extracting audio: {args.url}")
    print(f"Format: {args.format}")
    print(f"Quality: {args.quality}")
    print()

    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
