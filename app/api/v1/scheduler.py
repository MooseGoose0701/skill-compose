"""
Scheduled Tasks API endpoints.

CRUD operations for scheduled tasks, plus run-now, pause/resume, and run history.
"""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ScheduledTaskDB, TaskRunLogDB, AgentPresetDB, generate_uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


# === Pydantic Schemas ===

class ScheduledTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    agent_id: str
    prompt: str = Field(..., min_length=1)
    schedule_type: str = Field(..., pattern="^(cron|interval|once)$")
    schedule_value: str = Field(..., min_length=1)
    context_mode: str = Field(default="isolated", pattern="^(isolated|session)$")
    max_runs: Optional[int] = Field(default=None, ge=1)


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    prompt: Optional[str] = Field(default=None, min_length=1)
    schedule_type: Optional[str] = Field(default=None, pattern="^(cron|interval|once)$")
    schedule_value: Optional[str] = Field(default=None, min_length=1)
    context_mode: Optional[str] = Field(default=None, pattern="^(isolated|session)$")
    max_runs: Optional[int] = Field(default=None, ge=1)


class ScheduledTaskResponse(BaseModel):
    id: str
    name: str
    agent_id: str
    agent_name: Optional[str] = None
    prompt: str
    schedule_type: str
    schedule_value: str
    context_mode: str
    session_id: Optional[str] = None
    channel_binding_id: Optional[str] = None
    status: str
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    max_runs: Optional[int] = None
    run_count: int
    created_at: str
    updated_at: str


class TaskRunLogResponse(BaseModel):
    id: str
    task_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str
    result_summary: Optional[str] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: str


def _task_to_response(task: ScheduledTaskDB, agent_name: str = None) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "agent_id": task.agent_id,
        "agent_name": agent_name,
        "prompt": task.prompt,
        "schedule_type": task.schedule_type,
        "schedule_value": task.schedule_value,
        "context_mode": task.context_mode,
        "session_id": task.session_id,
        "channel_binding_id": task.channel_binding_id,
        "status": task.status,
        "next_run": task.next_run.isoformat() if task.next_run else None,
        "last_run": task.last_run.isoformat() if task.last_run else None,
        "max_runs": task.max_runs,
        "run_count": task.run_count,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _run_log_to_response(log: TaskRunLogDB) -> dict:
    return {
        "id": log.id,
        "task_id": log.task_id,
        "started_at": log.started_at.isoformat(),
        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        "duration_ms": log.duration_ms,
        "status": log.status,
        "result_summary": log.result_summary,
        "error": log.error,
        "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat(),
    }


# === Endpoints ===

@router.get("")
async def list_scheduled_tasks(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all scheduled tasks."""
    query = select(ScheduledTaskDB)
    if status:
        query = query.where(ScheduledTaskDB.status == status)
    query = query.order_by(ScheduledTaskDB.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()

    # Batch load agent names
    agent_ids = list(set(t.agent_id for t in tasks))
    agent_names = {}
    if agent_ids:
        agent_result = await db.execute(
            select(AgentPresetDB.id, AgentPresetDB.name).where(
                AgentPresetDB.id.in_(agent_ids)
            )
        )
        agent_names = {row[0]: row[1] for row in agent_result.fetchall()}

    return [_task_to_response(t, agent_names.get(t.agent_id)) for t in tasks]


@router.get("/{task_id}")
async def get_scheduled_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a scheduled task by ID."""
    result = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    # Load agent name
    agent_name = None
    agent_result = await db.execute(
        select(AgentPresetDB.name).where(AgentPresetDB.id == task.agent_id)
    )
    row = agent_result.scalar_one_or_none()
    if row:
        agent_name = row

    return _task_to_response(task, agent_name)


@router.post("", status_code=201)
async def create_scheduled_task(
    data: ScheduledTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new scheduled task."""
    from app.services.scheduler import validate_schedule, _calculate_next_run

    # Validate agent exists
    agent_result = await db.execute(
        select(AgentPresetDB).where(AgentPresetDB.id == data.agent_id)
    )
    if not agent_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent preset not found")

    # Validate schedule
    error = validate_schedule(data.schedule_type, data.schedule_value)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Check name uniqueness
    existing = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Task name '{data.name}' already exists")

    # Calculate initial next_run
    next_run = _calculate_next_run(data.schedule_type, data.schedule_value)

    now = datetime.utcnow()
    task = ScheduledTaskDB(
        id=generate_uuid(),
        name=data.name,
        agent_id=data.agent_id,
        prompt=data.prompt,
        schedule_type=data.schedule_type,
        schedule_value=data.schedule_value,
        context_mode=data.context_mode,
        max_runs=data.max_runs,
        next_run=next_run,
        status="active",
        run_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return _task_to_response(task)


@router.put("/{task_id}")
async def update_scheduled_task(
    task_id: str,
    data: ScheduledTaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled task."""
    from app.services.scheduler import validate_schedule, _calculate_next_run

    result = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    # Apply updates
    update_fields = data.model_dump(exclude_unset=True)

    # If schedule changed, validate and recalculate
    schedule_type = update_fields.get("schedule_type", task.schedule_type)
    schedule_value = update_fields.get("schedule_value", task.schedule_value)

    if "schedule_type" in update_fields or "schedule_value" in update_fields:
        error = validate_schedule(schedule_type, schedule_value)
        if error:
            raise HTTPException(status_code=400, detail=error)
        task.next_run = _calculate_next_run(schedule_type, schedule_value)

    # Check name uniqueness if changing
    if "name" in update_fields and update_fields["name"] != task.name:
        existing = await db.execute(
            select(ScheduledTaskDB).where(ScheduledTaskDB.name == update_fields["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Task name '{update_fields['name']}' already exists")

    for key, value in update_fields.items():
        setattr(task, key, value)

    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)

    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
async def delete_scheduled_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled task and its run logs."""
    result = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    await db.delete(task)
    await db.commit()


@router.post("/{task_id}/run-now")
async def run_task_now(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Execute a scheduled task immediately."""
    result = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    from app.services.scheduler import TaskScheduler
    scheduler = TaskScheduler()
    run_log_id = await scheduler.execute_task_async(task_id)

    return {"message": "Task execution started", "run_log_id": run_log_id}


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Pause a scheduled task."""
    result = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    if task.status != "active":
        raise HTTPException(status_code=400, detail="Only active tasks can be paused")

    task.status = "paused"
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)

    return _task_to_response(task)


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused scheduled task."""
    from app.services.scheduler import _calculate_next_run

    result = await db.execute(
        select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    if task.status != "paused":
        raise HTTPException(status_code=400, detail="Only paused tasks can be resumed")

    task.status = "active"
    task.next_run = _calculate_next_run(task.schedule_type, task.schedule_value)
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)

    return _task_to_response(task)


@router.get("/{task_id}/runs")
async def list_task_runs(
    task_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List run logs for a scheduled task."""
    # Verify task exists
    task_result = await db.execute(
        select(ScheduledTaskDB.id).where(ScheduledTaskDB.id == task_id)
    )
    if not task_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    result = await db.execute(
        select(TaskRunLogDB)
        .where(TaskRunLogDB.task_id == task_id)
        .order_by(TaskRunLogDB.started_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [_run_log_to_response(log) for log in logs]
