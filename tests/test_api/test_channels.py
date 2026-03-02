"""Unit tests for Channels API."""
import pytest

from tests.factories import make_preset, make_channel_binding


@pytest.mark.asyncio
class TestChannelsAPI:
    """Channel bindings CRUD tests."""

    async def test_list_empty(self, client):
        resp = await client.get("/api/v1/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["bindings"] == []
        assert data["total"] == 0

    async def test_create_binding(self, client, db_session):
        preset = make_preset(name="chan-agent")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "chat-001",
            "name": "Test Webhook",
            "agent_id": preset.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Webhook"
        assert data["enabled"] is True

    async def test_create_binding_invalid_agent(self, client):
        resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "chat-002",
            "name": "Bad Binding",
            "agent_id": "nonexistent",
        })
        assert resp.status_code == 400

    async def test_create_duplicate_binding(self, client, db_session):
        preset = make_preset(name="chan-agent-2")
        db_session.add(preset)
        await db_session.commit()

        await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "dup-chat",
            "name": "First",
            "agent_id": preset.id,
        })

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "dup-chat",
            "name": "Second",
            "agent_id": preset.id,
        })
        assert resp.status_code == 409

    async def test_get_binding(self, client, db_session):
        preset = make_preset(name="chan-agent-3")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/channels", json={
            "channel_type": "telegram",
            "external_id": "tg-123",
            "name": "TG Bot",
            "agent_id": preset.id,
        })
        binding_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/channels/{binding_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "TG Bot"

    async def test_get_binding_not_found(self, client):
        resp = await client.get("/api/v1/channels/nonexistent")
        assert resp.status_code == 404

    async def test_toggle_binding(self, client, db_session):
        preset = make_preset(name="chan-agent-4")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "toggle-chat",
            "name": "Toggle Test",
            "agent_id": preset.id,
        })
        binding_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/channels/{binding_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        resp = await client.post(f"/api/v1/channels/{binding_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    async def test_delete_binding(self, client, db_session):
        preset = make_preset(name="chan-agent-5")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "del-chat",
            "name": "Delete Me",
            "agent_id": preset.id,
        })
        binding_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/channels/{binding_id}")
        assert resp.status_code == 200

        resp = await client.get(f"/api/v1/channels/{binding_id}")
        assert resp.status_code == 404

    async def test_messages_empty(self, client, db_session):
        preset = make_preset(name="chan-agent-6")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "external_id": "msg-chat",
            "name": "Message Test",
            "agent_id": preset.id,
        })
        binding_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/channels/{binding_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["total"] == 0

    async def test_adapters_status(self, client):
        resp = await client.get("/api/v1/channels/adapters")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestGlobalBindingsAPI:
    """Tests for global Feishu binding support (external_id='*')."""

    async def test_create_global_binding(self, client, db_session):
        """Creating a Feishu binding without external_id should produce a global binding."""
        preset = make_preset(name="global-agent-1")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "name": "Global Feishu",
            "agent_id": preset.id,
            "config": {"app_id": "cli_global_001", "app_secret": "secret123"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["external_id"] == "*"
        assert data["is_global"] is True

    async def test_create_global_binding_explicit_star(self, client, db_session):
        """Creating with external_id='*' explicitly should also work."""
        preset = make_preset(name="global-agent-2")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "external_id": "*",
            "name": "Global Feishu Explicit",
            "agent_id": preset.id,
            "config": {"app_id": "cli_global_002", "app_secret": "secret456"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["external_id"] == "*"
        assert data["is_global"] is True

    async def test_global_binding_feishu_only(self, client, db_session):
        """Global bindings should be rejected for non-Feishu channel types."""
        preset = make_preset(name="global-agent-3")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "webhook",
            "name": "Global Webhook",
            "agent_id": preset.id,
        })
        assert resp.status_code == 400
        assert "only supported for Feishu" in resp.json()["detail"]

    async def test_global_binding_requires_app_id(self, client, db_session):
        """Global Feishu bindings must have app_id in config."""
        preset = make_preset(name="global-agent-4")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "name": "Global No AppId",
            "agent_id": preset.id,
            "config": {"app_secret": "secret789"},
        })
        assert resp.status_code == 400
        assert "app_id" in resp.json()["detail"]

    async def test_duplicate_global_binding_rejected(self, client, db_session):
        """Two global bindings for the same app_id should be rejected."""
        preset = make_preset(name="global-agent-5")
        db_session.add(preset)
        await db_session.commit()

        resp1 = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "name": "Global Feishu First",
            "agent_id": preset.id,
            "config": {"app_id": "cli_dup_global", "app_secret": "sec1"},
        })
        assert resp1.status_code == 200

        resp2 = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "name": "Global Feishu Duplicate",
            "agent_id": preset.id,
            "config": {"app_id": "cli_dup_global", "app_secret": "sec2"},
        })
        assert resp2.status_code == 409

    async def test_specific_binding_is_not_global(self, client, db_session):
        """A binding with a specific external_id should have is_global=False."""
        preset = make_preset(name="global-agent-6")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "external_id": "oc_specific_001",
            "name": "Specific Feishu",
            "agent_id": preset.id,
            "config": {"app_id": "cli_specific_001", "app_secret": "sec3"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_global"] is False
        assert data["external_id"] == "oc_specific_001"

    async def test_global_and_specific_coexist(self, client, db_session):
        """A global binding and specific binding for the same app can coexist."""
        preset = make_preset(name="global-agent-7")
        db_session.add(preset)
        await db_session.commit()

        # Create global
        resp1 = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "name": "Global Coexist",
            "agent_id": preset.id,
            "config": {"app_id": "cli_coexist", "app_secret": "sec4"},
        })
        assert resp1.status_code == 200
        assert resp1.json()["is_global"] is True

        # Create specific for same app
        resp2 = await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "external_id": "oc_coexist_001",
            "name": "Specific Coexist",
            "agent_id": preset.id,
            "config": {"app_id": "cli_coexist", "app_secret": "sec5"},
        })
        assert resp2.status_code == 200
        assert resp2.json()["is_global"] is False

    async def test_is_global_in_list_response(self, client, db_session):
        """The is_global field should appear in list responses."""
        preset = make_preset(name="global-agent-8")
        db_session.add(preset)
        await db_session.commit()

        await client.post("/api/v1/channels", json={
            "channel_type": "feishu",
            "name": "List Global",
            "agent_id": preset.id,
            "config": {"app_id": "cli_list_global", "app_secret": "sec6"},
        })

        resp = await client.get("/api/v1/channels")
        assert resp.status_code == 200
        bindings = resp.json()["bindings"]
        global_binding = next(b for b in bindings if b["name"] == "List Global")
        assert global_binding["is_global"] is True
