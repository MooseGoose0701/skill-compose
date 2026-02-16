"""Async event channel between agent (producer) and API endpoint (consumer).

Inspired by Pi Agent's EventStream — a CSP-style push/pull channel using asyncio.Queue.
Supports bidirectional communication: agent pushes events, API injects steering messages.
"""
import asyncio
from typing import Optional

from app.agent.agent import StreamEvent


class EventStream:
    """Async event channel for streaming agent events to API consumers.

    Producer (agent): calls push() / close()
    Consumer (API endpoint): async iterates over the stream
    Steering (API endpoint → agent): inject() / has_injection() / get_injection()
    """

    def __init__(self):
        self._queue: asyncio.Queue[Optional[StreamEvent]] = asyncio.Queue()
        self._injection_queue: asyncio.Queue[str] = asyncio.Queue()
        self._closed = False

    async def push(self, event: StreamEvent):
        """Push an event into the stream. No-op if already closed."""
        if not self._closed:
            await self._queue.put(event)

    async def close(self):
        """Signal that no more events will be pushed (sends sentinel)."""
        if not self._closed:
            self._closed = True
            await self._queue.put(None)

    @property
    def closed(self) -> bool:
        return self._closed

    # --- Steering injection (API → Agent) ---

    async def inject(self, message: str):
        """API endpoint: inject a steering message for the agent to consume."""
        await self._injection_queue.put(message)

    def has_injection(self) -> bool:
        """Agent: check if any steering messages are waiting (non-blocking)."""
        return not self._injection_queue.empty()

    def get_injection_nowait(self) -> Optional[str]:
        """Agent: consume a steering message (non-blocking). Returns None if empty."""
        try:
            return self._injection_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def __aiter__(self):
        """Async iterate over events until the stream is closed."""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event
