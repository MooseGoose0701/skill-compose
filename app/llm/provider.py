"""
Unified LLM client using native SDKs for multi-provider support.

Supports:
- Anthropic (Claude) - via anthropic SDK
- OpenAI (GPT-4o) - via openai SDK
- Google (Gemini) - via openai SDK (OpenAI-compatible endpoint)
- DeepSeek - via openai SDK (OpenAI-compatible endpoint)
- Kimi (Moonshot) - via openai SDK (OpenAI-compatible endpoint)
- OpenRouter - via openai SDK (OpenAI-compatible endpoint, access to 200+ models)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional

from app.config import read_env_value
from app.llm.models import get_context_limit


# Provider base URLs for OpenAI-compatible APIs
PROVIDER_BASE_URLS = {
    "openai": None,  # Use default
    "deepseek": "https://api.deepseek.com",
    "kimi": "https://api.moonshot.cn/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
}

# Max tokens limits by provider
PROVIDER_MAX_TOKENS = {
    "deepseek": 8192,
    "kimi": 8192,
}


@dataclass
class LLMUsage:
    """Token usage information."""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMToolCall:
    """Tool call from LLM response."""
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class LLMTextBlock:
    """Text content block."""
    text: str


@dataclass
class LLMResponse:
    """Unified response from LLM."""
    content: List[Any] = field(default_factory=list)  # List of LLMTextBlock or LLMToolCall
    stop_reason: str = "end_turn"
    usage: LLMUsage = field(default_factory=LLMUsage)
    model: str = ""
    is_delta: bool = False  # True for incremental text chunks during streaming

    @property
    def text_content(self) -> str:
        """Get concatenated text content."""
        texts = []
        for block in self.content:
            if isinstance(block, LLMTextBlock):
                texts.append(block.text)
        return "".join(texts)

    @property
    def tool_calls(self) -> List[LLMToolCall]:
        """Get all tool calls."""
        return [b for b in self.content if isinstance(b, LLMToolCall)]


# Provider name → environment variable name for the API key
PROVIDER_API_KEY_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class LLMClient:
    """
    Unified LLM client using native SDKs.

    - Anthropic: uses anthropic SDK
    - OpenAI/DeepSeek/Kimi/Google: uses openai SDK with custom base_url
    """

    def __init__(
        self,
        provider: str = "kimi",
        model: str = "kimi-k2.5",
        api_key: Optional[str] = None,
    ):
        """
        Initialize the LLM client.

        Args:
            provider: The LLM provider (anthropic, openai, google, deepseek, kimi)
            model: The model name/ID
            api_key: Optional API key (will use environment variable if not provided)
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key or self._get_api_key(provider)
        self._client = None
        self._async_client = None

    def _get_api_key(self, provider: str) -> str:
        """Get API key from .env file directly.

        Always reads from .env on disk so that all uvicorn workers
        see keys set via the Settings UI (multi-worker safe).
        """
        env_var = PROVIDER_API_KEY_MAP.get(provider, f"{provider.upper()}_API_KEY")
        return read_env_value(env_var)

    def _get_openai_client(self):
        """Get or create OpenAI client for OpenAI-compatible providers."""
        if self._client is None:
            from openai import OpenAI
            import httpx
            base_url = PROVIDER_BASE_URLS.get(self.provider)

            # Generous timeout for long streaming responses
            timeout = httpx.Timeout(600.0, connect=10.0)

            # OpenRouter requires/recommends additional headers
            if self.provider == "openrouter":
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                    default_headers={
                        "HTTP-Referer": "https://github.com/skill-compose",
                        "X-Title": "Skill Compose",
                    },
                )
            else:
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                )
        return self._client

    def _get_anthropic_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _get_async_openai_client(self):
        """Get or create async OpenAI client for OpenAI-compatible providers."""
        if self._async_client is None:
            from openai import AsyncOpenAI
            import httpx
            base_url = PROVIDER_BASE_URLS.get(self.provider)
            timeout = httpx.Timeout(600.0, connect=10.0)

            if self.provider == "openrouter":
                self._async_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                    default_headers={
                        "HTTP-Referer": "https://github.com/skill-compose",
                        "X-Title": "Skill Compose",
                    },
                )
            else:
                self._async_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                )
        return self._async_client

    def _get_async_anthropic_client(self):
        """Get or create async Anthropic client."""
        if self._async_client is None:
            import anthropic
            self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._async_client

    def get_context_limit(self) -> int:
        """Get the context window limit for the current model."""
        return get_context_limit(self.provider, self.model)

    def _convert_tools_to_openai(self, tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
        """
        Convert Anthropic-style tools to OpenAI format.

        Anthropic format:
        {
            "name": "tool_name",
            "description": "...",
            "input_schema": {...}
        }

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "...",
                "parameters": {...}
            }
        }
        """
        if not tools:
            return None

        converted = []
        for tool in tools:
            if "function" in tool:
                # Already in OpenAI format
                converted.append(tool)
            else:
                # Convert from Anthropic format
                input_schema = tool.get("input_schema", {})

                # Fix for OpenAI: if properties is empty, add additionalProperties: false
                if input_schema.get("type") == "object":
                    props = input_schema.get("properties", {})
                    if not props:
                        input_schema = {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        }

                converted.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": input_schema,
                    }
                })
        return converted

    def _convert_messages_to_openai(
        self,
        messages: List[Dict],
        system: Optional[str] = None
    ) -> List[Dict]:
        """
        Convert Anthropic-style messages to OpenAI format.

        Handles:
        - Adding system message as first message
        - Converting tool_result blocks to tool responses
        - Converting tool_use blocks to assistant tool calls
        """
        result = []

        # Add system message if provided
        if system:
            result.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")

            if isinstance(content, str):
                result.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Handle complex content blocks (Anthropic format)
                text_parts = []
                image_parts = []
                tool_calls = []
                tool_results = []

                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")

                        if block_type == "text":
                            text_parts.append(block.get("text", ""))

                        elif block_type == "image":
                            # Anthropic image block → OpenAI image_url
                            source = block.get("source", {})
                            media_type = source.get("media_type", "image/png")
                            data = source.get("data", "")
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{data}"}
                            })

                        elif block_type == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {}))
                                }
                            })

                        elif block_type == "tool_result":
                            tool_results.append({
                                "tool_call_id": block.get("tool_use_id", ""),
                                "content": block.get("content", ""),
                            })

                    elif isinstance(block, str):
                        text_parts.append(block)

                # Build the message based on what we found
                if role == "assistant":
                    msg_content = "\n".join(text_parts) if text_parts else None
                    if tool_calls:
                        result.append({
                            "role": "assistant",
                            "content": msg_content,
                            "tool_calls": tool_calls,
                        })
                    elif msg_content:
                        result.append({"role": "assistant", "content": msg_content})

                elif tool_results:
                    for tr in tool_results:
                        result.append({
                            "role": "tool",
                            "tool_call_id": tr["tool_call_id"],
                            "content": tr["content"],
                        })

                elif image_parts:
                    # User message with images: use multipart content format
                    openai_content = []
                    openai_content.extend(image_parts)
                    if text_parts:
                        openai_content.append({"type": "text", "text": "\n".join(text_parts)})
                    result.append({"role": "user", "content": openai_content})

                else:
                    combined_text = "\n".join(text_parts) if text_parts else ""
                    if combined_text:
                        result.append({"role": "user", "content": combined_text})

            else:
                result.append({"role": role, "content": str(content)})

        return result

    def _parse_openai_response(self, response) -> LLMResponse:
        """Parse OpenAI response into unified format."""
        content = []
        stop_reason = "end_turn"

        if response.choices:
            choice = response.choices[0]
            message = choice.message

            if message.content:
                content.append(LLMTextBlock(text=message.content))

            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except:
                        args = {}

                    content.append(LLMToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        input=args,
                    ))

            finish_reason = choice.finish_reason
            if finish_reason == "stop":
                stop_reason = "end_turn"
            elif finish_reason == "tool_calls":
                stop_reason = "tool_use"
            elif finish_reason == "length":
                stop_reason = "max_tokens"
            else:
                stop_reason = finish_reason or "end_turn"

        usage = LLMUsage()
        if response.usage:
            usage.input_tokens = response.usage.prompt_tokens or 0
            usage.output_tokens = response.usage.completion_tokens or 0

        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
            model=response.model or self.model,
        )

    def _parse_anthropic_response(self, response) -> LLMResponse:
        """Parse Anthropic response into unified format."""
        content = []

        for block in response.content:
            if block.type == "text":
                content.append(LLMTextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(LLMToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        usage = LLMUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            stop_reason=response.stop_reason,
            usage=usage,
            model=response.model,
        )

    def create(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 16384,
    ) -> LLMResponse:
        """
        Create a completion (synchronous).

        Args:
            messages: List of messages in Anthropic format
            system: Optional system prompt
            tools: Optional list of tools in Anthropic format
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content, stop_reason, and usage
        """
        # Adjust max_tokens based on provider limits
        provider_limit = PROVIDER_MAX_TOKENS.get(self.provider)
        if provider_limit:
            max_tokens = min(max_tokens, provider_limit)

        if self.provider == "anthropic":
            return self._create_anthropic(messages, system, tools, max_tokens)
        else:
            return self._create_openai_compatible(messages, system, tools, max_tokens)

    def _create_anthropic(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> LLMResponse:
        """Create completion using Anthropic SDK."""
        client = self._get_anthropic_client()

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = tools

        response = client.messages.create(**kwargs)
        return self._parse_anthropic_response(response)

    def _create_openai_compatible(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> LLMResponse:
        """Create completion using OpenAI SDK (for OpenAI-compatible providers)."""
        client = self._get_openai_client()

        converted_messages = self._convert_messages_to_openai(messages, system)
        converted_tools = self._convert_tools_to_openai(tools)

        kwargs = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
        }

        if converted_tools:
            kwargs["tools"] = converted_tools

        # Kimi K2.5: Disable thinking mode for tool calls to avoid reasoning_content requirement
        if self.provider == "kimi":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        response = client.chat.completions.create(**kwargs)
        return self._parse_openai_response(response)

    def create_stream(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 16384,
    ) -> Generator[LLMResponse, None, None]:
        """
        Create a streaming completion.

        Args:
            messages: List of messages in Anthropic format
            system: Optional system prompt
            tools: Optional list of tools in Anthropic format
            max_tokens: Maximum tokens to generate

        Yields:
            LLMResponse objects for each chunk
        """
        # Adjust max_tokens based on provider limits
        provider_limit = PROVIDER_MAX_TOKENS.get(self.provider)
        if provider_limit:
            max_tokens = min(max_tokens, provider_limit)

        if self.provider == "anthropic":
            yield from self._create_stream_anthropic(messages, system, tools, max_tokens)
        else:
            yield from self._create_stream_openai_compatible(messages, system, tools, max_tokens)

    def _create_stream_anthropic(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> Generator[LLMResponse, None, None]:
        """Create streaming completion using Anthropic SDK."""
        client = self._get_anthropic_client()

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = tools

        with client.messages.stream(**kwargs) as stream:
            # Yield text deltas as they arrive
            for text in stream.text_stream:
                if text:
                    yield LLMResponse(
                        content=[LLMTextBlock(text=text)],
                        is_delta=True,
                        model=self.model,
                    )

            # Yield final complete response
            response = stream.get_final_message()

        yield self._parse_anthropic_response(response)

    def _create_stream_openai_compatible(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> Generator[LLMResponse, None, None]:
        """Create streaming completion using OpenAI SDK."""
        client = self._get_openai_client()

        converted_messages = self._convert_messages_to_openai(messages, system)
        converted_tools = self._convert_tools_to_openai(tools)

        kwargs = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if converted_tools:
            kwargs["tools"] = converted_tools

        # Kimi K2.5: Disable thinking mode for tool calls to avoid reasoning_content requirement
        if self.provider == "kimi":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        response = client.chat.completions.create(**kwargs)

        # Accumulate streaming content
        accumulated_text = ""
        accumulated_tool_calls = {}
        usage = LLMUsage()
        stop_reason = "end_turn"

        for chunk in response:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    accumulated_text += delta.content
                    # Yield text delta immediately
                    yield LLMResponse(
                        content=[LLMTextBlock(text=delta.content)],
                        is_delta=True,
                        model=self.model,
                    )

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    if choice.finish_reason == "stop":
                        stop_reason = "end_turn"
                    elif choice.finish_reason == "tool_calls":
                        stop_reason = "tool_use"
                    elif choice.finish_reason == "length":
                        stop_reason = "max_tokens"
                    else:
                        stop_reason = choice.finish_reason

            if chunk.usage:
                usage.input_tokens = chunk.usage.prompt_tokens or 0
                usage.output_tokens = chunk.usage.completion_tokens or 0

        # Build final content
        content = []
        if accumulated_text:
            content.append(LLMTextBlock(text=accumulated_text))

        for tc_data in accumulated_tool_calls.values():
            try:
                args = json.loads(tc_data["arguments"])
            except:
                args = {}

            content.append(LLMToolCall(
                id=tc_data["id"],
                name=tc_data["name"],
                input=args,
            ))

        yield LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
            model=self.model,
        )

    # ============ Async Methods ============

    async def acreate(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 16384,
    ) -> LLMResponse:
        """Async version of create(). Same interface, uses async SDK clients."""
        provider_limit = PROVIDER_MAX_TOKENS.get(self.provider)
        if provider_limit:
            max_tokens = min(max_tokens, provider_limit)

        if self.provider == "anthropic":
            return await self._acreate_anthropic(messages, system, tools, max_tokens)
        else:
            return await self._acreate_openai_compatible(messages, system, tools, max_tokens)

    async def _acreate_anthropic(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> LLMResponse:
        """Async completion using Anthropic SDK."""
        client = self._get_async_anthropic_client()
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = await client.messages.create(**kwargs)
        return self._parse_anthropic_response(response)

    async def _acreate_openai_compatible(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> LLMResponse:
        """Async completion using OpenAI SDK."""
        client = self._get_async_openai_client()
        converted_messages = self._convert_messages_to_openai(messages, system)
        converted_tools = self._convert_tools_to_openai(tools)

        kwargs = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
        }
        if converted_tools:
            kwargs["tools"] = converted_tools
        if self.provider == "kimi":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        response = await client.chat.completions.create(**kwargs)
        return self._parse_openai_response(response)

    async def acreate_stream(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 16384,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Async version of create_stream(). Yields LLMResponse deltas, then final response."""
        provider_limit = PROVIDER_MAX_TOKENS.get(self.provider)
        if provider_limit:
            max_tokens = min(max_tokens, provider_limit)

        if self.provider == "anthropic":
            async for resp in self._acreate_stream_anthropic(messages, system, tools, max_tokens):
                yield resp
        else:
            async for resp in self._acreate_stream_openai_compatible(messages, system, tools, max_tokens):
                yield resp

    async def _acreate_stream_anthropic(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Async streaming using Anthropic SDK."""
        client = self._get_async_anthropic_client()
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield LLMResponse(
                        content=[LLMTextBlock(text=text)],
                        is_delta=True,
                        model=self.model,
                    )
            response = await stream.get_final_message()

        yield self._parse_anthropic_response(response)

    async def _acreate_stream_openai_compatible(
        self,
        messages: List[Dict],
        system: Optional[str],
        tools: Optional[List[Dict]],
        max_tokens: int,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Async streaming using OpenAI SDK."""
        client = self._get_async_openai_client()
        converted_messages = self._convert_messages_to_openai(messages, system)
        converted_tools = self._convert_tools_to_openai(tools)

        kwargs = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if converted_tools:
            kwargs["tools"] = converted_tools
        if self.provider == "kimi":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        response = await client.chat.completions.create(**kwargs)

        accumulated_text = ""
        accumulated_tool_calls = {}
        usage = LLMUsage()
        stop_reason = "end_turn"

        async for chunk in response:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    accumulated_text += delta.content
                    yield LLMResponse(
                        content=[LLMTextBlock(text=delta.content)],
                        is_delta=True,
                        model=self.model,
                    )

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    if choice.finish_reason == "stop":
                        stop_reason = "end_turn"
                    elif choice.finish_reason == "tool_calls":
                        stop_reason = "tool_use"
                    elif choice.finish_reason == "length":
                        stop_reason = "max_tokens"
                    else:
                        stop_reason = choice.finish_reason

            if chunk.usage:
                usage.input_tokens = chunk.usage.prompt_tokens or 0
                usage.output_tokens = chunk.usage.completion_tokens or 0

        content = []
        if accumulated_text:
            content.append(LLMTextBlock(text=accumulated_text))

        for tc_data in accumulated_tool_calls.values():
            try:
                args = json.loads(tc_data["arguments"])
            except:
                args = {}
            content.append(LLMToolCall(
                id=tc_data["id"],
                name=tc_data["name"],
                input=args,
            ))

        yield LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
            model=self.model,
        )
