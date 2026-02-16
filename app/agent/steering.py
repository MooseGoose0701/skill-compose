"""Filesystem-based steering message queue for cross-worker communication.

When uvicorn runs with multiple workers, each worker is a separate process
with its own memory. The SSE stream lives in one worker, but a steer POST
may land on any worker. This module uses the shared filesystem (/tmp) as a
cross-process message queue.

Flow:
1. Steer endpoint writes a .msg file to /tmp/agent_steering/{trace_id}/
2. A polling task in the streaming worker reads .msg files and injects
   them into the local EventStream
3. The agent loop picks up injected messages at tool boundaries

Atomicity:
- write_steering_message uses write-then-rename to prevent partial reads.
  rename() is atomic on the same filesystem (Linux guarantee).
- Filenames include time_ns + random suffix to prevent collision across workers.
- Polling only reads .msg files, ignoring .tmp files being written.
"""
import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from app.agent.event_stream import EventStream

logger = logging.getLogger("skills_api")

STEERING_DIR = Path("/tmp/agent_steering")


def write_steering_message(trace_id: str, message: str) -> None:
    """Write a steering message to the filesystem queue (atomic)."""
    trace_dir = STEERING_DIR / trace_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    # Use time_ns + pid + random bytes to avoid filename collision across workers
    unique = f"{time.time_ns()}_{os.getpid()}_{os.urandom(4).hex()}"
    tmp_file = trace_dir / f"{unique}.tmp"
    tmp_file.write_text(message, encoding="utf-8")
    # Atomic rename: polling only reads .msg files, so this is safe
    tmp_file.rename(trace_dir / f"{unique}.msg")


def cleanup_steering_dir(trace_id: str) -> None:
    """Remove steering directory for a trace."""
    trace_dir = STEERING_DIR / trace_id
    if trace_dir.exists():
        shutil.rmtree(trace_dir, ignore_errors=True)


async def poll_steering_messages(
    trace_id: str,
    event_stream: EventStream,
    poll_interval: float = 0.3,
) -> None:
    """Poll filesystem for steering messages and inject into EventStream.

    Runs until event_stream is closed or the task is cancelled.
    Only reads .msg files (fully written), ignoring .tmp files in flight.
    """
    trace_dir = STEERING_DIR / trace_id
    while not event_stream.closed:
        try:
            if trace_dir.exists():
                for msg_file in sorted(trace_dir.glob("*.msg")):
                    try:
                        message = msg_file.read_text(encoding="utf-8")
                        await event_stream.inject(message)
                        msg_file.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(poll_interval)
