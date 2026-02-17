"""
End-to-end tests using Kimi 2.5 (kimi-k2.5) API.

These tests require ``KIMI_API_KEY_REAL`` or ``MOONSHOT_API_KEY_REAL`` to be set.
They exercise the full Agent pipeline — no mocking.

Run:
    MOONSHOT_API_KEY_REAL=sk-xxx pytest tests/test_e2e/test_e2e_agent_real.py -v

All assertions check structure (types, non-empty, key existence),
never specific text content.
"""

import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.test_e2e.conftest import parse_sse_events

_KIMI_KEY = os.environ.get("KIMI_API_KEY_REAL", "") or os.environ.get("MOONSHOT_API_KEY_REAL", "")

skip_no_kimi = pytest.mark.skipif(
    not _KIMI_KEY,
    reason="KIMI_API_KEY_REAL or MOONSHOT_API_KEY_REAL not set"
)


def _patch_api_key():
    """Patch environment variable for Kimi API key."""
    return patch.dict(os.environ, {"MOONSHOT_API_KEY": _KIMI_KEY})


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_kimi
class TestRealAgentE2E:
    """Full Agent pipeline with real Kimi 2.5 API calls."""

    _state: dict = {}

    async def test_01_create_writing_agent(self, e2e_client: AsyncClient):
        """Create an Agent Preset for the real tests."""
        payload = {
            "name": "e2e-real-agent",
            "description": "E2E real LLM agent",
            "system_prompt": "You are a concise writing assistant. Reply briefly.",
            "skill_ids": [],
            "mcp_servers": [],
            "max_turns": 3,
            "model_provider": "kimi",
            "model_name": "kimi-k2.5",
        }
        resp = await e2e_client.post("/api/v1/agents", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "e2e-real-agent"
        type(self)._state["preset_id"] = body["id"]

    async def test_02_first_message(self, e2e_client: AsyncClient):
        """Send a simple message and validate response structure."""
        session_id = "e2e-real-session-001"
        type(self)._state["session_id"] = session_id
        with _patch_api_key():
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": "Hello, please respond with exactly one sentence.",
                    "max_turns": 3,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": session_id,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0
        assert body["trace_id"] is not None
        type(self)._state["trace_id_1"] = body["trace_id"]
        type(self)._state["first_answer"] = body["answer"]

    async def test_03_follow_up(self, e2e_client: AsyncClient):
        """Send a follow-up message using the same session (history loaded from DB)."""
        session_id = type(self)._state["session_id"]
        with _patch_api_key():
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": "Summarize what you just said in one word.",
                    "session_id": session_id,
                    "max_turns": 3,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["answer"], str)
        assert len(body["answer"]) > 0
        type(self)._state["trace_id_2"] = body["trace_id"]

    async def test_04_verify_traces(self, e2e_client: AsyncClient):
        """Verify that at least 2 traces were created."""
        resp = await e2e_client.get("/api/v1/traces")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2

        # Verify individual traces
        for key in ("trace_id_1", "trace_id_2"):
            tid = type(self)._state.get(key)
            if tid:
                detail_resp = await e2e_client.get(f"/api/v1/traces/{tid}")
                assert detail_resp.status_code == 200
                detail = detail_resp.json()
                assert detail["success"] is True
                assert detail["total_turns"] >= 1
                assert detail["total_input_tokens"] > 0
                assert detail["total_output_tokens"] > 0

    async def test_05_stream_conversation(self, e2e_client: AsyncClient):
        """Test SSE streaming with real LLM."""
        with _patch_api_key():
            resp = await e2e_client.post(
                "/api/v1/agent/run/stream",
                json={
                    "request": "Say hello in exactly three words.",
                    "max_turns": 3,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": "e2e-real-stream-session",
                },
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = parse_sse_events(resp.text)
        assert len(events) >= 2  # at least run_started + one more

        # First event should be run_started
        assert events[0]["event_type"] == "run_started"
        assert "trace_id" in events[0]

    async def test_06_cleanup(self, e2e_client: AsyncClient):
        """Delete the preset and traces."""
        pid = type(self)._state.get("preset_id")
        if pid:
            await e2e_client.delete(f"/api/v1/agents/{pid}")

        for key in ("trace_id_1", "trace_id_2"):
            tid = type(self)._state.get(key)
            if tid:
                await e2e_client.delete(f"/api/v1/traces/{tid}")


# ---------------------------------------------------------------------------
# Real Evolve E2E — jpg-to-bmp skill (create → trace → evolve → delete)
# ---------------------------------------------------------------------------

_JPG_TO_BMP_DIR = Path("skills/jpg-to-bmp")

_JPG_TO_BMP_SKILL_MD = """\
---
name: jpg-to-bmp
description: Convert JPG/JPEG images to BMP format. Handles color space conversion, resolution preservation, and basic image transformations during the conversion process.
---

# JPG to BMP Converter

## Overview

Convert JPG/JPEG images to BMP (Bitmap) format while preserving image quality.

## Conversion Steps

1. **Read Input**: Load the JPG/JPEG file using Pillow
2. **Color Space Check**: Ensure RGB color space (convert from CMYK if needed)
3. **Save as BMP**: Write output in uncompressed BMP format
4. **Verify Output**: Confirm output file dimensions match input

## Usage

```python
from PIL import Image

img = Image.open("input.jpg")
if img.mode != "RGB":
    img = img.convert("RGB")
img.save("output.bmp", "BMP")
```

## Notes

- BMP files are uncompressed, expect ~10x larger file size than JPG
- Maximum BMP dimensions: 32767 x 32767 pixels
- Alpha channel from RGBA images is discarded in BMP conversion
"""


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_kimi
class TestRealEvolveE2E:
    """Full lifecycle: create skill → trace → evolve via traces → evolve via feedback → delete."""

    _state: dict = {}

    @pytest.fixture(autouse=True, scope="class")
    def _cleanup_disk(self):
        """Ensure the jpg-to-bmp disk directory is removed after the class."""
        yield
        if _JPG_TO_BMP_DIR.exists():
            shutil.rmtree(_JPG_TO_BMP_DIR)

    # -- helpers --

    async def _poll_task(self, client: AsyncClient, task_id: str, timeout_s: int = 300):
        """Poll task status until completed/failed or timeout."""
        for _ in range(timeout_s // 5):
            await asyncio.sleep(5)
            resp = await client.get(f"/api/v1/registry/tasks/{task_id}")
            assert resp.status_code == 200
            data = resp.json()
            if data["status"] in ("completed", "failed"):
                return data
        pytest.fail(f"Task {task_id} did not finish within {timeout_s}s")

    # -- tests --

    async def test_01_create_skill_on_disk(self):
        """Write SKILL.md to disk so import-local can pick it up."""
        _JPG_TO_BMP_DIR.mkdir(parents=True, exist_ok=True)
        (_JPG_TO_BMP_DIR / "SKILL.md").write_text(
            _JPG_TO_BMP_SKILL_MD, encoding="utf-8"
        )
        assert (_JPG_TO_BMP_DIR / "SKILL.md").exists()

    async def test_02_register_skill(self, e2e_client: AsyncClient):
        """Register the on-disk jpg-to-bmp skill into the test DB."""
        resp = await e2e_client.post(
            "/api/v1/registry/import-local",
            json={"skill_names": ["jpg-to-bmp"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_imported"] >= 1
        result = next(r for r in body["results"] if r["name"] == "jpg-to-bmp")
        assert result["success"] is True

    async def test_03_run_agent_to_generate_trace(self, e2e_client: AsyncClient):
        """Run Agent with jpg-to-bmp to create a trace."""
        with _patch_api_key():
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": (
                        "Using the jpg-to-bmp skill, explain how to convert a "
                        "JPG image to BMP in Python. Keep it to 3 sentences max."
                    ),
                    "skills": ["jpg-to-bmp"],
                    "max_turns": 5,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": "e2e-evolve-session",
                },
                timeout=120,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["trace_id"] is not None
        type(self)._state["trace_id"] = body["trace_id"]

    async def test_04_verify_trace(self, e2e_client: AsyncClient):
        """Verify the trace from the agent run."""
        tid = type(self)._state["trace_id"]
        resp = await e2e_client.get(f"/api/v1/traces/{tid}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["success"] is True
        assert detail["total_turns"] >= 1
        assert detail["total_input_tokens"] > 0

    async def test_05_evolve_via_traces(
        self, e2e_client: AsyncClient, e2e_session_factories
    ):
        """Evolve jpg-to-bmp using the trace + feedback."""
        tid = type(self)._state["trace_id"]
        factories = e2e_session_factories

        with (
            _patch_api_key(),
            patch("app.services.task_manager.SyncSessionLocal", factories["sync"]),
            patch("app.services.task_manager.AsyncSessionLocal", factories["async"]),
            patch("app.api.v1.registry.SyncSessionLocal", factories["sync"]),
        ):
            resp = await e2e_client.post(
                "/api/v1/registry/skills/jpg-to-bmp/evolve-via-traces",
                json={
                    "trace_ids": [tid],
                    "feedback": (
                        "Add a section about handling EXIF metadata during "
                        "conversion, including orientation correction"
                    ),
                },
            )
            assert resp.status_code == 202
            task_id = resp.json()["task_id"]
            type(self)._state["evolve_task_1"] = task_id

            result = await self._poll_task(e2e_client, task_id)

        assert result["status"] == "completed", f"Evolve failed: {result.get('error')}"
        type(self)._state["evolved_version_1"] = result.get("new_version")

    async def test_06_verify_evolved_version(self, e2e_client: AsyncClient):
        """Verify at least 2 versions exist after evolve."""
        resp = await e2e_client.get(
            "/api/v1/registry/skills/jpg-to-bmp/versions"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2

    async def test_07_evolve_via_feedback_only(
        self, e2e_client: AsyncClient, e2e_session_factories
    ):
        """Evolve using feedback only (no traces) — routes to skill-updater."""
        factories = e2e_session_factories

        with (
            _patch_api_key(),
            patch("app.services.task_manager.SyncSessionLocal", factories["sync"]),
            patch("app.services.task_manager.AsyncSessionLocal", factories["async"]),
            patch("app.api.v1.registry.SyncSessionLocal", factories["sync"]),
        ):
            resp = await e2e_client.post(
                "/api/v1/registry/skills/jpg-to-bmp/evolve-via-traces",
                json={
                    "feedback": (
                        "Add support for batch conversion of multiple "
                        "JPG files in a directory"
                    ),
                },
            )
            assert resp.status_code == 202
            task_id = resp.json()["task_id"]
            type(self)._state["evolve_task_2"] = task_id

            result = await self._poll_task(e2e_client, task_id)

        assert result["status"] == "completed", f"Evolve failed: {result.get('error')}"
        type(self)._state["evolved_version_2"] = result.get("new_version")

    async def test_08_verify_three_versions(self, e2e_client: AsyncClient):
        """Verify at least 3 versions after two evolves."""
        resp = await e2e_client.get(
            "/api/v1/registry/skills/jpg-to-bmp/versions"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3

    async def test_09_verify_disk_modified(self):
        """SKILL.md on disk should differ from the seed content after evolves."""
        path = _JPG_TO_BMP_DIR / "SKILL.md"
        if not path.exists():
            pytest.skip("SKILL.md not on disk")
        current = path.read_text(encoding="utf-8")
        assert current != _JPG_TO_BMP_SKILL_MD, (
            "SKILL.md should have been modified by evolve"
        )

    async def test_10_delete_skill(self, e2e_client: AsyncClient):
        """Delete the skill (DB + disk)."""
        resp = await e2e_client.delete("/api/v1/registry/skills/jpg-to-bmp")
        assert resp.status_code == 204

    async def test_11_verify_deleted(self, e2e_client: AsyncClient):
        """Confirm the skill no longer exists."""
        resp = await e2e_client.get("/api/v1/registry/skills/jpg-to-bmp")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Real Import Lifecycle E2E — qdrant skill
# ---------------------------------------------------------------------------


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_kimi
class TestRealImportLifecycleE2E:
    """Import → Agent query → version → export → delete lifecycle."""

    _state: dict = {}

    async def test_01_import_qdrant(self, e2e_client: AsyncClient, qdrant_zip_bytes):
        """Import qdrant.zip via multipart upload."""
        resp = await e2e_client.post(
            "/api/v1/registry/import",
            files={"file": ("qdrant.zip", qdrant_zip_bytes, "application/zip")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "qdrant" in body["skill_name"]
        type(self)._state["skill_name"] = body["skill_name"]
        type(self)._state["initial_version"] = body["version"]

    async def test_02_verify_skill(self, e2e_client: AsyncClient):
        """Verify the imported skill exists in registry."""
        name = type(self)._state["skill_name"]
        resp = await e2e_client.get(f"/api/v1/registry/skills/{name}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == name
        assert body["current_version"] == type(self)._state["initial_version"]

    async def test_03_run_agent_with_skill(self, e2e_client: AsyncClient):
        """Run Agent with qdrant skill and verify success."""
        name = type(self)._state["skill_name"]
        with _patch_api_key():
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": (
                        f"Using the {name} skill, briefly explain "
                        "what Qdrant is and its main use case in 2 sentences."
                    ),
                    "skills": [name],
                    "max_turns": 5,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": "e2e-import-session",
                },
                timeout=120,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["trace_id"] is not None
        type(self)._state["trace_id"] = body["trace_id"]

    async def test_04_verify_trace(self, e2e_client: AsyncClient):
        """Verify trace from the agent run."""
        tid = type(self)._state["trace_id"]
        resp = await e2e_client.get(f"/api/v1/traces/{tid}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["success"] is True
        assert detail["total_input_tokens"] > 0

    async def test_05_create_version(self, e2e_client: AsyncClient):
        """Create a new version of the imported skill."""
        name = type(self)._state["skill_name"]
        resp = await e2e_client.post(
            f"/api/v1/registry/skills/{name}/versions",
            json={
                "version": "0.0.2",
                "skill_md": "# Qdrant Vector Search\n\nUpdated for E2E test.",
                "commit_message": "E2E test version bump",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["version"] == "0.0.2"

    async def test_06_list_versions(self, e2e_client: AsyncClient):
        """Verify both versions exist."""
        name = type(self)._state["skill_name"]
        resp = await e2e_client.get(
            f"/api/v1/registry/skills/{name}/versions"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2
        versions = [v["version"] for v in body["versions"]]
        assert type(self)._state["initial_version"] in versions
        assert "0.0.2" in versions

    async def test_07_export(self, e2e_client: AsyncClient):
        """Export the skill and verify it's a valid zip containing SKILL.md."""
        name = type(self)._state["skill_name"]
        resp = await e2e_client.get(
            f"/api/v1/registry/skills/{name}/export"
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "zip" in content_type or "octet-stream" in content_type

        import zipfile
        import io

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert any("SKILL.md" in n for n in names)

    async def test_08_delete(self, e2e_client: AsyncClient):
        """Delete the skill (also removes disk dir created by import)."""
        name = type(self)._state["skill_name"]
        resp = await e2e_client.delete(
            f"/api/v1/registry/skills/{name}"
        )
        assert resp.status_code == 204

    async def test_09_verify_deleted(self, e2e_client: AsyncClient):
        """Confirm the skill no longer exists."""
        name = type(self)._state["skill_name"]
        resp = await e2e_client.get(
            f"/api/v1/registry/skills/{name}"
        )
        assert resp.status_code == 404
