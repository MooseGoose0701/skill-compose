"""
Tests for EventStream — async event channel with bidirectional steering support.

Tests:
- Basic inject/get_injection functionality
- has_injection when empty
- Multiple injections in FIFO order
- Injection after stream is closed
"""
import asyncio

import pytest

from app.agent.agent import StreamEvent
from app.agent.event_stream import EventStream


@pytest.mark.asyncio
async def test_inject_and_get():
    """inject() puts a message, get_injection_nowait() retrieves it."""
    es = EventStream()
    await es.inject("fix the bug")
    assert es.has_injection() is True
    msg = es.get_injection_nowait()
    assert msg == "fix the bug"
    assert es.has_injection() is False


@pytest.mark.asyncio
async def test_has_injection_empty():
    """Empty injection queue returns False."""
    es = EventStream()
    assert es.has_injection() is False
    assert es.get_injection_nowait() is None


@pytest.mark.asyncio
async def test_multiple_injections_fifo():
    """Multiple injected messages are consumed in FIFO order."""
    es = EventStream()
    await es.inject("first")
    await es.inject("second")
    await es.inject("third")

    assert es.get_injection_nowait() == "first"
    assert es.get_injection_nowait() == "second"
    assert es.get_injection_nowait() == "third"
    assert es.get_injection_nowait() is None


@pytest.mark.asyncio
async def test_inject_after_close():
    """Injection still works even after the event stream is closed.

    This is by design: the injection queue is separate from the event queue.
    The agent may still check injections before exiting its loop.
    """
    es = EventStream()
    await es.close()
    assert es.closed is True

    await es.inject("late steering")
    assert es.has_injection() is True
    msg = es.get_injection_nowait()
    assert msg == "late steering"


@pytest.mark.asyncio
async def test_push_and_iterate():
    """Basic push/iterate still works alongside injection."""
    es = EventStream()
    event = StreamEvent(event_type="turn_start", turn=1, data={"turn": 1})

    await es.push(event)
    await es.inject("steer me")
    await es.close()

    collected = []
    async for e in es:
        collected.append(e)

    assert len(collected) == 1
    assert collected[0].event_type == "turn_start"

    # Injection queue is independent
    assert es.has_injection() is True
    assert es.get_injection_nowait() == "steer me"


@pytest.mark.asyncio
async def test_steering_received_event_with_id():
    """StreamEvent for steering_received can carry a steering_id in data."""
    import uuid
    es = EventStream()
    await es.inject("focus on tests")
    msg = es.get_injection_nowait()
    assert msg == "focus on tests"

    steer_id = f"steer-{uuid.uuid4().hex[:12]}"
    event = StreamEvent(
        event_type="steering_received",
        turn=1,
        data={"message": msg, "steering_id": steer_id},
    )

    # Push event through the event stream
    await es.push(event)
    await es.close()

    collected = []
    async for e in es:
        collected.append(e)

    assert len(collected) == 1
    assert collected[0].event_type == "steering_received"
    assert collected[0].data["message"] == "focus on tests"
    assert collected[0].data["steering_id"] == steer_id
    assert steer_id.startswith("steer-")


@pytest.mark.asyncio
async def test_duplicate_steering_messages_get_unique_ids():
    """Even identical steering messages get unique steering_ids via _make_steering_event."""
    from app.agent.agent import _make_steering_event

    events = [_make_steering_event(1, "continue") for _ in range(10)]
    ids = {e.data["steering_id"] for e in events}
    assert len(ids) == 10
    # All have correct structure
    for e in events:
        assert e.event_type == "steering_received"
        assert e.data["message"] == "continue"
