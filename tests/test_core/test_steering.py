"""
Tests for filesystem-based cross-worker steering queue.

Tests:
- write_steering_message creates .msg files
- poll_steering_messages picks up files and injects into EventStream
- cleanup_steering_dir removes the trace directory
- Multiple messages are consumed in order
"""
import asyncio
from pathlib import Path

import pytest

from app.agent.event_stream import EventStream
from app.agent.steering import (
    STEERING_DIR,
    write_steering_message,
    poll_steering_messages,
    cleanup_steering_dir,
)


@pytest.fixture(autouse=True)
def _cleanup_steering_dir():
    """Ensure steering directory is clean before and after each test."""
    import shutil
    test_dir = STEERING_DIR / "test-trace"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    yield
    if test_dir.exists():
        shutil.rmtree(test_dir)


def test_write_creates_msg_file():
    """write_steering_message creates a .msg file in the trace directory."""
    write_steering_message("test-trace", "hello")
    trace_dir = STEERING_DIR / "test-trace"
    assert trace_dir.exists()
    files = list(trace_dir.glob("*.msg"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "hello"


def test_write_multiple_messages():
    """Multiple writes create multiple .msg files in order."""
    write_steering_message("test-trace", "first")
    write_steering_message("test-trace", "second")
    write_steering_message("test-trace", "third")
    trace_dir = STEERING_DIR / "test-trace"
    files = sorted(trace_dir.glob("*.msg"))
    assert len(files) == 3
    assert files[0].read_text(encoding="utf-8") == "first"
    assert files[1].read_text(encoding="utf-8") == "second"
    assert files[2].read_text(encoding="utf-8") == "third"


def test_cleanup_removes_directory():
    """cleanup_steering_dir removes the trace directory entirely."""
    write_steering_message("test-trace", "msg")
    assert (STEERING_DIR / "test-trace").exists()
    cleanup_steering_dir("test-trace")
    assert not (STEERING_DIR / "test-trace").exists()


def test_cleanup_nonexistent_is_noop():
    """cleanup_steering_dir on nonexistent trace is a no-op."""
    cleanup_steering_dir("test-trace-does-not-exist")


@pytest.mark.asyncio
async def test_poll_picks_up_messages():
    """poll_steering_messages reads .msg files and injects into EventStream."""
    es = EventStream()

    # Write messages before polling starts
    write_steering_message("test-trace", "steer-1")
    write_steering_message("test-trace", "steer-2")

    # Start polling with short interval
    poll_task = asyncio.create_task(
        poll_steering_messages("test-trace", es, poll_interval=0.05)
    )

    # Wait for polling to pick up messages
    await asyncio.sleep(0.2)

    # Close stream to stop polling
    await es.close()
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass

    # Verify messages were injected
    assert es.get_injection_nowait() == "steer-1"
    assert es.get_injection_nowait() == "steer-2"
    assert es.get_injection_nowait() is None

    # Verify files were consumed (deleted)
    trace_dir = STEERING_DIR / "test-trace"
    remaining = list(trace_dir.glob("*.msg")) if trace_dir.exists() else []
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_poll_stops_when_stream_closed():
    """poll_steering_messages exits when event_stream is closed."""
    es = EventStream()
    await es.close()

    # Should exit quickly since stream is already closed
    poll_task = asyncio.create_task(
        poll_steering_messages("test-trace", es, poll_interval=0.05)
    )

    # Should complete within a short time
    await asyncio.sleep(0.15)
    assert poll_task.done() or poll_task.cancelled()
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass
