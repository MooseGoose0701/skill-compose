"""
Skill Configuration - Manage skill environment variables and secrets

Configuration is loaded from config/skills.json in the project directory.
API keys can be configured via:
1. config/skill-secrets.json (UI-managed, gitignored)
2. Environment variables (fallback)
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings

_settings = get_settings()


def _get_config_path() -> Path:
    """Get the skills config file path."""
    return Path(_settings.config_dir) / "skills.json"


def _get_secrets_path() -> Path:
    """Get the skill secrets file path."""
    return Path(_settings.config_dir) / "skill-secrets.json"


def _load_config() -> Dict[str, Any]:
    """
    Load skill configuration from config/skills.json.

    Returns:
        Dict with skills configuration.
    """
    config_path = _get_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"skills": {}}


def _save_config(config: Dict[str, Any]) -> None:
    """Save skill configuration to config/skills.json."""
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _load_secrets() -> Dict[str, Dict[str, str]]:
    """
    Load secrets from config/skill-secrets.json.

    Returns:
        Dict mapping skill_name -> {env_var_name: value}
    """
    secrets_path = _get_secrets_path()
    if secrets_path.exists():
        try:
            with open(secrets_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_secrets(secrets: Dict[str, Dict[str, str]]) -> None:
    """Save secrets to config/skill-secrets.json."""
    secrets_path = _get_secrets_path()
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    with open(secrets_path, 'w') as f:
        json.dump(secrets, f, indent=2)


# ============ Config Access ============

def get_skill_config(skill_name: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific skill.

    Args:
        skill_name: The skill name (e.g., "ragflow")

    Returns:
        Skill config dict or None if not configured.
    """
    config = _load_config()
    return config.get("skills", {}).get(skill_name)


def get_skill_required_env(skill_name: str) -> List[Dict[str, Any]]:
    """
    Get required environment variables for a skill.

    Args:
        skill_name: The skill name

    Returns:
        List of required env var configs:
        [{"name": "VAR_NAME", "description": "...", "secret": True, "default": "..."}]
    """
    skill_config = get_skill_config(skill_name)
    if not skill_config:
        return []
    return skill_config.get("required_env", [])


def set_skill_config(skill_name: str, required_env: List[Dict[str, Any]]) -> None:
    """
    Set configuration for a skill.

    Args:
        skill_name: The skill name
        required_env: List of required env var configs
    """
    config = _load_config()
    if "skills" not in config:
        config["skills"] = {}
    config["skills"][skill_name] = {"required_env": required_env}
    _save_config(config)


def delete_skill_config(skill_name: str) -> bool:
    """
    Delete configuration for a skill.

    Args:
        skill_name: The skill name

    Returns:
        True if deleted, False if not found.
    """
    config = _load_config()
    if skill_name in config.get("skills", {}):
        del config["skills"][skill_name]
        _save_config(config)
        return True
    return False


def list_skill_configs() -> Dict[str, Dict[str, Any]]:
    """
    List all skill configurations.

    Returns:
        Dict mapping skill_name -> config
    """
    config = _load_config()
    return config.get("skills", {})


# ============ Secrets Management ============

def get_skill_secret(skill_name: str, key_name: str) -> Tuple[Optional[str], str]:
    """
    Get a secret value for a skill.

    Priority: UI config (secrets file) > Environment variable > default value

    Args:
        skill_name: Skill name (e.g., "ragflow")
        key_name: Environment variable name (e.g., "RAGFLOW_API_KEY")

    Returns:
        Tuple of (value, source) where source is "secrets", "env", "default", or "none"
    """
    # Check UI config (secrets file) first
    secrets = _load_secrets()
    if skill_name in secrets and key_name in secrets[skill_name]:
        return secrets[skill_name][key_name], "secrets"

    # Fallback to .env file (multi-worker safe)
    from app.config import read_env_value
    env_value = read_env_value(key_name)
    if env_value:
        return env_value, "env"

    # Check for default value in config
    required_env = get_skill_required_env(skill_name)
    for env_config in required_env:
        if env_config.get("name") == key_name and "default" in env_config:
            return env_config["default"], "default"

    return None, "none"


def set_skill_secret(skill_name: str, key_name: str, value: str) -> None:
    """
    Set a secret value for a skill.

    Args:
        skill_name: Skill name
        key_name: Environment variable name
        value: The secret value
    """
    secrets = _load_secrets()
    if skill_name not in secrets:
        secrets[skill_name] = {}
    secrets[skill_name][key_name] = value
    _save_secrets(secrets)


def delete_skill_secret(skill_name: str, key_name: str) -> bool:
    """
    Delete a secret value for a skill.

    Args:
        skill_name: Skill name
        key_name: Environment variable name

    Returns:
        True if deleted, False if not found
    """
    secrets = _load_secrets()
    if skill_name in secrets and key_name in secrets[skill_name]:
        del secrets[skill_name][key_name]
        if not secrets[skill_name]:
            del secrets[skill_name]
        _save_secrets(secrets)
        return True
    return False


def get_skill_secrets_status(skill_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Get the configuration status for all required env vars of a skill.

    Args:
        skill_name: Skill name

    Returns:
        Dict mapping key_name -> {configured: bool, source: str, secret: bool}
    """
    required_env = get_skill_required_env(skill_name)
    status = {}
    for env_config in required_env:
        key_name = env_config.get("name")
        if not key_name:
            continue
        value, source = get_skill_secret(skill_name, key_name)
        status[key_name] = {
            "configured": value is not None and value != "",
            "source": source,
            "secret": env_config.get("secret", False),
            "description": env_config.get("description", ""),
        }
    return status


def get_all_skills_secrets_status() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Get the configuration status for all skills.

    Returns:
        Dict mapping skill_name -> {key_name -> status}
    """
    configs = list_skill_configs()
    result = {}
    for skill_name in configs:
        result[skill_name] = get_skill_secrets_status(skill_name)
    return result


def check_skill_env_ready(skill_name: str) -> Tuple[bool, List[str]]:
    """
    Check if all required environment variables for a skill are configured.

    Args:
        skill_name: Skill name

    Returns:
        Tuple of (all_ready, missing_keys)
    """
    status = get_skill_secrets_status(skill_name)
    missing = [key for key, info in status.items() if not info["configured"]]
    return len(missing) == 0, missing


def get_skills_env_vars(skill_names: List[str]) -> Dict[str, str]:
    """
    Get all configured environment variables for a list of skills.

    This collects all secrets/env vars that are configured (from secrets file,
    environment, or defaults) for the given skills.

    Args:
        skill_names: List of skill names

    Returns:
        Dict mapping env var name -> value (only includes configured values)
    """
    env_vars: Dict[str, str] = {}
    for skill_name in skill_names:
        required_env = get_skill_required_env(skill_name)
        for env_config in required_env:
            key_name = env_config.get("name")
            if not key_name:
                continue
            value, source = get_skill_secret(skill_name, key_name)
            if value is not None and value != "":
                env_vars[key_name] = value
    return env_vars


# ============ Dependencies Management ============

def check_skill_has_setup_script(skill_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a skill directory has a setup.sh file.

    Args:
        skill_name: The skill name

    Returns:
        Tuple of (has_setup_script, setup_script_path)
    """
    skills_dir = Path(_settings.custom_skills_dir).resolve()
    skill_dir = skills_dir / skill_name
    setup_script = skill_dir / "setup.sh"

    if setup_script.exists() and setup_script.is_file():
        return True, str(setup_script)
    return False, None


def get_skill_dependencies_status(skill_name: str) -> Dict[str, Any]:
    """
    Get the dependency installation status for a skill.

    Args:
        skill_name: The skill name

    Returns:
        Dict with:
          - skill_name: str
          - has_setup_script: bool
          - setup_script_path: Optional[str]
          - last_installed_at: Optional[str] (ISO timestamp)
          - last_install_success: Optional[bool]
          - needs_install: bool (has script but never installed)
    """
    has_script, script_path = check_skill_has_setup_script(skill_name)

    # Get stored installation info from config
    config = _load_config()
    skill_config = config.get("skills", {}).get(skill_name, {})
    deps_info = skill_config.get("dependencies", {})

    last_installed_at = deps_info.get("last_installed_at")
    last_install_success = deps_info.get("last_install_success")

    # needs_install: has setup script AND (never installed OR last install failed)
    needs_install = has_script and (last_installed_at is None or last_install_success is False)

    return {
        "skill_name": skill_name,
        "has_setup_script": has_script,
        "setup_script_path": script_path,
        "last_installed_at": last_installed_at,
        "last_install_success": last_install_success,
        "needs_install": needs_install,
    }


def set_skill_dependencies_installed(skill_name: str, success: bool, log: str) -> None:
    """
    Record the result of a dependency installation.

    Args:
        skill_name: The skill name
        success: Whether the installation succeeded
        log: The full installation log (stdout + stderr)
    """
    from datetime import datetime

    config = _load_config()
    if "skills" not in config:
        config["skills"] = {}
    if skill_name not in config["skills"]:
        config["skills"][skill_name] = {}

    config["skills"][skill_name]["dependencies"] = {
        "last_installed_at": datetime.utcnow().isoformat() + "Z",
        "last_install_success": success,
        "last_install_log": log,
    }
    _save_config(config)


def get_skill_dependencies_log(skill_name: str) -> Optional[str]:
    """
    Get the last installation log for a skill.

    Args:
        skill_name: The skill name

    Returns:
        The installation log or None if not available
    """
    config = _load_config()
    skill_config = config.get("skills", {}).get(skill_name, {})
    deps_info = skill_config.get("dependencies", {})
    return deps_info.get("last_install_log")
