"""Configuration management for Skill Composer."""
import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file into os.environ at startup
# Priority: config/.env (Docker volume, Settings API writes here) > ./.env (local dev fallback)
_config_env = Path(os.environ.get("CONFIG_DIR", "./config")) / ".env"
if _config_env.exists():
    load_dotenv(_config_env, override=True)
else:
    load_dotenv(override=True)

# Resolve env_file path for Pydantic Settings
_env_file = str(_config_env) if _config_env.exists() else ".env"


class Settings(BaseSettings):
    """Application settings"""
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    # API Server
    host: str = "127.0.0.1"
    port: int = 62610
    debug: bool = False

    # LLM API Keys
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""  # For Gemini

    # Default model configuration
    default_model_provider: str = "kimi"
    default_model_name: str = "kimi-k2.5"

    # Legacy: claude_model for backward compatibility
    claude_model: str = "claude-sonnet-4-5-20250929"

    # Agent configuration
    agent_max_turns: int = 60

    # Paths (can be overridden via environment variables for Docker)
    project_dir: str = "."
    skills_dir: str = ""  # SKILLS_DIR env var, defaults to custom_skills_dir if empty
    custom_skills_dir: str = "./skills"  # Fallback for skills_dir
    data_dir: str = "./data"  # DATA_DIR env var
    logs_dir: str = "./logs"  # LOGS_DIR env var
    upload_dir: str = "./uploads"  # UPLOADS_DIR env var
    config_dir: str = "./config"  # CONFIG_DIR env var
    backups_dir: str = "./backups"  # BACKUPS_DIR env var

    # File upload
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    # Code execution
    code_execution_timeout: int = 300  # seconds
    code_max_output_chars: int = 10000
    code_executor_type: str = "jupyter"  # "jupyter" or "simple"

    # Database (Phase 1: Skill Registry)
    # Can be overridden, but default uses data_dir
    database_url: str = ""
    database_echo: bool = False  # Log SQL statements

    # Meta skills (internal use only, not selectable by users)
    meta_skills: list[str] = ["skill-creator", "skill-updater", "skill-evolver", "skill-finder", "trace-qa", "skills-planner", "planning-with-files", "mcp-builder"]

    @property
    def effective_skills_dir(self) -> str:
        """Get effective skills directory (SKILLS_DIR or custom_skills_dir)"""
        return self.skills_dir if self.skills_dir else self.custom_skills_dir

    @property
    def effective_database_url(self) -> str:
        """Get effective database URL (DATABASE_URL or default PostgreSQL)"""
        if self.database_url:
            return self.database_url
        return "postgresql+asyncpg://skills:skills123@localhost:62620/skills_api"

    @property
    def effective_config_path(self) -> str:
        """Get effective MCP config path"""
        return f"{self.config_dir}/mcp.json"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Module-level settings instance for convenience
settings = get_settings()


def _get_env_file_path() -> Path:
    """Get the .env file path (config/.env or ./.env)."""
    config_env = Path(os.environ.get("CONFIG_DIR", "./config")) / ".env"
    if config_env.exists():
        return config_env
    project_env = Path(".env")
    if project_env.exists():
        return project_env
    return config_env


def read_env_value(key: str) -> str:
    """Read a single key's value from the .env file.

    Always reads from disk so all uvicorn workers and callsites
    see the latest value written by the Settings API.
    Falls back to os.environ if not found on disk (e.g. in tests
    or when vars are injected via docker-compose environment).
    """
    env_path = _get_env_file_path()
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == key:
                        return v.strip()
        except Exception:
            pass
    # Fallback to os.environ (tests, docker-compose environment injection)
    return os.environ.get(key, "")


def read_env_all() -> dict[str, str]:
    """Read all key-value pairs from the .env file.

    Returns a dict of all env vars. Always reads from disk.
    """
    env_path = _get_env_file_path()
    if not env_path.exists():
        return {}
    result = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    except Exception:
        pass
    return result


def get_search_dirs(project_dir: str = ".") -> list[Path]:
    """
    Get all searchable skill directories in priority order.

    Priority: custom > project .agent > global .agent > project .claude > global .claude
    """
    home = Path.home()
    project = Path(project_dir).resolve()
    settings = get_settings()

    dirs = [
        Path(settings.effective_skills_dir).resolve(),  # 0. Custom skills dir
        project / ".agent" / "skills",    # 1. Project universal
        home / ".agent" / "skills",        # 2. Global universal
        project / ".claude" / "skills",   # 3. Project claude
        home / ".claude" / "skills",       # 4. Global claude
    ]
    return dirs
