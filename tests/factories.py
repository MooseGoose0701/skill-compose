"""
Test data factories for creating database objects.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from app.db.models import (
    SkillDB,
    SkillVersionDB,
    SkillFileDB,
    AgentTraceDB,
    BackgroundTaskDB,
    AgentPresetDB,
    SkillChangelogDB,
    PublishedSessionDB,
)


def make_skill(
    name: str = "test-skill",
    description: str = "A test skill",
    status: str = "active",
    skill_type: str = "user",
    current_version: Optional[str] = "0.0.1",
    tags: Optional[List[str]] = None,
    category: Optional[str] = None,
    is_pinned: bool = False,
    seed_hash: Optional[str] = None,
    **kwargs,
) -> SkillDB:
    return SkillDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        name=name,
        description=description,
        status=status,
        skill_type=skill_type,
        current_version=current_version,
        tags=tags,
        category=category,
        is_pinned=is_pinned,
        seed_hash=seed_hash,
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at", datetime.utcnow()),
    )


def make_skill_version(
    skill_id: str,
    version: str = "0.0.1",
    skill_md: str = "---\nname: test-skill\ndescription: A test skill\n---\n\n# Test Skill\n\nThis skill does testing things for automated test suites.",
    parent_version: Optional[str] = None,
    commit_message: str = "Test version",
    **kwargs,
) -> SkillVersionDB:
    return SkillVersionDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        skill_id=skill_id,
        version=version,
        parent_version=parent_version,
        skill_md=skill_md,
        schema_json=kwargs.get("schema_json"),
        manifest_json=kwargs.get("manifest_json"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        created_by=kwargs.get("created_by"),
        commit_message=commit_message,
    )


def make_skill_file(
    version_id: str,
    file_path: str = "scripts/test.py",
    file_type: str = "script",
    content: bytes = b"print('hello')",
    **kwargs,
) -> SkillFileDB:
    return SkillFileDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        version_id=version_id,
        file_path=file_path,
        file_type=file_type,
        content=content,
        content_hash=kwargs.get("content_hash", "abc123"),
        size_bytes=kwargs.get("size_bytes", len(content)),
        created_at=kwargs.get("created_at", datetime.utcnow()),
    )


def make_trace(
    request: str = "test request",
    success: bool = True,
    model: str = "kimi-k2.5",
    total_turns: int = 3,
    **kwargs,
) -> AgentTraceDB:
    return AgentTraceDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        request=request,
        skills_used=kwargs.get("skills_used", ["test-skill"]),
        model=model,
        status=kwargs.get("status", "completed"),
        success=success,
        answer=kwargs.get("answer", "Test answer"),
        error=kwargs.get("error"),
        total_turns=total_turns,
        total_input_tokens=kwargs.get("total_input_tokens", 1000),
        total_output_tokens=kwargs.get("total_output_tokens", 500),
        steps=kwargs.get("steps", [
            {"role": "assistant", "content": "I'll help with that."},
            {"role": "assistant", "content": "Here is the result.", "tool_name": "execute_code", "tool_input": {"code": "print('hi')"}, "tool_result": "hi"},
        ]),
        llm_calls=kwargs.get("llm_calls", [
            {"turn": 1, "model": model, "input_tokens": 500, "output_tokens": 250, "stop_reason": "tool_use"},
            {"turn": 2, "model": model, "input_tokens": 500, "output_tokens": 250, "stop_reason": "end_turn"},
        ]),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        duration_ms=kwargs.get("duration_ms", 5000),
    )


def make_preset(
    name: str = "test-preset",
    description: str = "A test preset",
    is_system: bool = False,
    is_published: bool = False,
    max_turns: int = 60,
    seed_hash: Optional[str] = None,
    **kwargs,
) -> AgentPresetDB:
    return AgentPresetDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        name=name,
        description=description,
        system_prompt=kwargs.get("system_prompt"),
        skill_ids=kwargs.get("skill_ids", ["test-skill"]),
        mcp_servers=kwargs.get("mcp_servers", ["fetch"]),
        builtin_tools=kwargs.get("builtin_tools"),
        max_turns=max_turns,
        is_system=is_system,
        is_published=is_published,
        seed_hash=seed_hash,
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at", datetime.utcnow()),
    )


def make_background_task(
    task_type: str = "create_skill",
    status: str = "pending",
    **kwargs,
) -> BackgroundTaskDB:
    return BackgroundTaskDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        task_type=task_type,
        status=status,
        metadata_json=kwargs.get("metadata_json", {"skill_name": "test-skill"}),
        result_json=kwargs.get("result_json"),
        error=kwargs.get("error"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        started_at=kwargs.get("started_at"),
        completed_at=kwargs.get("completed_at"),
    )


def make_published_session(
    agent_id: str,
    messages: Optional[List[dict]] = None,
    agent_context: Optional[List[dict]] = None,
    **kwargs,
) -> PublishedSessionDB:
    return PublishedSessionDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        agent_id=agent_id,
        messages=messages or [],
        agent_context=agent_context,
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at", datetime.utcnow()),
    )


def make_changelog(
    skill_id: str,
    change_type: str = "create",
    **kwargs,
) -> SkillChangelogDB:
    return SkillChangelogDB(
        id=kwargs.get("id", str(uuid.uuid4())),
        skill_id=skill_id,
        version_from=kwargs.get("version_from"),
        version_to=kwargs.get("version_to", "0.0.1"),
        change_type=change_type,
        diff_content=kwargs.get("diff_content"),
        changed_by=kwargs.get("changed_by"),
        changed_at=kwargs.get("changed_at", datetime.utcnow()),
        comment=kwargs.get("comment", "Test change"),
    )
