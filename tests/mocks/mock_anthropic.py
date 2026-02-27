"""
Mock Anthropic client for testing Agent without real API calls.

Also provides mocks for the unified LLMClient used by the agent.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any
from unittest.mock import MagicMock

from app.llm.provider import LLMResponse, LLMTextBlock, LLMToolCall, LLMUsage


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = "Mock response"


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "tool_123"
    name: str = "list_skills"
    input: dict = field(default_factory=dict)


@dataclass
class MockUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class MockResponse:
    """Mock response for raw Anthropic client (legacy tests)."""
    id: str = "msg_test"
    type: str = "message"
    role: str = "assistant"
    content: list = field(default_factory=lambda: [MockTextBlock()])
    model: str = "claude-sonnet-4-5-20250929"
    stop_reason: str = "end_turn"
    usage: MockUsage = field(default_factory=MockUsage)

    def to_llm_response(self) -> LLMResponse:
        """Convert MockResponse to LLMResponse for LLMClient compatibility."""
        content = []
        for block in self.content:
            if isinstance(block, MockTextBlock):
                content.append(LLMTextBlock(text=block.text))
            elif isinstance(block, MockToolUseBlock):
                content.append(LLMToolCall(id=block.id, name=block.name, input=block.input))
        return LLMResponse(
            content=content,
            stop_reason=self.stop_reason,
            usage=LLMUsage(
                input_tokens=self.usage.input_tokens,
                output_tokens=self.usage.output_tokens,
            ),
            model=self.model,
        )


def simple_text_response(text: str = "Here is my response.") -> MockResponse:
    """Create a mock response with simple text."""
    return MockResponse(
        content=[MockTextBlock(text=text)],
        stop_reason="end_turn",
    )


def tool_then_text_response(
    tool_name: str = "list_skills",
    tool_input: dict = None,
    text: str = "Done.",
) -> list:
    """Create a sequence of responses: tool call followed by text.

    Returns a list of MockResponse objects to be used as side_effect.
    """
    tool_response = MockResponse(
        content=[MockToolUseBlock(name=tool_name, input=tool_input or {})],
        stop_reason="tool_use",
    )
    text_response = MockResponse(
        content=[MockTextBlock(text=text)],
        stop_reason="end_turn",
    )
    return [tool_response, text_response]


def create_mock_client(responses: Optional[list] = None):
    """Create a mock anthropic.Anthropic client.

    Args:
        responses: List of MockResponse objects. If None, returns a single text response.

    Returns:
        A mock client where client.messages.create() returns the provided responses.
    """
    if responses is None:
        responses = [simple_text_response()]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses
    return mock_client


def create_mock_llm_client(responses: Optional[list] = None):
    """Create a mock LLMClient.

    Args:
        responses: List of MockResponse objects. If None, returns a single text response.
                   MockResponse objects will be automatically converted to LLMResponse.

    Returns:
        A mock LLMClient where client.create()/acreate()/acreate_stream() returns LLMResponse objects.
        All three methods share a single response queue so calls interleave correctly
        (e.g. acreate_stream → acreate for summary → acreate_stream).
    """
    from unittest.mock import AsyncMock

    if responses is None:
        responses = [simple_text_response()]

    # Convert MockResponse to LLMResponse
    llm_responses = [r.to_llm_response() if isinstance(r, MockResponse) else r for r in responses]

    # Shared call index across all methods
    call_idx = {"i": 0}

    def _next_response():
        idx = call_idx["i"]
        call_idx["i"] += 1
        return llm_responses[idx] if idx < len(llm_responses) else llm_responses[-1]

    def sync_create(*args, **kwargs):
        return _next_response()

    async def async_create(*args, **kwargs):
        return _next_response()

    def make_stream_generator(*args, **kwargs):
        """Return an async generator that yields the next response as a non-delta final."""
        resp = _next_response()

        async def _gen():
            yield resp
        return _gen()

    mock_client = MagicMock()
    mock_client.create = MagicMock(side_effect=sync_create)
    mock_client.acreate = AsyncMock(side_effect=async_create)
    mock_client.acreate_stream = MagicMock(side_effect=make_stream_generator)
    mock_client.get_context_limit.return_value = 200_000  # Default Claude context limit
    mock_client.max_output_tokens = 64000  # Default Claude max output tokens
    return mock_client
