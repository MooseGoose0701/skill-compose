#!/bin/bash
# Setup script for download-video-from-url skill
# Installs yt-dlp, ffmpeg, and aria2

set -e

echo "=== Installing dependencies for download-video-from-url ==="

# Install yt-dlp
echo "[1/3] Installing yt-dlp..."
pip install -U yt-dlp

# Install ffmpeg
echo "[2/3] Installing ffmpeg..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y ffmpeg
elif command -v brew &> /dev/null; then
    brew install ffmpeg
else
    echo "Warning: Could not install ffmpeg. Please install it manually."
fi

# Install aria2
echo "[3/3] Installing aria2..."
if command -v apt-get &> /dev/null; then
    apt-get install -y aria2
elif command -v brew &> /dev/null; then
    brew install aria2
else
    echo "Warning: Could not install aria2. Please install it manually."
fi

echo "=== Setup complete ==="
