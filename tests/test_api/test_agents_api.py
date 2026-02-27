"""
Tests for Agent Presets CRUD API.

Endpoints tested:
- GET    /api/v1/agents
- GET    /api/v1/agents/{id}
- GET    /api/v1/agents/by-name/{name}
- POST   /api/v1/agents
- PUT    /api/v1/agents/{id}
- DELETE /api/v1/agents/{id}
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentPresetDB
from tests.factories import make_preset, make_skill

API = "/api/v1/agents"


class TestListPresets:
    """Tests for GET /api/v1/agents."""

    async def test_list_presets_empty(self, client: AsyncClient):
        """With no presets in the DB, should return an empty list."""
        response = await client.get(API)
        assert response.status_code == 200
        data = response.json()
        assert data["presets"] == []
        assert data["total"] == 0

    async def test_list_presets_returns_all(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """With one sample preset, should return a list of length 1."""
        response = await client.get(API)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["presets"][0]["name"] == "test-preset"

    async def test_list_presets_filter_by_system(
        self, client: AsyncClient, system_preset: AgentPresetDB
    ):
        """Filtering is_system=true should return only system presets."""
        response = await client.get(API, params={"is_system": True})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for preset in data["presets"]:
            assert preset["is_system"] is True

    async def test_list_presets_filter_by_user(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Filtering is_system=false should return only user presets."""
        response = await client.get(API, params={"is_system": False})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for preset in data["presets"]:
            assert preset["is_system"] is False


class TestCreatePreset:
    """Tests for POST /api/v1/agents."""

    async def test_create_preset(self, client: AsyncClient):
        """Creating a preset with valid data should return 200."""
        payload = {
            "name": "new-preset",
            "description": "Freshly created preset",
            "system_prompt": "You are helpful.",
            "skill_ids": ["pdf-to-md"],
            "mcp_servers": ["fetch"],
            "max_turns": 20,
        }
        response = await client.post(API, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "new-preset"
        assert data["description"] == "Freshly created preset"
        assert data["max_turns"] == 20
        assert data["is_system"] is False
        assert "id" in data
        assert "created_at" in data

    async def test_create_preset_duplicate_name(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Creating a preset with an already-existing name should return 400."""
        payload = {
            "name": sample_preset.name,
            "description": "Duplicate",
            "max_turns": 10,
        }
        response = await client.post(API, json=payload)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_create_preset_missing_name(self, client: AsyncClient):
        """Omitting the required 'name' field should return 422."""
        payload = {"description": "No name provided"}
        response = await client.post(API, json=payload)
        assert response.status_code == 422

    async def test_create_preset_name_too_long(self, client: AsyncClient):
        """A name exceeding max_length (128) should return 422."""
        payload = {"name": "x" * 200, "max_turns": 10}
        response = await client.post(API, json=payload)
        assert response.status_code == 422

    async def test_create_preset_max_turns_bounds(self, client: AsyncClient):
        """max_turns outside [1, 60000] should return 422."""
        # max_turns = 0 (below minimum of 1)
        response = await client.post(
            API, json={"name": "low-turns", "max_turns": 0}
        )
        assert response.status_code == 422

        # max_turns = 60001 (above maximum of 60000)
        response = await client.post(
            API, json={"name": "high-turns", "max_turns": 60001}
        )
        assert response.status_code == 422


class TestGetPreset:
    """Tests for GET /api/v1/agents/{id} and GET /api/v1/agents/by-name/{name}."""

    async def test_get_preset_by_id(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Fetching by valid ID should return 200 with correct data."""
        response = await client.get(f"{API}/{sample_preset.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_preset.id
        assert data["name"] == sample_preset.name

    async def test_get_preset_not_found(self, client: AsyncClient):
        """Fetching a nonexistent ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"{API}/{fake_id}")
        assert response.status_code == 404

    async def test_get_preset_by_name(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Fetching by valid name should return 200 with correct data."""
        response = await client.get(f"{API}/by-name/{sample_preset.name}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_preset.name
        assert data["id"] == sample_preset.id

    async def test_get_preset_by_name_not_found(self, client: AsyncClient):
        """Fetching a nonexistent name should return 404."""
        response = await client.get(f"{API}/by-name/nope")
        assert response.status_code == 404


class TestUpdatePreset:
    """Tests for PUT /api/v1/agents/{id}."""

    async def test_update_preset(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Updating a user preset should return 200 with updated fields."""
        response = await client.put(
            f"{API}/{sample_preset.id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["id"] == sample_preset.id

    async def test_update_preset_system_allowed(
        self, client: AsyncClient, system_preset: AgentPresetDB
    ):
        """Updating a system preset should be allowed."""
        response = await client.put(
            f"{API}/{system_preset.id}",
            json={"description": "Updated system preset description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated system preset description"
        assert data["is_system"] is True

    async def test_update_preset_not_found(self, client: AsyncClient):
        """Updating a nonexistent preset should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.put(
            f"{API}/{fake_id}",
            json={"description": "Ghost"},
        )
        assert response.status_code == 404


class TestDeletePreset:
    """Tests for DELETE /api/v1/agents/{id}."""

    async def test_delete_preset(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Deleting a user preset should return 200."""
        response = await client.delete(f"{API}/{sample_preset.id}")
        assert response.status_code == 200

        # Verify it is gone
        get_response = await client.get(f"{API}/{sample_preset.id}")
        assert get_response.status_code == 404

    async def test_delete_preset_system_forbidden(
        self, client: AsyncClient, system_preset: AgentPresetDB
    ):
        """Deleting a system preset should return 403."""
        response = await client.delete(f"{API}/{system_preset.id}")
        assert response.status_code == 403
        assert "system" in response.json()["detail"].lower()


class TestPublishPreset:
    """Tests for POST /api/v1/agents/{id}/publish and /unpublish."""

    async def test_publish_preset(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Publishing a user preset returns is_published=True."""
        response = await client.post(
            f"{API}/{sample_preset.id}/publish",
            json={"api_response_mode": "streaming"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_published"] is True
        assert data["id"] == sample_preset.id

    async def test_publish_system_preset_forbidden(
        self, client: AsyncClient, system_preset: AgentPresetDB
    ):
        """Publishing a system preset returns 403."""
        response = await client.post(
            f"{API}/{system_preset.id}/publish",
            json={"api_response_mode": "streaming"}
        )
        assert response.status_code == 403
        assert "system" in response.json()["detail"].lower()

    async def test_publish_nonexistent_404(self, client: AsyncClient):
        """Publishing a nonexistent preset returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"{API}/{fake_id}/publish",
            json={"api_response_mode": "streaming"}
        )
        assert response.status_code == 404

    async def test_unpublish_preset(
        self, client: AsyncClient, sample_preset: AgentPresetDB
    ):
        """Unpublishing a preset returns is_published=False."""
        # First publish, then unpublish
        await client.post(
            f"{API}/{sample_preset.id}/publish",
            json={"api_response_mode": "streaming"}
        )

        response = await client.post(f"{API}/{sample_preset.id}/unpublish")
        assert response.status_code == 200
        data = response.json()
        assert data["is_published"] is False
        assert data["id"] == sample_preset.id


class TestNullSkillIdsNormalization:
    """Tests that null skill_ids in DB is normalized to all skill names in API responses."""

    @pytest_asyncio.fixture
    async def skills_in_db(self, db_session: AsyncSession):
        """Create two user skills and one meta skill in the database."""
        s1 = make_skill(name="skill-alpha", description="Alpha")
        s2 = make_skill(name="skill-beta", description="Beta")
        s3 = make_skill(name="skill-creator", description="Meta", skill_type="meta")
        db_session.add_all([s1, s2, s3])
        await db_session.flush()
        return [s1, s2, s3]

    @pytest_asyncio.fixture
    async def preset_with_null_skills(self, db_session: AsyncSession):
        """Create a preset with skill_ids=None (means 'all skills')."""
        preset = make_preset(name="null-skills-preset", skill_ids=None)
        db_session.add(preset)
        await db_session.flush()
        return preset

    @pytest_asyncio.fixture
    async def preset_with_explicit_skills(self, db_session: AsyncSession):
        """Create a preset with explicit skill_ids list."""
        preset = make_preset(name="explicit-skills-preset", skill_ids=["skill-alpha"])
        db_session.add(preset)
        await db_session.flush()
        return preset

    async def test_get_by_id_null_skills_returns_all(
        self, client: AsyncClient, skills_in_db, preset_with_null_skills
    ):
        """GET by ID: null skill_ids should be normalized to all skill names."""
        response = await client.get(f"{API}/{preset_with_null_skills.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["skill_ids"] is not None
        assert set(data["skill_ids"]) >= {"skill-alpha", "skill-beta"}

    async def test_get_by_name_null_skills_returns_all(
        self, client: AsyncClient, skills_in_db, preset_with_null_skills
    ):
        """GET by name: null skill_ids should be normalized to all skill names."""
        response = await client.get(f"{API}/by-name/null-skills-preset")
        assert response.status_code == 200
        data = response.json()
        assert data["skill_ids"] is not None
        assert set(data["skill_ids"]) >= {"skill-alpha", "skill-beta"}

    async def test_list_null_skills_returns_all(
        self, client: AsyncClient, skills_in_db, preset_with_null_skills
    ):
        """GET list: null skill_ids should be normalized to all skill names."""
        response = await client.get(API)
        assert response.status_code == 200
        presets = response.json()["presets"]
        matched = [p for p in presets if p["id"] == preset_with_null_skills.id]
        assert len(matched) == 1
        assert matched[0]["skill_ids"] is not None
        assert set(matched[0]["skill_ids"]) >= {"skill-alpha", "skill-beta"}

    async def test_explicit_skills_unchanged(
        self, client: AsyncClient, skills_in_db, preset_with_explicit_skills
    ):
        """Explicit skill_ids should be returned as-is, not expanded."""
        response = await client.get(f"{API}/{preset_with_explicit_skills.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["skill_ids"] == ["skill-alpha"]

    async def test_update_preserves_normalization(
        self, client: AsyncClient, skills_in_db, preset_with_null_skills
    ):
        """PUT that doesn't touch skill_ids should still normalize null in response."""
        response = await client.put(
            f"{API}/{preset_with_null_skills.id}",
            json={"description": "Updated desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["skill_ids"] is not None
        assert set(data["skill_ids"]) >= {"skill-alpha", "skill-beta"}

    async def test_meta_skills_included_in_normalization(
        self, client: AsyncClient, skills_in_db, preset_with_null_skills
    ):
        """Normalized skill_ids should include both user and meta skills."""
        response = await client.get(f"{API}/{preset_with_null_skills.id}")
        assert response.status_code == 200
        data = response.json()
        assert "skill-creator" in data["skill_ids"]
        assert "skill-alpha" in data["skill_ids"]
        assert "skill-beta" in data["skill_ids"]

    async def test_normalized_skills_sorted(
        self, client: AsyncClient, skills_in_db, preset_with_null_skills
    ):
        """Normalized skill_ids should be sorted alphabetically."""
        response = await client.get(f"{API}/{preset_with_null_skills.id}")
        assert response.status_code == 200
        skill_ids = response.json()["skill_ids"]
        assert skill_ids == sorted(skill_ids)
