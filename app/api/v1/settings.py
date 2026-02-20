"""Settings API endpoints - Environment variable configuration."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/settings", tags=["Settings"])


class EnvVariable(BaseModel):
    """Environment variable model."""
    key: str
    value: str
    description: Optional[str] = None
    sensitive: bool = False
    source: str = "env"  # "env" (from .env file), "runtime" (os.environ only), "example" (from .env.example)
    category: str = "custom"  # "custom" (user-added, non-sensitive) or "preset" (API keys, sensitive)


class EnvVariableCreate(BaseModel):
    """Create environment variable request."""
    key: str
    value: str


class EnvVariableUpdate(BaseModel):
    """Environment variable update request."""
    key: str
    value: str


class EnvConfigResponse(BaseModel):
    """Environment configuration response."""
    variables: list[EnvVariable]
    env_file_path: str
    env_file_exists: bool


def _get_env_file_path() -> Path:
    """Get the path to the .env file.

    Prefer config_dir/.env (Docker volume, always writable) over
    project_dir/.env (bind mount, may be read-only due to userns remapping).
    """
    settings = get_settings()
    config_env = Path(settings.config_dir) / ".env"
    project_env = Path(settings.project_dir) / ".env"

    # Prefer config dir (Docker volume, always writable)
    if config_env.exists():
        return config_env.resolve()

    # Fallback to project dir (local dev, or Docker before first entrypoint run)
    if project_env.exists():
        return project_env.resolve()

    # Last resort: current working directory
    cwd_env = Path(".env")
    if cwd_env.exists():
        return cwd_env.resolve()

    # Default to config dir for new files (writable)
    return config_env.resolve()


def _is_sensitive_key(key: str) -> bool:
    """Check if a key is sensitive based on naming conventions."""
    sensitive_patterns = ["key", "password", "secret", "token", "credential", "auth"]
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in sensitive_patterns)


def _mask_value(value: str) -> str:
    """Mask a sensitive value for display."""
    if not value:
        return value
    if len(value) > 16:
        return f"{value[:8]}...{value[-4:]}"
    elif len(value) > 4:
        return f"{value[:2]}...{value[-2:]}"
    else:
        return "***"


def _read_env_file() -> dict[str, str]:
    """Read current .env file values."""
    env_path = _get_env_file_path()
    if not env_path.exists():
        return {}

    values = {}
    content = env_path.read_text(encoding="utf-8")

    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()

    return values


def _write_env_file(variables: dict[str, str]):
    """Write variables to .env file."""
    env_path = _get_env_file_path()

    lines = []
    for key, value in sorted(variables.items()):
        lines.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _delete_from_env_file(key: str):
    """Delete a variable from .env file."""
    env_path = _get_env_file_path()
    if not env_path.exists():
        return

    lines = env_path.read_text(encoding="utf-8").split("\n")
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            line_key = stripped.split("=")[0].strip()
            if line_key != key:
                new_lines.append(line)
        else:
            new_lines.append(line)

    env_path.write_text("\n".join(new_lines), encoding="utf-8")


def _get_custom_keys_path() -> Path:
    """Get the path to the custom keys file."""
    env_path = _get_env_file_path()
    return env_path.parent / ".env.custom.keys"


def _read_custom_keys() -> set[str]:
    """Read the set of user-added custom variable keys."""
    path = _get_custom_keys_path()
    if not path.exists():
        return set()
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return set()
    return set(line.strip() for line in content.split("\n") if line.strip())


def _add_custom_key(key: str):
    """Add a key to the custom keys file."""
    path = _get_custom_keys_path()
    custom_keys = _read_custom_keys()
    custom_keys.add(key)
    path.write_text("\n".join(sorted(custom_keys)) + "\n", encoding="utf-8")


def _remove_custom_key(key: str):
    """Remove a key from the custom keys file."""
    path = _get_custom_keys_path()
    custom_keys = _read_custom_keys()
    custom_keys.discard(key)
    if custom_keys:
        path.write_text("\n".join(sorted(custom_keys)) + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


@router.get("/env", response_model=EnvConfigResponse)
async def get_env_config():
    """
    Get environment variables from .env file only.

    Sensitive values (containing key, password, secret, token) are masked.
    Variables are categorized as "custom" (user-added via UI) or "preset" (from original .env).
    """
    # Get values from .env file only
    env_file_values = _read_env_file()
    custom_keys = _read_custom_keys()

    variables = []
    for key, value in env_file_values.items():
        sensitive = _is_sensitive_key(key)
        display_value = _mask_value(value) if sensitive else value
        # Category is based on whether user added it via UI, not sensitivity
        category = "custom" if key in custom_keys else "preset"

        variables.append(EnvVariable(
            key=key,
            value=display_value,
            sensitive=sensitive,
            source="env",
            category=category,
        ))

    # Sort: custom first, then preset, alphabetically within each group
    variables.sort(key=lambda v: (v.category != "custom", v.key))

    env_path = _get_env_file_path()
    return EnvConfigResponse(
        variables=variables,
        env_file_path=str(env_path),
        env_file_exists=env_path.exists(),
    )


@router.post("/env")
async def create_env_variable(create: EnvVariableCreate):
    """
    Create a new environment variable.

    Adds the variable to both the .env file and current process environment.
    """
    # Validate key format
    if not create.key or not create.key.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid key format. Use only alphanumeric characters and underscores."
        )

    # Check if already exists
    current_values = _read_env_file()
    if create.key in current_values:
        raise HTTPException(
            status_code=409,
            detail=f"Environment variable '{create.key}' already exists. Use PUT to update."
        )

    # Add to .env file
    current_values[create.key] = create.value
    _write_env_file(current_values)

    # Mark as user-added custom variable
    _add_custom_key(create.key)

    return {"success": True, "key": create.key, "message": f"Created {create.key}"}


@router.put("/env")
async def update_env_variable(update: EnvVariableUpdate):
    """
    Update an environment variable.

    Updates the value in the .env file. All workers read from .env directly.
    """
    # Validate key format
    if not update.key or not update.key.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid key format. Use only alphanumeric characters and underscores."
        )

    # Read current values
    current_values = _read_env_file()

    # Update value
    current_values[update.key] = update.value

    # Write back to file
    _write_env_file(current_values)

    return {"success": True, "key": update.key, "message": f"Updated {update.key}"}


@router.delete("/env/{key}")
async def delete_env_variable(key: str):
    """
    Delete an environment variable.

    Removes from both .env file and current process environment.
    """
    # Check if exists in .env file
    current_values = _read_env_file()

    if key not in current_values:
        raise HTTPException(
            status_code=404,
            detail=f"Environment variable '{key}' not found in .env file"
        )

    # Remove from .env file
    _delete_from_env_file(key)

    # Remove from custom keys if present
    _remove_custom_key(key)

    return {"success": True, "key": key, "message": f"Deleted {key}"}


@router.put("/env/batch")
async def update_env_variables_batch(updates: list[EnvVariableUpdate]):
    """
    Update multiple environment variables at once.
    """
    current_values = _read_env_file()

    for update in updates:
        if not update.key or not update.key.replace("_", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid key format for '{update.key}'"
            )
        current_values[update.key] = update.value

    _write_env_file(current_values)

    return {"success": True, "updated_count": len(updates)}
