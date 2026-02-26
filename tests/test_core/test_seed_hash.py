"""
Tests for seed hash computation functions.

- Pure logic tests (no database required) — verifies determinism,
  order-independence, field handling, and round-trip consistency.
- Integration tests (requires PostgreSQL) — verifies 4-case startup logic
  for seed agents directly against the database.
"""

import json
import uuid

import pytest
from sqlalchemy import text

from app.db.database import (
    _compute_agent_seed_hash,
    _compute_skill_seed_hash,
    _db_row_to_agent_dict,
    _db_row_to_skill_seed_dict,
    _sync_one_seed_agent,
)


# ---------------------------------------------------------------------------
# Agent seed hash tests
# ---------------------------------------------------------------------------

class TestComputeAgentSeedHash:
    """Tests for _compute_agent_seed_hash."""

    def _base_agent(self, **overrides):
        data = {
            "system_prompt": "You are helpful.",
            "description": "Test agent",
            "skill_ids": ["skill-a", "skill-b"],
            "mcp_servers": ["time", "tavily"],
            "builtin_tools": None,
            "max_turns": 60,
            "model_provider": "kimi",
            "model_name": "kimi-k2.5",
            "executor_name": "base",
        }
        data.update(overrides)
        return data

    def test_deterministic(self):
        """Same input produces same hash."""
        data = self._base_agent()
        h1 = _compute_agent_seed_hash(data)
        h2 = _compute_agent_seed_hash(data)
        assert h1 == h2

    def test_hash_format(self):
        """Hash is 64-character lowercase hex (SHA-256)."""
        h = _compute_agent_seed_hash(self._base_agent())
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_list_order_independent(self):
        """Sorted lists produce identical hash regardless of input order."""
        h1 = _compute_agent_seed_hash(self._base_agent(skill_ids=["b", "a"]))
        h2 = _compute_agent_seed_hash(self._base_agent(skill_ids=["a", "b"]))
        assert h1 == h2

    def test_mcp_order_independent(self):
        """MCP server list order doesn't affect hash."""
        h1 = _compute_agent_seed_hash(self._base_agent(mcp_servers=["tavily", "time"]))
        h2 = _compute_agent_seed_hash(self._base_agent(mcp_servers=["time", "tavily"]))
        assert h1 == h2

    def test_builtin_tools_order_independent(self):
        """Builtin tools list order doesn't affect hash."""
        h1 = _compute_agent_seed_hash(self._base_agent(builtin_tools=["read", "write", "bash"]))
        h2 = _compute_agent_seed_hash(self._base_agent(builtin_tools=["bash", "read", "write"]))
        assert h1 == h2

    def test_different_content_different_hash(self):
        """Different inputs produce different hashes."""
        h1 = _compute_agent_seed_hash(self._base_agent(description="Agent A"))
        h2 = _compute_agent_seed_hash(self._base_agent(description="Agent B"))
        assert h1 != h2

    def test_none_vs_empty_list_builtin_tools(self):
        """None and [] for builtin_tools produce different hashes (None means 'all')."""
        h1 = _compute_agent_seed_hash(self._base_agent(builtin_tools=None))
        h2 = _compute_agent_seed_hash(self._base_agent(builtin_tools=[]))
        assert h1 != h2

    def test_none_vs_empty_list_skill_ids(self):
        """None and [] for skill_ids produce the same hash (both mean 'no skills')."""
        h1 = _compute_agent_seed_hash(self._base_agent(skill_ids=None))
        h2 = _compute_agent_seed_hash(self._base_agent(skill_ids=[]))
        assert h1 == h2

    def test_missing_fields_use_defaults(self):
        """Missing fields fall back to defaults without error."""
        minimal = {"name": "test"}
        h = _compute_agent_seed_hash(minimal)
        assert len(h) == 64

    def test_max_turns_matters(self):
        """Different max_turns produces different hash."""
        h1 = _compute_agent_seed_hash(self._base_agent(max_turns=60))
        h2 = _compute_agent_seed_hash(self._base_agent(max_turns=120))
        assert h1 != h2

    def test_system_prompt_matters(self):
        """Different system_prompt produces different hash."""
        h1 = _compute_agent_seed_hash(self._base_agent(system_prompt="Prompt A"))
        h2 = _compute_agent_seed_hash(self._base_agent(system_prompt="Prompt B"))
        assert h1 != h2

    def test_executor_name_matters(self):
        """Different executor_name produces different hash."""
        h1 = _compute_agent_seed_hash(self._base_agent(executor_name="base"))
        h2 = _compute_agent_seed_hash(self._base_agent(executor_name="ml"))
        assert h1 != h2


# ---------------------------------------------------------------------------
# Skill seed hash tests
# ---------------------------------------------------------------------------

class TestComputeSkillSeedHash:
    """Tests for _compute_skill_seed_hash."""

    def _base_skill(self, **overrides):
        data = {
            "category": "Content Creation",
            "source": "https://github.com/example/repo",
            "author": "example-org",
            "is_pinned": False,
        }
        data.update(overrides)
        return data

    def test_deterministic(self):
        """Same input produces same hash."""
        data = self._base_skill()
        h1 = _compute_skill_seed_hash(data)
        h2 = _compute_skill_seed_hash(data)
        assert h1 == h2

    def test_hash_format(self):
        """Hash is 64-character lowercase hex."""
        h = _compute_skill_seed_hash(self._base_skill())
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_content_different_hash(self):
        """Different category produces different hash."""
        h1 = _compute_skill_seed_hash(self._base_skill(category="Content Creation"))
        h2 = _compute_skill_seed_hash(self._base_skill(category="Media & Design"))
        assert h1 != h2

    def test_is_pinned_matters(self):
        """Pinned status affects hash."""
        h1 = _compute_skill_seed_hash(self._base_skill(is_pinned=False))
        h2 = _compute_skill_seed_hash(self._base_skill(is_pinned=True))
        assert h1 != h2

    def test_missing_fields_use_defaults(self):
        """Empty dict produces valid hash."""
        h = _compute_skill_seed_hash({})
        assert len(h) == 64

    def test_none_fields_same_as_missing(self):
        """None values treated same as missing (both normalize to empty string)."""
        h1 = _compute_skill_seed_hash({"category": None})
        h2 = _compute_skill_seed_hash({})
        assert h1 == h2

    def test_source_matters(self):
        """Different source produces different hash."""
        h1 = _compute_skill_seed_hash(self._base_skill(source="https://github.com/a/b"))
        h2 = _compute_skill_seed_hash(self._base_skill(source="https://github.com/c/d"))
        assert h1 != h2


# ---------------------------------------------------------------------------
# Helper: fake row with _mapping (mimics SQLAlchemy Row)
# ---------------------------------------------------------------------------

class _FakeRow:
    """Mimics a SQLAlchemy Row object with _mapping dict access."""

    def __init__(self, **kwargs):
        self._mapping = kwargs


# ---------------------------------------------------------------------------
# DB row conversion tests
# ---------------------------------------------------------------------------

class TestDbRowToAgentDict:
    """Tests for _db_row_to_agent_dict."""

    def test_mapping_access(self):
        """Works with SQLAlchemy-style _mapping dict."""
        row = _FakeRow(
            system_prompt="test prompt",
            description="test desc",
            skill_ids=["a", "b"],
            mcp_servers=["time"],
            builtin_tools=None,
            max_turns=60,
            model_provider="kimi",
            model_name="kimi-k2.5",
            executor_name="base",
        )
        result = _db_row_to_agent_dict(row)
        assert result["system_prompt"] == "test prompt"
        assert result["description"] == "test desc"
        assert result["skill_ids"] == ["a", "b"]
        assert result["builtin_tools"] is None
        assert result["max_turns"] == 60

    def test_json_string_parsing(self):
        """JSONB stored as string is parsed correctly."""
        row = _FakeRow(
            system_prompt="prompt",
            description="desc",
            skill_ids=json.dumps(["x", "y"]),
            mcp_servers=json.dumps(["time"]),
            builtin_tools=None,
            max_turns=30,
            model_provider=None,
            model_name=None,
            executor_name=None,
        )
        result = _db_row_to_agent_dict(row)
        assert result["skill_ids"] == ["x", "y"]
        assert result["mcp_servers"] == ["time"]


class TestDbRowToSkillSeedDict:
    """Tests for _db_row_to_skill_seed_dict."""

    def test_mapping_access(self):
        """Works with SQLAlchemy-style _mapping dict."""
        row = _FakeRow(
            category="Media & Design",
            source="https://github.com/test",
            author="test-author",
            is_pinned=True,
        )
        result = _db_row_to_skill_seed_dict(row)
        assert result["category"] == "Media & Design"
        assert result["source"] == "https://github.com/test"
        assert result["author"] == "test-author"
        assert result["is_pinned"] is True

    def test_none_fields_normalized_to_empty_string(self):
        """None values are normalized to empty string for consistent hash comparison."""
        row = _FakeRow(
            category=None,
            source=None,
            author=None,
            is_pinned=False,
        )
        result = _db_row_to_skill_seed_dict(row)
        assert result["category"] == ""
        assert result["source"] == ""
        assert result["author"] == ""


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

class TestSeedHashRoundTrip:
    """Verify that seed dict → hash == db row → dict → hash (round-trip consistency)."""

    def test_agent_round_trip(self):
        """Agent seed dict hashes the same as reconstructed dict from DB row."""
        seed = {
            "system_prompt": "You are a builder.",
            "description": "Build things",
            "skill_ids": ["skill-creator", "skill-evolver"],
            "mcp_servers": ["time", "tavily"],
            "builtin_tools": None,
            "max_turns": 90,
            "model_provider": "anthropic",
            "model_name": "claude-sonnet-4-5-20250929",
            "executor_name": None,
        }
        seed_hash = _compute_agent_seed_hash(seed)

        row = _FakeRow(**seed)
        db_dict = _db_row_to_agent_dict(row)
        db_hash = _compute_agent_seed_hash(db_dict)
        assert seed_hash == db_hash

    def test_agent_round_trip_with_json_strings(self):
        """Agent hash matches even when DB stores JSONB as strings."""
        seed = {
            "system_prompt": "Hello",
            "description": "Desc",
            "skill_ids": ["a", "b", "c"],
            "mcp_servers": ["time"],
            "builtin_tools": ["read", "write"],
            "max_turns": 60,
            "model_provider": None,
            "model_name": None,
            "executor_name": None,
        }
        seed_hash = _compute_agent_seed_hash(seed)

        # Simulate DB storing JSONB as strings
        row = _FakeRow(
            system_prompt="Hello",
            description="Desc",
            skill_ids=json.dumps(["a", "b", "c"]),
            mcp_servers=json.dumps(["time"]),
            builtin_tools=json.dumps(["read", "write"]),
            max_turns=60,
            model_provider=None,
            model_name=None,
            executor_name=None,
        )
        db_dict = _db_row_to_agent_dict(row)
        db_hash = _compute_agent_seed_hash(db_dict)
        assert seed_hash == db_hash

    def test_skill_round_trip(self):
        """Skill seed dict hashes the same as reconstructed dict from DB row."""
        seed = {
            "category": "Research & Knowledge",
            "source": "https://github.com/K-Dense-AI/repo",
            "author": "K-Dense-AI",
            "is_pinned": False,
        }
        seed_hash = _compute_skill_seed_hash(seed)

        row = _FakeRow(**seed)
        db_dict = _db_row_to_skill_seed_dict(row)
        db_hash = _compute_skill_seed_hash(db_dict)
        assert seed_hash == db_hash


# ---------------------------------------------------------------------------
# Integration tests: 4-case startup logic (requires PostgreSQL)
# ---------------------------------------------------------------------------

def _make_seed_agent(**overrides):
    """Create a minimal seed agent dict for testing."""
    data = {
        "name": f"test-seed-{uuid.uuid4().hex[:8]}",
        "description": "Seed agent for testing",
        "system_prompt": "You are a test agent.",
        "skill_ids": ["skill-a"],
        "mcp_servers": ["time"],
        "builtin_tools": None,
        "max_turns": 60,
        "is_system": True,
        "model_provider": None,
        "model_name": None,
        "executor_name": None,
    }
    data.update(overrides)
    return data


async def _insert_agent(session, agent_dict, seed_hash=None):
    """Insert an agent preset directly into DB for test setup."""
    agent_id = str(uuid.uuid4())
    skill_ids = json.dumps(agent_dict.get("skill_ids")) if agent_dict.get("skill_ids") is not None else None
    mcp_servers = json.dumps(agent_dict.get("mcp_servers")) if agent_dict.get("mcp_servers") is not None else None
    builtin_tools = json.dumps(agent_dict.get("builtin_tools")) if agent_dict.get("builtin_tools") is not None else None
    await session.execute(
        text("""
            INSERT INTO agent_presets (id, name, description, system_prompt,
                skill_ids, mcp_servers, builtin_tools, max_turns,
                model_provider, model_name, executor_name,
                seed_hash, is_system, is_published, created_at, updated_at)
            VALUES (:id, :name, :description, :system_prompt,
                :skill_ids, :mcp_servers, :builtin_tools, :max_turns,
                :model_provider, :model_name, :executor_name,
                :seed_hash, :is_system, FALSE, NOW(), NOW())
        """),
        {
            "id": agent_id,
            "name": agent_dict["name"],
            "description": agent_dict.get("description"),
            "system_prompt": agent_dict.get("system_prompt"),
            "skill_ids": skill_ids,
            "mcp_servers": mcp_servers,
            "builtin_tools": builtin_tools,
            "max_turns": agent_dict.get("max_turns", 60),
            "model_provider": agent_dict.get("model_provider"),
            "model_name": agent_dict.get("model_name"),
            "executor_name": agent_dict.get("executor_name"),
            "seed_hash": seed_hash,
            "is_system": agent_dict.get("is_system", True),
        },
    )
    await session.commit()
    return agent_id


async def _get_agent(session, name):
    """Fetch agent preset by name."""
    result = await session.execute(
        text("SELECT * FROM agent_presets WHERE name = :name"),
        {"name": name},
    )
    return result.fetchone()


async def _run_seed_for_agent(session, agent):
    """Call the real production _sync_one_seed_agent and flush.

    Thin wrapper that calls the actual production function, ensuring
    tests exercise the same code path as startup.
    """
    await _sync_one_seed_agent(session, agent)
    await session.flush()


class TestSeedAgentStartupLogic:
    """Integration tests for the 4-case agent seed startup logic."""

    @pytest.mark.asyncio
    async def test_case1_insert_new(self, db_session):
        """Case 1: agent not in DB → inserted with seed_hash."""
        agent = _make_seed_agent()
        await _run_seed_for_agent(db_session, agent)

        row = await _get_agent(db_session, agent["name"])
        assert row is not None
        m = row._mapping
        assert m["description"] == agent["description"]
        assert m["seed_hash"] == _compute_agent_seed_hash(agent)

    @pytest.mark.asyncio
    async def test_case2_backfill_null_hash_matching(self, db_session):
        """Case 2: existing record with NULL seed_hash, DB matches seed → backfill new_seed_hash."""
        agent = _make_seed_agent()
        await _insert_agent(db_session, agent, seed_hash=None)

        await _run_seed_for_agent(db_session, agent)

        row = await _get_agent(db_session, agent["name"])
        m = row._mapping
        assert m["seed_hash"] == _compute_agent_seed_hash(agent)

    @pytest.mark.asyncio
    async def test_case2_backfill_null_hash_diverged(self, db_session):
        """Case 2: existing record with NULL seed_hash, DB differs → backfill db_hash."""
        agent = _make_seed_agent()
        # Insert with different description so DB != seed
        modified = {**agent, "description": "User modified description"}
        await _insert_agent(db_session, modified, seed_hash=None)

        await _run_seed_for_agent(db_session, agent)

        row = await _get_agent(db_session, agent["name"])
        m = row._mapping
        # seed_hash should be hash of DB state (the modified version), not the seed
        expected_hash = _compute_agent_seed_hash(modified)
        assert m["seed_hash"] == expected_hash
        # Description should NOT be updated (Case 2 only backfills hash)
        assert m["description"] == "User modified description"

    @pytest.mark.asyncio
    async def test_case3_seed_unchanged_skip(self, db_session):
        """Case 3: seed_hash matches → no update."""
        agent = _make_seed_agent()
        seed_hash = _compute_agent_seed_hash(agent)
        await _insert_agent(db_session, agent, seed_hash=seed_hash)

        # Get original updated_at
        row_before = await _get_agent(db_session, agent["name"])
        updated_before = row_before._mapping["updated_at"]

        # Run seed with same data
        await _run_seed_for_agent(db_session, agent)

        row_after = await _get_agent(db_session, agent["name"])
        assert row_after._mapping["updated_at"] == updated_before

    @pytest.mark.asyncio
    async def test_case4a_seed_changed_user_didnt_edit(self, db_session):
        """Case 4a: seed changed, user didn't edit → DB updated."""
        agent_v1 = _make_seed_agent(description="Version 1")
        v1_hash = _compute_agent_seed_hash(agent_v1)
        await _insert_agent(db_session, agent_v1, seed_hash=v1_hash)

        # Seed updated to v2
        agent_v2 = {**agent_v1, "description": "Version 2"}
        await _run_seed_for_agent(db_session, agent_v2)

        row = await _get_agent(db_session, agent_v1["name"])
        m = row._mapping
        assert m["description"] == "Version 2"
        assert m["seed_hash"] == _compute_agent_seed_hash(agent_v2)

    @pytest.mark.asyncio
    async def test_case4b_seed_changed_user_edited(self, db_session):
        """Case 4b: seed changed, user edited → DB preserved, hash advanced."""
        agent_v1 = _make_seed_agent(description="Version 1")
        v1_hash = _compute_agent_seed_hash(agent_v1)

        # Insert with v1 hash, but user has changed description
        user_modified = {**agent_v1, "description": "User custom description"}
        await _insert_agent(db_session, user_modified, seed_hash=v1_hash)

        # Seed updated to v2
        agent_v2 = {**agent_v1, "description": "Version 2"}
        v2_hash = _compute_agent_seed_hash(agent_v2)
        await _run_seed_for_agent(db_session, agent_v2)

        row = await _get_agent(db_session, agent_v1["name"])
        m = row._mapping
        # User edit preserved
        assert m["description"] == "User custom description"
        # Hash advanced to v2 so we don't re-check every boot
        assert m["seed_hash"] == v2_hash

    @pytest.mark.asyncio
    async def test_case4b_subsequent_boot_skips(self, db_session):
        """After Case 4b advances the hash, next boot hits Case 3 (SKIP)."""
        agent_v1 = _make_seed_agent(description="V1")
        v1_hash = _compute_agent_seed_hash(agent_v1)
        user_modified = {**agent_v1, "description": "User edit"}
        await _insert_agent(db_session, user_modified, seed_hash=v1_hash)

        agent_v2 = {**agent_v1, "description": "V2"}
        v2_hash = _compute_agent_seed_hash(agent_v2)

        # First boot: Case 4b → advances hash
        await _run_seed_for_agent(db_session, agent_v2)
        row1 = await _get_agent(db_session, agent_v1["name"])
        assert row1._mapping["seed_hash"] == v2_hash

        # Second boot: same seed → Case 3 (SKIP), no change
        updated_before = row1._mapping["updated_at"]
        await _run_seed_for_agent(db_session, agent_v2)
        row2 = await _get_agent(db_session, agent_v1["name"])
        assert row2._mapping["updated_at"] == updated_before
        assert row2._mapping["description"] == "User edit"
