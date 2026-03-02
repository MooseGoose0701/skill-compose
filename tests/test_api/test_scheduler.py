"""Unit tests for Scheduled Tasks API."""
import pytest
import pytest_asyncio

from tests.factories import make_preset, make_scheduled_task, make_task_run_log, make_channel_binding


@pytest.mark.asyncio
class TestSchedulerAPI:
    """Scheduled tasks CRUD tests."""

    async def test_list_empty(self, client):
        resp = await client.get("/api/v1/scheduled-tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_task(self, client, db_session):
        # Create agent preset first
        preset = make_preset(name="sched-agent")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "my-task",
            "agent_id": preset.id,
            "prompt": "Say hello",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-task"
        assert data["status"] == "active"
        assert data["next_run"] is not None

    async def test_create_task_invalid_agent(self, client):
        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "bad-task",
            "agent_id": "nonexistent",
            "prompt": "test",
            "schedule_type": "interval",
            "schedule_value": "60",
        })
        assert resp.status_code == 400

    async def test_create_task_invalid_cron(self, client, db_session):
        preset = make_preset(name="sched-agent-2")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "bad-cron",
            "agent_id": preset.id,
            "prompt": "test",
            "schedule_type": "cron",
            "schedule_value": "invalid",
        })
        assert resp.status_code == 400

    async def test_create_duplicate_name(self, client, db_session):
        preset = make_preset(name="sched-agent-3")
        db_session.add(preset)
        await db_session.commit()

        resp1 = await client.post("/api/v1/scheduled-tasks", json={
            "name": "dup-task",
            "agent_id": preset.id,
            "prompt": "test",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/scheduled-tasks", json={
            "name": "dup-task",
            "agent_id": preset.id,
            "prompt": "test 2",
            "schedule_type": "interval",
            "schedule_value": "7200",
        })
        assert resp2.status_code == 409

    async def test_get_task(self, client, db_session):
        preset = make_preset(name="sched-agent-4")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "get-me",
            "agent_id": preset.id,
            "prompt": "hello",
            "schedule_type": "interval",
            "schedule_value": "60",
        })
        task_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/scheduled-tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"

    async def test_get_task_not_found(self, client):
        resp = await client.get("/api/v1/scheduled-tasks/nonexistent")
        assert resp.status_code == 404

    async def test_delete_task(self, client, db_session):
        preset = make_preset(name="sched-agent-5")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "delete-me",
            "agent_id": preset.id,
            "prompt": "hello",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })
        task_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/scheduled-tasks/{task_id}")
        assert resp.status_code == 204

    async def test_pause_and_resume(self, client, db_session):
        preset = make_preset(name="sched-agent-6")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "pause-me",
            "agent_id": preset.id,
            "prompt": "hello",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })
        task_id = create_resp.json()["id"]

        # Pause
        resp = await client.post(f"/api/v1/scheduled-tasks/{task_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

        # Resume
        resp = await client.post(f"/api/v1/scheduled-tasks/{task_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_list_with_status_filter(self, client, db_session):
        preset = make_preset(name="sched-agent-7")
        db_session.add(preset)
        await db_session.commit()

        await client.post("/api/v1/scheduled-tasks", json={
            "name": "filter-task",
            "agent_id": preset.id,
            "prompt": "hello",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })

        resp = await client.get("/api/v1/scheduled-tasks?status=active")
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["status"] == "active" for t in tasks)

    async def test_list_runs_empty(self, client, db_session):
        preset = make_preset(name="sched-agent-8")
        db_session.add(preset)
        await db_session.commit()

        create_resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "runs-task",
            "agent_id": preset.id,
            "prompt": "hello",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })
        task_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/scheduled-tasks/{task_id}/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_cron_task(self, client, db_session):
        preset = make_preset(name="sched-agent-9")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "cron-task",
            "agent_id": preset.id,
            "prompt": "daily report",
            "schedule_type": "cron",
            "schedule_value": "0 9 * * *",
        })
        assert resp.status_code == 201
        assert resp.json()["schedule_type"] == "cron"
        assert resp.json()["next_run"] is not None

    async def test_create_task_with_global_binding_and_delivery_to(self, client, db_session):
        """Global binding + delivery_to should succeed."""
        preset = make_preset(name="sched-agent-global-ok")
        binding = make_channel_binding(
            name="global-feishu",
            channel_type="feishu",
            external_id="*",
            agent_id=preset.id,
        )
        db_session.add(preset)
        db_session.add(binding)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "global-task-ok",
            "agent_id": preset.id,
            "prompt": "Report",
            "schedule_type": "interval",
            "schedule_value": "3600",
            "channel_binding_id": binding.id,
            "delivery_to": "oc_target_chat_123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["delivery_to"] == "oc_target_chat_123"
        assert data["channel_binding_id"] == binding.id

    async def test_create_task_with_global_binding_no_delivery_to_fails(self, client, db_session):
        """Global binding without delivery_to should fail with 400."""
        preset = make_preset(name="sched-agent-global-fail")
        binding = make_channel_binding(
            name="global-feishu-2",
            channel_type="feishu",
            external_id="*",
            agent_id=preset.id,
        )
        db_session.add(preset)
        db_session.add(binding)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "global-task-fail",
            "agent_id": preset.id,
            "prompt": "Report",
            "schedule_type": "interval",
            "schedule_value": "3600",
            "channel_binding_id": binding.id,
        })
        assert resp.status_code == 400
        assert "delivery_to" in resp.json()["detail"].lower()

    async def test_create_task_with_delivery_to_override(self, client, db_session):
        """Specific binding + delivery_to override should succeed."""
        preset = make_preset(name="sched-agent-override")
        binding = make_channel_binding(
            name="specific-feishu",
            channel_type="feishu",
            external_id="oc_original_chat",
            agent_id=preset.id,
        )
        db_session.add(preset)
        db_session.add(binding)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "override-task",
            "agent_id": preset.id,
            "prompt": "Report",
            "schedule_type": "interval",
            "schedule_value": "3600",
            "channel_binding_id": binding.id,
            "delivery_to": "oc_different_chat",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["delivery_to"] == "oc_different_chat"

    async def test_update_clear_delivery_to_with_global_binding_fails(self, client, db_session):
        """Clearing delivery_to on a task with global binding should fail."""
        preset = make_preset(name="sched-agent-clear-fail")
        binding = make_channel_binding(
            name="global-feishu-3",
            channel_type="feishu",
            external_id="*",
            agent_id=preset.id,
        )
        db_session.add(preset)
        db_session.add(binding)
        await db_session.commit()

        # Create task with global binding + delivery_to
        create_resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "clear-fail-task",
            "agent_id": preset.id,
            "prompt": "Report",
            "schedule_type": "interval",
            "schedule_value": "3600",
            "channel_binding_id": binding.id,
            "delivery_to": "oc_target_123",
        })
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        # Try to clear delivery_to — should fail
        resp = await client.put(f"/api/v1/scheduled-tasks/{task_id}", json={
            "delivery_to": None,
        })
        assert resp.status_code == 400
        assert "delivery_to" in resp.json()["detail"].lower()

    async def test_create_task_delivery_to_without_channel_fails(self, client, db_session):
        """delivery_to without channel_binding_id should fail with 400."""
        preset = make_preset(name="sched-agent-no-channel")
        db_session.add(preset)
        await db_session.commit()

        resp = await client.post("/api/v1/scheduled-tasks", json={
            "name": "orphan-delivery",
            "agent_id": preset.id,
            "prompt": "Report",
            "schedule_type": "interval",
            "schedule_value": "3600",
            "delivery_to": "oc_some_chat",
        })
        assert resp.status_code == 400
        assert "delivery_to" in resp.json()["detail"].lower()
