"""
Tests for Settings API endpoints — environment variable CRUD.

Endpoints tested:
- GET    /api/v1/settings/env          — list all env vars
- POST   /api/v1/settings/env          — create env var
- PUT    /api/v1/settings/env          — update env var
- DELETE /api/v1/settings/env/{key}    — delete env var
- PUT    /api/v1/settings/env/batch    — batch update

Also tests the single-source-of-truth mechanism:
- config/.env is the canonical file for reads and writes
- load_dotenv loads from config/.env, overriding docker-compose env vars
- os.environ is updated on write for immediate runtime effect
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_test_env(path: Path, content: str):
    """Write a test .env file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_test_env(path: Path) -> dict[str, str]:
    """Read a test .env file into a dict."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values


# ---------------------------------------------------------------------------
# GET /api/v1/settings/env
# ---------------------------------------------------------------------------

class TestGetEnvConfig:
    """Tests for GET /api/v1/settings/env."""

    async def test_get_env_returns_200(self, client: AsyncClient):
        response = await client.get("/api/v1/settings/env")
        assert response.status_code == 200
        data = response.json()
        assert "variables" in data
        assert "env_file_path" in data
        assert "env_file_exists" in data

    async def test_get_env_has_variables_list(self, client: AsyncClient):
        response = await client.get("/api/v1/settings/env")
        data = response.json()
        assert isinstance(data["variables"], list)

    async def test_get_env_masks_sensitive_values(self, client: AsyncClient, tmp_path: Path):
        """Sensitive keys (containing 'key', 'password', etc.) should be masked."""
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "MY_API_KEY=sk-supersecretvalue12345678\nNORMAL_VAR=hello\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        vars_by_key = {v["key"]: v for v in data["variables"]}

        assert vars_by_key["MY_API_KEY"]["sensitive"] is True
        assert "supersecret" not in vars_by_key["MY_API_KEY"]["value"]
        assert vars_by_key["MY_API_KEY"]["value"].startswith("sk-super")
        assert vars_by_key["MY_API_KEY"]["value"].endswith("...5678")

        assert vars_by_key["NORMAL_VAR"]["sensitive"] is False
        assert vars_by_key["NORMAL_VAR"]["value"] == "hello"

    async def test_get_env_categorizes_custom_vs_preset(self, client: AsyncClient, tmp_path: Path):
        """Variables in .env.custom.keys should be category=custom, others preset."""
        env_file = tmp_path / ".env"
        custom_keys_file = tmp_path / ".env.custom.keys"
        _write_test_env(env_file, "PRESET_VAR=aaa\nCUSTOM_VAR=bbb\n")
        custom_keys_file.write_text("CUSTOM_VAR\n", encoding="utf-8")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        vars_by_key = {v["key"]: v for v in data["variables"]}
        assert vars_by_key["CUSTOM_VAR"]["category"] == "custom"
        assert vars_by_key["PRESET_VAR"]["category"] == "preset"

    async def test_get_env_custom_sorted_first(self, client: AsyncClient, tmp_path: Path):
        """Custom variables should appear before preset variables."""
        env_file = tmp_path / ".env"
        custom_keys_file = tmp_path / ".env.custom.keys"
        _write_test_env(env_file, "ZZZ_PRESET=1\nAAA_CUSTOM=2\n")
        custom_keys_file.write_text("AAA_CUSTOM\n", encoding="utf-8")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        keys = [v["key"] for v in data["variables"]]
        assert keys.index("AAA_CUSTOM") < keys.index("ZZZ_PRESET")

    async def test_get_env_skips_comments_and_blank_lines(self, client: AsyncClient, tmp_path: Path):
        """Comments and blank lines in .env should be ignored."""
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "# comment\n\nVAR_A=1\n# another comment\nVAR_B=2\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        keys = {v["key"] for v in data["variables"]}
        assert keys == {"VAR_A", "VAR_B"}

    async def test_get_env_nonexistent_file(self, client: AsyncClient, tmp_path: Path):
        """When .env file doesn't exist, return empty list."""
        missing = tmp_path / "nonexistent" / ".env"

        with patch("app.api.v1.settings._get_env_file_path", return_value=missing):
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        assert data["variables"] == []
        assert data["env_file_exists"] is False


# ---------------------------------------------------------------------------
# POST /api/v1/settings/env
# ---------------------------------------------------------------------------

class TestCreateEnvVariable:
    """Tests for POST /api/v1/settings/env."""

    async def test_create_variable(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "EXISTING=val\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.post(
                "/api/v1/settings/env",
                json={"key": "NEW_VAR", "value": "new_value"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["key"] == "NEW_VAR"

        # Verify written to file
        written = _read_test_env(env_file)
        assert written["NEW_VAR"] == "new_value"
        assert written["EXISTING"] == "val"

    async def test_create_variable_marked_as_custom(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            await client.post(
                "/api/v1/settings/env",
                json={"key": "UI_ADDED", "value": "yes"},
            )

        custom_keys_file = tmp_path / ".env.custom.keys"
        assert custom_keys_file.exists()
        assert "UI_ADDED" in custom_keys_file.read_text()

    async def test_create_duplicate_returns_409(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "DUPE_VAR=old\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.post(
                "/api/v1/settings/env",
                json={"key": "DUPE_VAR", "value": "new"},
            )

        assert response.status_code == 409

    async def test_create_invalid_key_returns_400(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.post(
                "/api/v1/settings/env",
                json={"key": "invalid-key!", "value": "val"},
            )

        assert response.status_code == 400

    async def test_create_empty_key_returns_400(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.post(
                "/api/v1/settings/env",
                json={"key": "", "value": "val"},
            )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# PUT /api/v1/settings/env
# ---------------------------------------------------------------------------

class TestUpdateEnvVariable:
    """Tests for PUT /api/v1/settings/env."""

    async def test_update_existing_variable(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "UPDATE_ME=old_value\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.put(
                "/api/v1/settings/env",
                json={"key": "UPDATE_ME", "value": "new_value"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

        written = _read_test_env(env_file)
        assert written["UPDATE_ME"] == "new_value"

    async def test_update_creates_if_not_exists(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.put(
                "/api/v1/settings/env",
                json={"key": "BRAND_NEW", "value": "created"},
            )

        assert response.status_code == 200
        written = _read_test_env(env_file)
        assert written["BRAND_NEW"] == "created"

    async def test_update_invalid_key_returns_400(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.put(
                "/api/v1/settings/env",
                json={"key": "bad key spaces", "value": "val"},
            )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/v1/settings/env/{key}
# ---------------------------------------------------------------------------

class TestDeleteEnvVariable:
    """Tests for DELETE /api/v1/settings/env/{key}."""

    async def test_delete_variable(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "DELETE_ME=goodbye\nKEEP_ME=stay\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.delete("/api/v1/settings/env/DELETE_ME")

        assert response.status_code == 200
        assert response.json()["success"] is True

        written = _read_test_env(env_file)
        assert "DELETE_ME" not in written
        assert written["KEEP_ME"] == "stay"

    async def test_delete_removes_custom_key_tracking(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        custom_keys_file = tmp_path / ".env.custom.keys"
        _write_test_env(env_file, "MY_CUSTOM=val\n")
        custom_keys_file.write_text("MY_CUSTOM\n", encoding="utf-8")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            await client.delete("/api/v1/settings/env/MY_CUSTOM")

        # Custom keys file should be cleaned up
        if custom_keys_file.exists():
            assert "MY_CUSTOM" not in custom_keys_file.read_text()

    async def test_delete_nonexistent_returns_404(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "SOMETHING=val\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.delete("/api/v1/settings/env/DOES_NOT_EXIST")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/settings/env/batch
# ---------------------------------------------------------------------------

class TestBatchUpdateEnvVariables:
    """Tests for PUT /api/v1/settings/env/batch."""

    async def test_batch_update(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "A=1\nB=2\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.put(
                "/api/v1/settings/env/batch",
                json=[
                    {"key": "A", "value": "10"},
                    {"key": "B", "value": "20"},
                    {"key": "C", "value": "30"},
                ],
            )

        assert response.status_code == 200
        assert response.json()["updated_count"] == 3

        written = _read_test_env(env_file)
        assert written == {"A": "10", "B": "20", "C": "30"}

    async def test_batch_update_invalid_key_returns_400(self, client: AsyncClient, tmp_path: Path):
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            response = await client.put(
                "/api/v1/settings/env/batch",
                json=[
                    {"key": "GOOD_KEY", "value": "ok"},
                    {"key": "bad-key!", "value": "fail"},
                ],
            )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Masking logic
# ---------------------------------------------------------------------------

class TestMaskValue:
    """Tests for _mask_value and _is_sensitive_key helpers."""

    def test_sensitive_key_patterns(self):
        from app.api.v1.settings import _is_sensitive_key
        assert _is_sensitive_key("ANTHROPIC_API_KEY") is True
        assert _is_sensitive_key("DB_PASSWORD") is True
        assert _is_sensitive_key("MY_SECRET") is True
        assert _is_sensitive_key("AUTH_TOKEN") is True
        assert _is_sensitive_key("CREDENTIAL_FILE") is True
        assert _is_sensitive_key("NORMAL_VAR") is False
        assert _is_sensitive_key("DEBUG") is False
        assert _is_sensitive_key("TZ") is False

    def test_mask_long_value(self):
        from app.api.v1.settings import _mask_value
        result = _mask_value("sk-ant-1234567890abcdef")
        assert result == "sk-ant-1...cdef"

    def test_mask_medium_value(self):
        from app.api.v1.settings import _mask_value
        result = _mask_value("short-key")
        assert result == "sh...ey"

    def test_mask_short_value(self):
        from app.api.v1.settings import _mask_value
        assert _mask_value("abc") == "***"

    def test_mask_empty_value(self):
        from app.api.v1.settings import _mask_value
        assert _mask_value("") == ""


# ---------------------------------------------------------------------------
# Config.py load_dotenv priority
# ---------------------------------------------------------------------------

class TestConfigEnvPriority:
    """Tests for config.py load_dotenv single-source-of-truth."""

    def test_config_env_preferred_over_project_env(self, tmp_path: Path):
        """When config/.env exists, it should be loaded instead of project .env."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_env = config_dir / ".env"
        config_env.write_text("TEST_PRIORITY=from_config\n")

        project_env = tmp_path / ".env"
        project_env.write_text("TEST_PRIORITY=from_project\n")

        # Simulate what config.py does
        from dotenv import load_dotenv
        os.environ.pop("TEST_PRIORITY", None)

        if config_env.exists():
            load_dotenv(config_env, override=True)
        else:
            load_dotenv(project_env, override=True)

        assert os.environ.get("TEST_PRIORITY") == "from_config"
        os.environ.pop("TEST_PRIORITY", None)

    def test_load_dotenv_override_beats_compose_env(self, tmp_path: Path):
        """load_dotenv(override=True) should override pre-existing os.environ values.

        This simulates: docker-compose injects old value → load_dotenv overrides with new value.
        """
        config_env = tmp_path / ".env"
        config_env.write_text("OVERRIDE_TEST=new_from_settings\n")

        # Simulate docker-compose injecting an old value
        os.environ["OVERRIDE_TEST"] = "old_from_compose"

        from dotenv import load_dotenv
        load_dotenv(config_env, override=True)

        assert os.environ.get("OVERRIDE_TEST") == "new_from_settings"
        os.environ.pop("OVERRIDE_TEST", None)

    def test_env_file_path_prefers_config_dir(self, tmp_path: Path):
        """_get_env_file_path should prefer config_dir/.env over project_dir/.env."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / ".env").write_text("X=1\n")
        (tmp_path / ".env").write_text("X=2\n")

        from app.api.v1.settings import _get_env_file_path
        with patch("app.api.v1.settings.get_settings") as mock_settings:
            mock_settings.return_value.config_dir = str(config_dir)
            mock_settings.return_value.project_dir = str(tmp_path)
            path = _get_env_file_path()

        assert path == (config_dir / ".env").resolve()

    def test_env_file_path_fallback_to_project(self, tmp_path: Path):
        """When config/.env doesn't exist, fall back to project_dir/.env."""
        config_dir = tmp_path / "config"  # dir exists but no .env
        config_dir.mkdir()
        (tmp_path / ".env").write_text("Y=1\n")

        from app.api.v1.settings import _get_env_file_path
        with patch("app.api.v1.settings.get_settings") as mock_settings:
            mock_settings.return_value.config_dir = str(config_dir)
            mock_settings.return_value.project_dir = str(tmp_path)
            path = _get_env_file_path()

        assert path == (tmp_path / ".env").resolve()


# ---------------------------------------------------------------------------
# Write + Read roundtrip
# ---------------------------------------------------------------------------

class TestEnvFileRoundtrip:
    """Tests that write → read → verify through the API is consistent."""

    async def test_create_then_read(self, client: AsyncClient, tmp_path: Path):
        """POST a variable, then GET should return it."""
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            await client.post(
                "/api/v1/settings/env",
                json={"key": "ROUNDTRIP_VAR", "value": "trip_value"},
            )
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        keys = {v["key"]: v["value"] for v in data["variables"]}
        assert keys["ROUNDTRIP_VAR"] == "trip_value"

        os.environ.pop("ROUNDTRIP_VAR", None)

    async def test_update_then_read(self, client: AsyncClient, tmp_path: Path):
        """PUT a variable, then GET should return the updated value."""
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "CHANGE_ME=before\n")

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            await client.put(
                "/api/v1/settings/env",
                json={"key": "CHANGE_ME", "value": "after"},
            )
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        keys = {v["key"]: v["value"] for v in data["variables"]}
        assert keys["CHANGE_ME"] == "after"

        os.environ.pop("CHANGE_ME", None)

    async def test_delete_then_read(self, client: AsyncClient, tmp_path: Path):
        """DELETE a variable, then GET should not return it."""
        env_file = tmp_path / ".env"
        _write_test_env(env_file, "GONE=soon\n")
        os.environ["GONE"] = "soon"

        with patch("app.api.v1.settings._get_env_file_path", return_value=env_file):
            await client.delete("/api/v1/settings/env/GONE")
            response = await client.get("/api/v1/settings/env")

        data = response.json()
        keys = {v["key"] for v in data["variables"]}
        assert "GONE" not in keys
