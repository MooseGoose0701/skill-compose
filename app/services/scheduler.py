"""
Task Scheduler service for periodic agent execution.

Polls the database for due tasks and executes them via SkillsAgent.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def _calculate_next_run(
    schedule_type: str,
    schedule_value: str,
    from_time: Optional[datetime] = None,
) -> Optional[datetime]:
    """Calculate the next run time based on schedule type.

    Args:
        schedule_type: 'cron', 'interval', or 'once'
        schedule_value: cron expression, interval in seconds, or ISO datetime
        from_time: base time for calculation (defaults to now)
    """
    now = from_time or datetime.utcnow()

    if schedule_type == "cron":
        from croniter import croniter
        cron = croniter(schedule_value, now)
        return cron.get_next(datetime)

    elif schedule_type == "interval":
        seconds = int(schedule_value)
        return now + timedelta(seconds=seconds)

    elif schedule_type == "once":
        # ISO datetime string
        run_at = datetime.fromisoformat(schedule_value.replace("Z", "+00:00").replace("+00:00", ""))
        if run_at > now:
            return run_at
        return None

    return None


def validate_schedule(schedule_type: str, schedule_value: str) -> str | None:
    """Validate schedule configuration. Returns error message or None."""
    if schedule_type not in ("cron", "interval", "once"):
        return f"Invalid schedule_type: {schedule_type}. Must be cron, interval, or once."

    if schedule_type == "cron":
        try:
            from croniter import croniter
            croniter(schedule_value)
        except (ValueError, KeyError) as e:
            return f"Invalid cron expression: {e}"

    elif schedule_type == "interval":
        try:
            val = int(schedule_value)
            if val < 10:
                return "Interval must be at least 10 seconds"
        except ValueError:
            return "Interval must be an integer (seconds)"

    elif schedule_type == "once":
        try:
            datetime.fromisoformat(schedule_value.replace("Z", "+00:00").replace("+00:00", ""))
        except ValueError:
            return "Invalid ISO datetime for once schedule"

    return None


class TaskScheduler:
    """Singleton scheduler that polls for due tasks and executes them."""

    _instance = None
    _task: Optional[asyncio.Task] = None
    _running: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def start(self):
        """Start the scheduler polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("TaskScheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("TaskScheduler stopped")

    async def _loop(self):
        """Main polling loop."""
        from app.config import settings
        interval = settings.scheduler_poll_interval

        while self._running:
            try:
                await self._poll_and_execute()
            except Exception as e:
                logger.error(f"Scheduler poll error: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def _poll_and_execute(self):
        """Find and execute due tasks."""
        from sqlalchemy import select, update
        from app.db.database import AsyncSessionLocal
        from app.db.models import ScheduledTaskDB, TaskRunLogDB, generate_uuid

        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            # Find due tasks
            result = await session.execute(
                select(ScheduledTaskDB).where(
                    ScheduledTaskDB.status == "active",
                    ScheduledTaskDB.next_run <= now,
                )
            )
            due_tasks = result.scalars().all()

            for task in due_tasks:
                try:
                    # Calculate next run
                    next_run = _calculate_next_run(task.schedule_type, task.schedule_value, now)

                    # Update task next_run and last_run
                    task.next_run = next_run
                    task.last_run = now
                    task.run_count += 1

                    # Check if max_runs reached
                    if task.max_runs and task.run_count >= task.max_runs:
                        task.status = "completed"
                    elif task.schedule_type == "once":
                        task.status = "completed"

                    # Create run log
                    run_log = TaskRunLogDB(
                        id=generate_uuid(),
                        task_id=task.id,
                        started_at=now,
                        status="running",
                    )
                    session.add(run_log)
                    await session.commit()

                    # Execute in background thread
                    task_id = task.id
                    run_log_id = run_log.id
                    thread = threading.Thread(
                        target=self._execute_task,
                        args=(task_id, run_log_id),
                        daemon=True,
                    )
                    thread.start()

                    logger.info(f"Scheduled task '{task.name}' (id={task.id}) dispatched, run_log={run_log_id}")

                except Exception as e:
                    logger.error(f"Error dispatching task {task.id}: {e}", exc_info=True)

    def _execute_task(self, task_id: str, run_log_id: str):
        """Execute a scheduled task in a background thread."""
        from app.db.database import SyncSessionLocal
        from app.db.models import (
            ScheduledTaskDB, TaskRunLogDB, AgentPresetDB,
            AgentTraceDB, PublishedSessionDB, generate_uuid,
        )
        from app.agent.run_agent import SkillsAgent

        start_time = time.time()
        session = SyncSessionLocal()

        try:
            # Load task and agent preset
            task = session.get(ScheduledTaskDB, task_id)
            if not task:
                logger.error(f"Scheduled task {task_id} not found")
                return

            preset = session.get(AgentPresetDB, task.agent_id)
            if not preset:
                logger.error(f"Agent preset {task.agent_id} not found for task {task_id}")
                self._update_run_log(session, run_log_id, "failed", error="Agent preset not found")
                return

            # Build conversation history for session mode
            conversation_history = None
            if task.context_mode == "session" and task.session_id:
                pub_session = session.get(PublishedSessionDB, task.session_id)
                if pub_session and pub_session.agent_context:
                    conversation_history = pub_session.agent_context

            # Create agent
            agent = SkillsAgent(
                system_prompt=preset.system_prompt,
                skill_names=preset.skill_ids,
                mcp_servers=preset.mcp_servers,
                builtin_tool_names=preset.builtin_tools,
                max_turns=preset.max_turns or 60,
                model_provider=preset.model_provider,
                model_name=preset.model_name,
                executor_name=preset.executor_name,
            )

            # Run agent
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    agent.run(task.prompt, conversation_history=conversation_history)
                )
            finally:
                loop.close()

            duration_ms = int((time.time() - start_time) * 1000)

            # Save trace
            trace = AgentTraceDB(
                id=generate_uuid(),
                request=task.prompt,
                skills_used=list(result.skills_used) if result.skills_used else [],
                model_provider=preset.model_provider or "kimi",
                model=result.model or preset.model_name or "kimi-k2.5",
                status="completed" if result.success else "failed",
                success=result.success,
                answer=result.answer,
                error=result.error,
                total_turns=result.total_turns,
                total_input_tokens=result.total_input_tokens,
                total_output_tokens=result.total_output_tokens,
                steps=result.steps,
                llm_calls=result.llm_calls,
                duration_ms=duration_ms,
                session_id=task.session_id,
            )
            session.add(trace)

            # Update session context if session mode
            if task.context_mode == "session" and task.session_id and result.messages:
                pub_session = session.get(PublishedSessionDB, task.session_id)
                if pub_session:
                    pub_session.agent_context = result.messages
                    pub_session.updated_at = datetime.utcnow()

            # Update run log
            self._update_run_log(
                session, run_log_id, "completed",
                result_summary=result.answer[:500] if result.answer else None,
                trace_id=trace.id,
                duration_ms=duration_ms,
            )

            # Send to channel if binding exists
            if task.channel_binding_id and result.answer:
                try:
                    from app.services.channel_manager import ChannelManager
                    manager = ChannelManager()
                    send_loop = asyncio.new_event_loop()
                    try:
                        send_loop.run_until_complete(
                            manager.send_to_channel(task.channel_binding_id, result.answer)
                        )
                    finally:
                        send_loop.close()
                except Exception as e:
                    logger.warning(f"Failed to send result to channel: {e}")

            logger.info(f"Scheduled task '{task_id}' completed in {duration_ms}ms")

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Scheduled task {task_id} failed: {e}", exc_info=True)
            self._update_run_log(
                session, run_log_id, "failed",
                error=str(e),
                duration_ms=duration_ms,
            )
        finally:
            session.close()

    def _update_run_log(
        self, session, run_log_id: str, status: str,
        result_summary: str = None, error: str = None,
        trace_id: str = None, duration_ms: int = None,
    ):
        """Update a run log record."""
        from app.db.models import TaskRunLogDB

        run_log = session.get(TaskRunLogDB, run_log_id)
        if run_log:
            run_log.status = status
            run_log.completed_at = datetime.utcnow()
            if result_summary:
                run_log.result_summary = result_summary
            if error:
                run_log.error = error
            if trace_id:
                run_log.trace_id = trace_id
            if duration_ms is not None:
                run_log.duration_ms = duration_ms
            session.commit()

    async def execute_task_async(self, task_id: str):
        """Execute a task immediately (for run-now endpoint)."""
        from app.db.database import AsyncSessionLocal
        from app.db.models import ScheduledTaskDB, TaskRunLogDB, generate_uuid

        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ScheduledTaskDB).where(ScheduledTaskDB.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task {task_id} not found")

            now = datetime.utcnow()
            run_log = TaskRunLogDB(
                id=generate_uuid(),
                task_id=task.id,
                started_at=now,
                status="running",
            )
            session.add(run_log)
            task.last_run = now
            task.run_count += 1
            await session.commit()

            run_log_id = run_log.id

        # Execute in background thread
        thread = threading.Thread(
            target=self._execute_task,
            args=(task_id, run_log_id),
            daemon=True,
        )
        thread.start()
        return run_log_id
