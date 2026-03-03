"""
Real E2E test: verify all 4 memory file types are properly utilized.

- SOUL.md, USER.md, MEMORY.md → injected into system prompt
- memory/*.md (daily logs) → NOT injected, accessed via memory_get tool

Usage:
    MOONSHOT_API_KEY=sk-xxx OPENAI_API_KEY=sk-xxx \
    python -m pytest tests/test_e2e/test_memory_bootstrap_real.py -v -s
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.test_e2e.conftest import parse_sse_events

MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY", "")
pytestmark = pytest.mark.skipif(
    not MOONSHOT_KEY, reason="MOONSHOT_API_KEY not set"
)


def _patch_api_key():
    return patch.dict(os.environ, {"MOONSHOT_API_KEY": MOONSHOT_KEY})


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
class TestMemoryFileUtilization:
    """Verify all 4 memory file types are correctly utilized by a real agent."""

    _state: dict = {}

    # ── Test 1: Create preset and setup memory files ─────────

    async def test_01_setup(self, e2e_client, tmp_path_factory):
        """Create an agent preset and populate all 4 memory file types."""
        # Create preset in DB
        resp = await e2e_client.post(
            "/api/v1/agents",
            json={
                "name": f"memory-e2e-{uuid.uuid4().hex[:8]}",
                "description": "E2E memory file test agent",
                "skill_ids": [],
                "mcp_servers": [],
                "max_turns": 5,
                "model_provider": "kimi",
                "model_name": "kimi-k2.5",
            },
        )
        assert resp.status_code == 200
        preset = resp.json()
        agent_id = preset["id"]
        type(self)._state["agent_id"] = agent_id
        type(self)._state["preset_id"] = agent_id
        print(f"\n[Setup] Created preset: {agent_id}")

        # Create memory root and files
        root = tmp_path_factory.mktemp("memory")
        type(self)._state["memory_root"] = root

        agent_dir = root / "agents" / agent_id
        agent_dir.mkdir(parents=True)

        # 1) SOUL.md — distinctive persona
        (agent_dir / "SOUL.md").write_text(
            "You are Captain Cosmos, a space explorer. "
            "Always start your reply with 'Greetings, Earthling!' "
            "and refer to yourself as Captain Cosmos.",
            encoding="utf-8",
        )

        # 2) USER.md — user preferences
        (agent_dir / "USER.md").write_text(
            "User's name is Zephyr. Zephyr prefers bullet-point answers "
            "and dislikes long paragraphs. Zephyr's favorite language is Rust.",
            encoding="utf-8",
        )

        # 3) MEMORY.md — curated facts
        (agent_dir / "MEMORY.md").write_text(
            "- Project Starlight launched on 2026-02-14\n"
            "- The database was migrated from MySQL to CockroachDB on 2026-02-20\n"
            "- Sprint velocity is 42 story points per week\n",
            encoding="utf-8",
        )

        # 4) memory/YYYY-MM-DD.md — daily log (should NOT be in prompt)
        daily_dir = agent_dir / "memory"
        daily_dir.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        type(self)._state["today"] = today
        (daily_dir / f"{today}.md").write_text(
            "## Daily Log\n"
            "- Fixed bug #789 in the warp drive module\n"
            "- Deployed v3.2.1 to staging\n"
            "- TODO: review PR #42 from Lieutenant Nova\n",
            encoding="utf-8",
        )

        print(f"[Setup] Memory files created at {agent_dir}")
        for f in sorted(agent_dir.rglob("*.md")):
            print(f"  - {f.relative_to(agent_dir)}")

    # ── Test 2: SOUL.md persona is active ─────────────────────

    async def test_02_soul_md_persona(self, e2e_client, e2e_session_factories):
        """Agent should adopt the Captain Cosmos persona from SOUL.md."""
        agent_id = type(self)._state["agent_id"]
        root = type(self)._state["memory_root"]

        with (
            _patch_api_key(),
            patch("app.services.memory_service._memory_dir", return_value=root),
            patch("app.api.v1.sessions.AsyncSessionLocal", e2e_session_factories["async"]),
        ):
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": "Introduce yourself in one sentence.",
                    "agent_id": agent_id,
                    "max_turns": 1,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": uuid.uuid4().hex[:32],
                },
                timeout=60,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        answer = body.get("answer", "")
        print(f"\n[SOUL.md] Answer:\n{answer}")

        answer_lower = answer.lower()
        assert any(w in answer_lower for w in ("captain cosmos", "earthling", "cosmos", "space")), (
            f"SOUL.md persona not reflected in: {answer[:200]}"
        )

    # ── Test 3: USER.md preferences recognized ───────────────

    async def test_03_user_md_preferences(self, e2e_client, e2e_session_factories):
        """Agent should know user's name and preferences from USER.md."""
        agent_id = type(self)._state["agent_id"]
        root = type(self)._state["memory_root"]

        with (
            _patch_api_key(),
            patch("app.services.memory_service._memory_dir", return_value=root),
            patch("app.api.v1.sessions.AsyncSessionLocal", e2e_session_factories["async"]),
        ):
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": "What is my name and what programming language do I prefer?",
                    "agent_id": agent_id,
                    "max_turns": 1,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": uuid.uuid4().hex[:32],
                },
                timeout=60,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        answer = body.get("answer", "")
        print(f"\n[USER.md] Answer:\n{answer}")

        answer_lower = answer.lower()
        assert "zephyr" in answer_lower, f"User name not recognized: {answer[:200]}"
        assert "rust" in answer_lower, f"Language preference not recognized: {answer[:200]}"

    # ── Test 4: MEMORY.md facts available ─────────────────────

    async def test_04_memory_md_facts(self, e2e_client, e2e_session_factories):
        """Agent should know facts from MEMORY.md."""
        agent_id = type(self)._state["agent_id"]
        root = type(self)._state["memory_root"]

        with (
            _patch_api_key(),
            patch("app.services.memory_service._memory_dir", return_value=root),
            patch("app.api.v1.sessions.AsyncSessionLocal", e2e_session_factories["async"]),
        ):
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": (
                        "When did Project Starlight launch and "
                        "what database did we migrate to?"
                    ),
                    "agent_id": agent_id,
                    "max_turns": 1,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": uuid.uuid4().hex[:32],
                },
                timeout=60,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        answer = body.get("answer", "")
        print(f"\n[MEMORY.md] Answer:\n{answer}")

        answer_lower = answer.lower()
        assert any(d in answer_lower for d in ("2026-02-14", "february 14", "feb 14")), (
            f"Launch date not found: {answer[:200]}"
        )
        assert "cockroachdb" in answer_lower or "cockroach" in answer_lower, (
            f"Database migration fact not found: {answer[:200]}"
        )

    # ── Test 5: daily log NOT in bootstrap, accessible via memory_get ──

    async def test_05_daily_log_not_in_prompt(self):
        """Verify load_bootstrap_files does NOT include daily logs."""
        agent_id = type(self)._state["agent_id"]
        root = type(self)._state["memory_root"]
        today = type(self)._state["today"]

        with patch("app.services.memory_service._memory_dir", return_value=root):
            from app.services.memory_service import load_bootstrap_files

            files = load_bootstrap_files(agent_id)

        print(f"\n[Bootstrap] Keys: {list(files.keys())}")

        assert "SOUL.md" in files, "SOUL.md missing from bootstrap"
        assert "USER.md" in files, "USER.md missing from bootstrap"
        assert "MEMORY.md" in files, "MEMORY.md missing from bootstrap"
        assert f"memory/{today}.md" not in files, (
            f"Daily log memory/{today}.md should NOT be in bootstrap!"
        )
        assert not any(k.startswith("memory/") for k in files), (
            "No memory/*.md keys should be in bootstrap files"
        )

    async def test_06_daily_log_via_memory_get(self, e2e_client, e2e_session_factories):
        """Agent should use memory_get tool to read daily log content."""
        agent_id = type(self)._state["agent_id"]
        root = type(self)._state["memory_root"]
        today = type(self)._state["today"]

        with (
            _patch_api_key(),
            patch("app.services.memory_service._memory_dir", return_value=root),
            patch("app.api.v1.sessions.AsyncSessionLocal", e2e_session_factories["async"]),
        ):
            resp = await e2e_client.post(
                "/api/v1/agent/run/stream",
                json={
                    "request": (
                        f"Use the memory_get tool to read memory/{today}.md "
                        "and tell me what bugs were fixed today."
                    ),
                    "agent_id": agent_id,
                    "max_turns": 5,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": uuid.uuid4().hex[:32],
                },
                timeout=120,
            )

        assert resp.status_code == 200
        events = parse_sse_events(resp.text)

        # Inspect tool calls
        tool_calls = [e for e in events if e.get("event_type") == "tool_call"]
        tool_results = [e for e in events if e.get("event_type") == "tool_result"]

        print(f"\n[Daily Log] Tool calls ({len(tool_calls)}):")
        for tc in tool_calls:
            print(f"  - {tc.get('tool_name')}: {str(tc.get('tool_input', ''))[:120]}")

        print(f"[Daily Log] Tool results ({len(tool_results)}):")
        for tr in tool_results:
            print(f"  - {str(tr.get('content', ''))[:200]}")

        # Verify memory_get was called
        memory_get_calls = [
            tc for tc in tool_calls if tc.get("tool_name") == "memory_get"
        ]
        assert len(memory_get_calls) > 0, (
            f"Agent did not call memory_get! "
            f"Calls: {[tc.get('tool_name') for tc in tool_calls]}"
        )

        # Check final answer contains daily log content
        complete_events = [e for e in events if e.get("event_type") == "complete"]
        if complete_events:
            final_answer = complete_events[-1].get("answer", "")
            print(f"\n[Daily Log] Final answer:\n{final_answer}")
            final_lower = final_answer.lower()
            assert "789" in final_lower or "warp" in final_lower, (
                f"Daily log content not in answer: {final_answer[:200]}"
            )

    # ── Cleanup ───────────────────────────────────────────────

    async def test_99_cleanup(self, e2e_client):
        """Delete the test preset."""
        pid = type(self)._state.get("preset_id")
        if pid:
            await e2e_client.delete(f"/api/v1/agents/{pid}")
            print(f"\n[Cleanup] Deleted preset {pid}")
