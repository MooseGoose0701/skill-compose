"""
Model registry with capabilities and context limits for all supported LLM providers.
"""

from typing import Dict, List, Optional, TypedDict


class ModelInfo(TypedDict):
    """Model information."""
    provider: str
    model_id: str  # The ID used by the provider's API
    display_name: str
    context_limit: int
    max_output_tokens: int  # Maximum output tokens the model supports
    supports_tools: bool
    supports_vision: bool


# Supported models by provider
# Format: "provider/model" -> ModelInfo
SUPPORTED_MODELS: Dict[str, ModelInfo] = {
    # Anthropic models (direct API)
    "anthropic/claude-sonnet-4-5-20250929": {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-5-20250929",
        "display_name": "Claude Sonnet 4.5",
        "context_limit": 200000,
        "max_output_tokens": 64000,
        "supports_tools": True,
        "supports_vision": True,
    },
    "anthropic/claude-opus-4-6": {
        "provider": "anthropic",
        "model_id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6",
        "context_limit": 200000,
        "max_output_tokens": 128000,
        "supports_tools": True,
        "supports_vision": True,
    },
    # OpenAI direct models
    "openai/gpt-4o": {
        "provider": "openai",
        "model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "context_limit": 128000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
    },
    "openai/gpt-4o-mini": {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "context_limit": 128000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
    },
    # Google Gemini direct models
    "google/gemini-2.0-flash": {
        "provider": "google",
        "model_id": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "context_limit": 1000000,
        "max_output_tokens": 8192,
        "supports_tools": True,
        "supports_vision": True,
    },
    # DeepSeek direct models
    "deepseek/deepseek-chat": {
        "provider": "deepseek",
        "model_id": "deepseek-chat",
        "display_name": "DeepSeek Chat",
        "context_limit": 64000,
        "max_output_tokens": 8192,
        "supports_tools": True,
        "supports_vision": False,
    },
    "deepseek/deepseek-reasoner": {
        "provider": "deepseek",
        "model_id": "deepseek-reasoner",
        "display_name": "DeepSeek Reasoner",
        "context_limit": 64000,
        "max_output_tokens": 8192,
        "supports_tools": True,
        "supports_vision": False,
    },
    # Kimi (Moonshot AI) models
    "kimi/kimi-k2.5": {
        "provider": "kimi",
        "model_id": "kimi-k2.5",
        "display_name": "Kimi K2.5",
        "context_limit": 256000,
        "max_output_tokens": 65535,
        "supports_tools": True,
        "supports_vision": True,
    },
    # OpenRouter models (access 200+ models via single API)
    # Claude via OpenRouter
    "openrouter/anthropic/claude-sonnet-4.5": {
        "provider": "openrouter",
        "model_id": "anthropic/claude-sonnet-4.5",
        "display_name": "Claude Sonnet 4.5",
        "context_limit": 200000,
        "max_output_tokens": 64000,
        "supports_tools": True,
        "supports_vision": True,
    },
    "openrouter/anthropic/claude-opus-4.6": {
        "provider": "openrouter",
        "model_id": "anthropic/claude-opus-4.6",
        "display_name": "Claude Opus 4.6",
        "context_limit": 200000,
        "max_output_tokens": 128000,
        "supports_tools": True,
        "supports_vision": True,
    },
    # DeepSeek via OpenRouter
    "openrouter/deepseek/deepseek-chat-v3-0324": {
        "provider": "openrouter",
        "model_id": "deepseek/deepseek-chat-v3-0324",
        "display_name": "DeepSeek V3.2",
        "context_limit": 64000,
        "max_output_tokens": 65536,
        "supports_tools": True,
        "supports_vision": False,
    },
    # Kimi via OpenRouter
    "openrouter/moonshotai/kimi-k2.5": {
        "provider": "openrouter",
        "model_id": "moonshotai/kimi-k2.5",
        "display_name": "Kimi K2.5",
        "context_limit": 256000,
        "max_output_tokens": 65535,
        "supports_tools": True,
        "supports_vision": True,
    },
    # Gemini via OpenRouter
    "openrouter/google/gemini-3-flash-preview": {
        "provider": "openrouter",
        "model_id": "google/gemini-3-flash-preview",
        "display_name": "Gemini 3 Flash Preview",
        "context_limit": 1000000,
        "max_output_tokens": 65535,
        "supports_tools": True,
        "supports_vision": True,
    },
    "openrouter/google/gemini-2.5-flash": {
        "provider": "openrouter",
        "model_id": "google/gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "context_limit": 1000000,
        "max_output_tokens": 65535,
        "supports_tools": True,
        "supports_vision": True,
    },
    "openrouter/google/gemini-2.5-flash-lite": {
        "provider": "openrouter",
        "model_id": "google/gemini-2.5-flash-lite",
        "display_name": "Gemini 2.5 Flash Lite",
        "context_limit": 1000000,
        "max_output_tokens": 65535,
        "supports_tools": True,
        "supports_vision": True,
    },
    # MiniMax via OpenRouter
    "openrouter/minimax/minimax-m2.1": {
        "provider": "openrouter",
        "model_id": "minimax/minimax-m2.1",
        "display_name": "MiniMax M2.1",
        "context_limit": 1000000,
        "max_output_tokens": 65535,
        "supports_tools": True,
        "supports_vision": True,
    },
    # Grok via OpenRouter
    "openrouter/x-ai/grok-code-fast-1": {
        "provider": "openrouter",
        "model_id": "x-ai/grok-code-fast-1",
        "display_name": "Grok Code Fast 1",
        "context_limit": 131072,
        "max_output_tokens": 131072,
        "supports_tools": True,
        "supports_vision": False,
    },
    "openrouter/x-ai/grok-4.1-fast": {
        "provider": "openrouter",
        "model_id": "x-ai/grok-4.1-fast",
        "display_name": "Grok 4.1 Fast",
        "context_limit": 131072,
        "max_output_tokens": 131072,
        "supports_tools": True,
        "supports_vision": True,
    },
}

# Context limits by model (for backward compatibility)
MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    info["model_id"]: info["context_limit"]
    for info in SUPPORTED_MODELS.values()
}

# Also add legacy model names for backward compatibility
MODEL_CONTEXT_LIMITS.update({
    "claude-sonnet-4-5-20250929": 200000,
    "claude-opus-4-6": 200000,
})

DEFAULT_CONTEXT_LIMIT = 200000

# Max output tokens by model_id (for backward compatibility)
MODEL_MAX_OUTPUT_TOKENS: Dict[str, int] = {
    info["model_id"]: info["max_output_tokens"]
    for info in SUPPORTED_MODELS.values()
}

DEFAULT_MAX_OUTPUT_TOKENS = 16384


def get_model_info(model_key: str) -> Optional[ModelInfo]:
    """Get model info by full key (provider/model)."""
    return SUPPORTED_MODELS.get(model_key)


def get_provider_models(provider: str) -> List[Dict]:
    """Get all models for a specific provider."""
    models = []
    for key, info in SUPPORTED_MODELS.items():
        if info["provider"] == provider:
            models.append({
                "key": key,
                **info,
            })
    return models


def get_all_providers() -> List[str]:
    """Get list of all supported providers."""
    providers = set()
    for info in SUPPORTED_MODELS.values():
        providers.add(info["provider"])
    return sorted(providers)


def get_context_limit(provider: str, model_name: str) -> int:
    """Get context limit for a model."""
    # Try full key first
    full_key = f"{provider}/{model_name}"
    if full_key in SUPPORTED_MODELS:
        return SUPPORTED_MODELS[full_key]["context_limit"]

    # Try model_id match
    if model_name in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[model_name]

    return DEFAULT_CONTEXT_LIMIT


def get_max_output_tokens(provider: str, model_name: str) -> int:
    """Get max output tokens for a model."""
    # Try full key first
    full_key = f"{provider}/{model_name}"
    if full_key in SUPPORTED_MODELS:
        return SUPPORTED_MODELS[full_key]["max_output_tokens"]

    # Try model_id match
    if model_name in MODEL_MAX_OUTPUT_TOKENS:
        return MODEL_MAX_OUTPUT_TOKENS[model_name]

    return DEFAULT_MAX_OUTPUT_TOKENS


def supports_vision(provider: str, model_name: str) -> bool:
    """Check if a model supports vision/image input.

    Returns True for models with known vision support, and True by default
    for unknown models (optimistic — most modern models support vision).
    """
    # Try full key first
    full_key = f"{provider}/{model_name}"
    if full_key in SUPPORTED_MODELS:
        return SUPPORTED_MODELS[full_key]["supports_vision"]

    # Try matching by model_id across all entries
    for info in SUPPORTED_MODELS.values():
        if info["model_id"] == model_name:
            return info["supports_vision"]

    # Unknown model — optimistically assume vision support
    return True
