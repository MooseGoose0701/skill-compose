"""
Abstract base class for channel adapters.

Each adapter connects to an external messaging platform (Feishu, Telegram, etc.)
and routes messages to/from published agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Awaitable


@dataclass
class InboundMessage:
    """A message received from an external channel."""
    channel_type: str
    external_id: str  # Chat/group ID on the platform
    sender_id: str
    sender_name: str
    content: str
    message_type: str = "text"  # text / image / file
    external_message_id: Optional[str] = None
    metadata: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OutboundMessage:
    """A message to send to an external channel."""
    external_id: str  # Chat/group ID to send to
    content: str
    message_type: str = "text"


MessageHandler = Callable[[InboundMessage], Awaitable[None]]


class ChannelAdapter(ABC):
    """Abstract base class for channel adapters.

    Each adapter manages the connection to a specific messaging platform
    and handles sending/receiving messages.
    """

    channel_type: str = ""
    _message_handler: Optional[MessageHandler] = None

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the messaging platform."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    async def send_message(self, message: OutboundMessage) -> None:
        """Send a message to the platform."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the adapter is currently connected."""
        ...

    def set_message_handler(self, handler: MessageHandler):
        """Set the callback for handling inbound messages."""
        self._message_handler = handler
