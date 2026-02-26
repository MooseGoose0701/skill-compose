"""
Executor configuration loader.

Reads executor definitions from config/executors.json,
providing a single source of truth for executor names, URLs, and metadata.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache loaded config
_executor_configs: Optional[Dict] = None


def _get_config_path() -> Path:
    """Get path to executors.json config file."""
    from app.config import settings
    return Path(settings.config_dir) / "executors.json"


def load_executor_configs() -> Dict[str, dict]:
    """
    Load executor configurations from config/executors.json.

    Returns:
        Dict mapping executor name to its config dict.
        Falls back to hardcoded defaults if the file is missing or invalid.
    """
    global _executor_configs
    if _executor_configs is not None:
        return _executor_configs

    config_path = _get_config_path()
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                data = json.load(f)
            _executor_configs = data.get("executors", {})
            logger.info(f"Loaded {len(_executor_configs)} executor configs from {config_path}")
            return _executor_configs
    except Exception as e:
        logger.warning(f"Failed to load {config_path}: {e}, using defaults")

    # Fallback defaults
    _executor_configs = {
        "base": {
            "description": "Python 3.11 basic environment with common utilities",
            "image": "skillcompose/executor-base:latest",
            "url": "http://executor-base:62680",
            "memory_limit": "2G",
            "gpu_required": False,
        },
        "chemscout": {
            "description": "Chemistry and cheminformatics environment with RDKit, BioPython, PubChemPy",
            "image": "skillcompose/executor-chemscout:latest",
            "url": "http://executor-chemscout:62680",
            "memory_limit": "4G",
            "gpu_required": False,
        },
        "remotion": {
            "description": "Video rendering environment with Node.js 20, Chromium, ffmpeg, yt-dlp for Remotion",
            "image": "skillcompose/executor-remotion:latest",
            "url": "http://executor-remotion:62680",
            "memory_limit": "4G",
            "gpu_required": False,
        },
    }
    return _executor_configs


def get_executor_url(name: str) -> str:
    """
    Get URL for an executor by name.

    Resolution order:
    1. Environment variable EXECUTOR_{NAME}_URL (NAME uppercased, hyphens → underscores)
    2. 'url' field in config/executors.json
    3. Fallback pattern: http://skills-executor-{name}:62680
    """
    env_key = f"EXECUTOR_{name.upper().replace('-', '_')}_URL"
    env_url = os.environ.get(env_key)
    if env_url:
        return env_url

    configs = load_executor_configs()
    if name in configs and "url" in configs[name]:
        return configs[name]["url"]

    return f"http://skills-executor-{name}:62680"


def get_all_executor_names() -> List[str]:
    """Return list of all configured executor names."""
    return list(load_executor_configs().keys())


def get_builtin_executor_defs() -> List[dict]:
    """
    Return executor definitions for ensure_builtin_executors().

    Each dict has: name, description, image, memory_limit, gpu_required.
    """
    configs = load_executor_configs()
    result = []
    for name, cfg in configs.items():
        result.append({
            "name": name,
            "description": cfg.get("description", ""),
            "image": cfg.get("image", f"skillcompose/executor-{name}:latest"),
            "memory_limit": cfg.get("memory_limit", "2G"),
            "gpu_required": cfg.get("gpu_required", False),
        })
    return result


def reload_executor_configs():
    """Force reload of executor configs (e.g., after config file change)."""
    global _executor_configs
    _executor_configs = None
    return load_executor_configs()
