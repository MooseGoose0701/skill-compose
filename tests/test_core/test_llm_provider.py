"""
Unit tests for LLM provider abstraction layer.

Tests:
- LLMClient initialization and configuration
- API key resolution
- Tool format conversion (Anthropic -> OpenAI)
- Message format conversion
- Response parsing
- Real LLM calls (when API keys available)
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.llm.provider import (
    LLMClient,
    LLMResponse,
    LLMUsage,
    LLMTextBlock,
    LLMToolCall,
    PROVIDER_BASE_URLS,
    PROVIDER_MAX_TOKENS,
)
from app.llm.models import SUPPORTED_MODELS, get_context_limit


class TestLLMClientInit:
    """Test LLMClient initialization."""

    def test_default_provider(self):
        """Default provider should be kimi."""
        client = LLMClient()
        assert client.provider == "kimi"
        assert client.model == "kimi-k2.5"

    def test_custom_provider(self):
        """Can specify custom provider and model."""
        client = LLMClient(provider="openai", model="gpt-4o")
        assert client.provider == "openai"
        assert client.model == "gpt-4o"

    def test_explicit_api_key(self):
        """Explicit API key takes precedence over environment."""
        client = LLMClient(provider="openai", api_key="explicit-key")
        assert client.api_key == "explicit-key"

    def test_api_key_from_env(self):
        """API key is read from .env file."""
        with patch("app.llm.provider.read_env_value", return_value="env-key"):
            client = LLMClient(provider="openai")
            assert client.api_key == "env-key"

    def test_api_key_mapping(self):
        """Each provider has correct env var mapping."""
        test_cases = [
            ("anthropic", "ANTHROPIC_API_KEY", "key1"),
            ("openai", "OPENAI_API_KEY", "key2"),
            ("google", "GOOGLE_API_KEY", "key3"),
            ("deepseek", "DEEPSEEK_API_KEY", "key4"),
            ("kimi", "MOONSHOT_API_KEY", "key5"),
        ]
        for provider, env_var, key_value in test_cases:
            def _mock_read(key, expected_var=env_var, val=key_value):
                return val if key == expected_var else ""
            with patch("app.llm.provider.read_env_value", side_effect=_mock_read):
                client = LLMClient(provider=provider)
                assert client.api_key == key_value, f"Failed for {provider}"


class TestProviderConfig:
    """Test provider-specific configuration."""

    def test_provider_base_urls(self):
        """Verify base URLs are configured correctly."""
        assert PROVIDER_BASE_URLS["openai"] is None
        assert "deepseek.com" in PROVIDER_BASE_URLS["deepseek"]
        assert "moonshot.cn" in PROVIDER_BASE_URLS["kimi"]
        assert "googleapis.com" in PROVIDER_BASE_URLS["google"]

    def test_provider_max_tokens(self):
        """Verify max tokens limits."""
        assert PROVIDER_MAX_TOKENS.get("deepseek") == 8192
        assert PROVIDER_MAX_TOKENS.get("kimi") == 8192
        # Anthropic and OpenAI don't have limits in this dict
        assert "anthropic" not in PROVIDER_MAX_TOKENS
        assert "openai" not in PROVIDER_MAX_TOKENS


class TestToolConversion:
    """Test Anthropic to OpenAI tool format conversion."""

    def test_convert_empty_tools(self):
        """Empty/None tools returns None."""
        client = LLMClient(provider="openai")
        assert client._convert_tools_to_openai(None) is None
        assert client._convert_tools_to_openai([]) is None

    def test_convert_anthropic_tool(self):
        """Convert Anthropic tool format to OpenAI format."""
        client = LLMClient(provider="openai")

        anthropic_tools = [{
            "name": "get_weather",
            "description": "Get weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        }]

        converted = client._convert_tools_to_openai(anthropic_tools)

        assert len(converted) == 1
        assert converted[0]["type"] == "function"
        assert converted[0]["function"]["name"] == "get_weather"
        assert converted[0]["function"]["description"] == "Get weather for a location"
        assert "location" in converted[0]["function"]["parameters"]["properties"]

    def test_convert_tool_empty_properties(self):
        """Tools with empty properties get additionalProperties: false."""
        client = LLMClient(provider="openai")

        anthropic_tools = [{
            "name": "no_params_tool",
            "description": "Tool with no parameters",
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }]

        converted = client._convert_tools_to_openai(anthropic_tools)
        params = converted[0]["function"]["parameters"]

        assert params["type"] == "object"
        assert params["additionalProperties"] is False

    def test_already_openai_format(self):
        """Tools already in OpenAI format pass through unchanged."""
        client = LLMClient(provider="openai")

        openai_tools = [{
            "type": "function",
            "function": {
                "name": "my_func",
                "description": "desc",
                "parameters": {"type": "object"}
            }
        }]

        converted = client._convert_tools_to_openai(openai_tools)
        assert converted == openai_tools


class TestMessageConversion:
    """Test Anthropic to OpenAI message format conversion."""

    def test_simple_messages(self):
        """Simple string messages convert correctly."""
        client = LLMClient(provider="openai")

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        converted = client._convert_messages_to_openai(messages)

        assert len(converted) == 2
        assert converted[0]["role"] == "user"
        assert converted[0]["content"] == "Hello"
        assert converted[1]["role"] == "assistant"
        assert converted[1]["content"] == "Hi there!"

    def test_system_prompt_added(self):
        """System prompt is added as first message."""
        client = LLMClient(provider="openai")

        messages = [{"role": "user", "content": "Hello"}]
        converted = client._convert_messages_to_openai(messages, system="You are helpful")

        assert len(converted) == 2
        assert converted[0]["role"] == "system"
        assert converted[0]["content"] == "You are helpful"
        assert converted[1]["role"] == "user"

    def test_tool_use_conversion(self):
        """Anthropic tool_use blocks convert to OpenAI tool_calls."""
        client = LLMClient(provider="openai")

        messages = [{
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check."},
                {
                    "type": "tool_use",
                    "id": "call_123",
                    "name": "get_weather",
                    "input": {"location": "Tokyo"}
                }
            ]
        }]

        converted = client._convert_messages_to_openai(messages)

        assert len(converted) == 1
        msg = converted[0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Let me check."
        assert len(msg["tool_calls"]) == 1
        assert msg["tool_calls"][0]["id"] == "call_123"
        assert msg["tool_calls"][0]["function"]["name"] == "get_weather"

    def test_tool_result_conversion(self):
        """Anthropic tool_result blocks convert to OpenAI tool messages."""
        client = LLMClient(provider="openai")

        messages = [{
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "call_123",
                "content": "Sunny, 25C"
            }]
        }]

        converted = client._convert_messages_to_openai(messages)

        assert len(converted) == 1
        msg = converted[0]
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_123"
        assert msg["content"] == "Sunny, 25C"


class TestResponseParsing:
    """Test response parsing from different providers."""

    def test_parse_openai_text_response(self):
        """Parse OpenAI response with text content."""
        client = LLMClient(provider="openai")

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "gpt-4o"

        result = client._parse_openai_response(mock_response)

        assert isinstance(result, LLMResponse)
        assert result.text_content == "Hello world"
        assert result.stop_reason == "end_turn"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 5

    def test_parse_openai_tool_call_response(self):
        """Parse OpenAI response with tool calls."""
        client = LLMClient(provider="openai")

        mock_tool_call = Mock()
        mock_tool_call.id = "call_abc"
        mock_tool_call.function.name = "get_time"
        mock_tool_call.function.arguments = '{"timezone": "UTC"}'

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 15
        mock_response.model = "gpt-4o"

        result = client._parse_openai_response(mock_response)

        assert result.stop_reason == "tool_use"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_time"
        assert result.tool_calls[0].input == {"timezone": "UTC"}


class TestContextLimit:
    """Test context limit retrieval."""

    def test_get_context_limit_known_model(self):
        """Get context limit for known models."""
        assert get_context_limit("anthropic", "claude-sonnet-4-5-20250929") == 200000
        assert get_context_limit("openai", "gpt-4o") == 128000
        assert get_context_limit("google", "gemini-2.0-flash") == 1000000
        assert get_context_limit("deepseek", "deepseek-chat") == 64000
        assert get_context_limit("kimi", "kimi-k2.5") == 256000

    def test_get_context_limit_unknown_model(self):
        """Unknown models return default limit."""
        limit = get_context_limit("unknown", "unknown-model")
        assert limit == 200000  # DEFAULT_CONTEXT_LIMIT


class TestSupportedModels:
    """Test model registry."""

    def test_all_providers_have_models(self):
        """Each supported provider has at least one model."""
        providers = set()
        for info in SUPPORTED_MODELS.values():
            providers.add(info["provider"])

        expected = {"anthropic", "openai", "google", "deepseek", "kimi", "openrouter"}
        assert providers == expected

    def test_model_info_structure(self):
        """All models have required fields."""
        required_fields = ["provider", "model_id", "display_name", "context_limit", "supports_tools", "supports_vision"]

        for key, info in SUPPORTED_MODELS.items():
            for field in required_fields:
                assert field in info, f"Missing {field} in {key}"

    def test_kimi_model_config(self):
        """Verify Kimi K2.5 model configuration."""
        kimi_key = "kimi/kimi-k2.5"
        assert kimi_key in SUPPORTED_MODELS
        info = SUPPORTED_MODELS[kimi_key]
        assert info["provider"] == "kimi"
        assert info["model_id"] == "kimi-k2.5"
        assert info["context_limit"] == 256000
        assert info["supports_tools"] is True


# =============================================================================
# Real LLM Integration Tests (require API keys)
# =============================================================================

def _get_real_api_key(provider: str) -> str:
    """Get real API key from environment for integration tests."""
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
    }
    env_var = key_map.get(provider, "")
    key = os.environ.get(env_var, "")
    # Skip if key looks like a test placeholder
    if key.startswith("test-") or key.startswith("sk-test") or not key:
        return ""
    return key


@pytest.mark.integration
class TestRealLLMCalls:
    """
    Integration tests that call real LLM APIs.

    Run with: pytest tests/test_core/test_llm_provider.py -m integration -v

    Requires real API keys in environment variables.
    """

    @pytest.mark.skipif(not _get_real_api_key("kimi"), reason="No Kimi API key")
    def test_kimi_k2_5(self):
        """Test real call to Kimi K2.5."""
        client = LLMClient(
            provider="kimi",
            model="kimi-k2.5",
            api_key=_get_real_api_key("kimi"),
        )

        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        )

        assert "hello" in response.text_content.strip().lower()
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0

    @pytest.mark.skipif(not _get_real_api_key("openai"), reason="No OpenAI API key")
    def test_openai_gpt4o(self):
        """Test real call to GPT-4o."""
        client = LLMClient(
            provider="openai",
            model="gpt-4o",
            api_key=_get_real_api_key("openai"),
        )

        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        )

        assert "hello" in response.text_content.strip().lower()
        assert response.usage.input_tokens > 0

    @pytest.mark.skipif(not _get_real_api_key("openai"), reason="No OpenAI API key")
    def test_openai_gpt4o_mini(self):
        """Test real call to GPT-4o-mini."""
        client = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=_get_real_api_key("openai"),
        )

        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        )

        assert "hello" in response.text_content.strip().lower()

    @pytest.mark.skipif(not _get_real_api_key("google"), reason="No Google API key")
    def test_google_gemini_flash(self):
        """Test real call to Gemini 2.0 Flash."""
        client = LLMClient(
            provider="google",
            model="gemini-2.0-flash",
            api_key=_get_real_api_key("google"),
        )

        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        )

        assert "hello" in response.text_content.strip().lower()

    @pytest.mark.skipif(not _get_real_api_key("deepseek"), reason="No DeepSeek API key")
    def test_deepseek_chat(self):
        """Test real call to DeepSeek Chat."""
        client = LLMClient(
            provider="deepseek",
            model="deepseek-chat",
            api_key=_get_real_api_key("deepseek"),
        )

        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        )

        assert "hello" in response.text_content.strip().lower()

    @pytest.mark.skipif(not _get_real_api_key("deepseek"), reason="No DeepSeek API key")
    def test_deepseek_reasoner(self):
        """Test real call to DeepSeek Reasoner."""
        client = LLMClient(
            provider="deepseek",
            model="deepseek-reasoner",
            api_key=_get_real_api_key("deepseek"),
        )

        # Reasoner model needs more tokens for "thinking" before output
        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=1024,
        )

        assert "hello" in response.text_content.strip().lower()

    @pytest.mark.skipif(not _get_real_api_key("kimi"), reason="No Kimi/Moonshot API key")
    def test_kimi_k25(self):
        """Test real call to Kimi K2.5."""
        client = LLMClient(
            provider="kimi",
            model="kimi-k2.5",
            api_key=_get_real_api_key("kimi"),
        )

        # Kimi K2.5 may need more tokens for reasoning
        response = client.create(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=1024,
        )

        assert "hello" in response.text_content.strip().lower()

    @pytest.mark.skipif(not _get_real_api_key("openai"), reason="No OpenAI API key")
    def test_tool_calling_openai(self):
        """Test tool calling with OpenAI."""
        client = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=_get_real_api_key("openai"),
        )

        tools = [{
            "name": "get_current_time",
            "description": "Get the current time",
            "input_schema": {
                "type": "object",
                "properties": {},
            }
        }]

        response = client.create(
            messages=[{"role": "user", "content": "What time is it now? Use the get_current_time tool."}],
            tools=tools,
            max_tokens=100,
        )

        # Should trigger tool use
        assert len(response.tool_calls) > 0 or "time" in response.text_content.lower()

    @pytest.mark.skipif(not _get_real_api_key("kimi"), reason="No Kimi API key")
    def test_tool_calling_kimi(self):
        """Test tool calling with Kimi."""
        client = LLMClient(
            provider="kimi",
            model="kimi-k2.5",
            api_key=_get_real_api_key("kimi"),
        )

        tools = [{
            "name": "get_current_time",
            "description": "Get the current time",
            "input_schema": {
                "type": "object",
                "properties": {},
            }
        }]

        response = client.create(
            messages=[{"role": "user", "content": "What time is it now? Use the get_current_time tool."}],
            tools=tools,
            max_tokens=100,
        )

        # Should trigger tool use
        assert len(response.tool_calls) > 0


@pytest.mark.integration
class TestRealLLMStreaming:
    """Test streaming with real LLM APIs."""

    @pytest.mark.skipif(not _get_real_api_key("openai"), reason="No OpenAI API key")
    def test_streaming_openai(self):
        """Test streaming with OpenAI."""
        client = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=_get_real_api_key("openai"),
        )

        responses = list(client.create_stream(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        ))

        assert len(responses) > 0
        final = responses[-1]
        assert "hello" in final.text_content.strip().lower()

    @pytest.mark.skipif(not _get_real_api_key("kimi"), reason="No Kimi API key")
    def test_streaming_kimi(self):
        """Test streaming with Kimi."""
        client = LLMClient(
            provider="kimi",
            model="kimi-k2.5",
            api_key=_get_real_api_key("kimi"),
        )

        responses = list(client.create_stream(
            messages=[{"role": "user", "content": "Say 'hello' in one word only."}],
            max_tokens=50,
        ))

        assert len(responses) > 0
        final = responses[-1]
        assert "hello" in final.text_content.strip().lower()
