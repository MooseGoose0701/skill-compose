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
