"""
Agent Traces API endpoints.

Provides endpoints for:
- Listing execution traces
- Getting trace details
- Deleting traces
- Exporting traces
"""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import AgentTraceDB


router = APIRouter(prefix="/traces", tags=["traces"])


# Response models
class StepInfo(BaseModel):
    """A single step in agent execution."""
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_result: Optional[str] = None


class TraceListItem(BaseModel):
    """Trace item for list response."""
    id: str
    request: str
    skills_used: Optional[List[str]] = None
    model: str
    status: str = "completed"  # running/completed/failed
    success: bool
    total_turns: int
    total_input_tokens: int
    total_output_tokens: int
    created_at: datetime
    duration_ms: Optional[int] = None
    executor_name: Optional[str] = None


class TraceDetail(BaseModel):
    """Full trace details."""
    id: str
    request: str
    skills_used: Optional[List[str]] = None
    model: str
    status: str = "completed"  # running/completed/failed
    success: bool
    answer: Optional[str] = None
    error: Optional[str] = None
    total_turns: int
    total_input_tokens: int
    total_output_tokens: int
    steps: Optional[List[dict]] = None
    llm_calls: Optional[List[dict]] = None
    created_at: datetime
    duration_ms: Optional[int] = None
    executor_name: Optional[str] = None


class TraceListResponse(BaseModel):
    """Response for listing traces."""
    traces: List[TraceListItem]
    total: int
    offset: int
    limit: int


@router.get("", response_model=TraceListResponse)
async def list_traces(
    success: Optional[bool] = Query(None, description="Filter by success status"),
    skill_name: Optional[str] = Query(None, description="Filter by skill name (in skills_used)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
):
    """
    List agent execution traces.

    Returns a paginated list of traces, ordered by creation time (newest first).
    Optionally filter by skill_name to get traces that used a specific skill.
    """
    # Build query
    query = select(AgentTraceDB)

    if success is not None:
        query = query.where(AgentTraceDB.success == success)

    # Filter by skill_name - check if skill is in the skills_used JSONB array
    if skill_name is not None:
        query = query.where(
            cast(AgentTraceDB.skills_used, String).like(f'%"{skill_name}"%')
        )

    # Get total count
    count_query = select(AgentTraceDB.id)
    if success is not None:
        count_query = count_query.where(AgentTraceDB.success == success)
    if skill_name is not None:
        count_query = count_query.where(
            cast(AgentTraceDB.skills_used, String).like(f'%"{skill_name}"%')
        )
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Get paginated results
    query = query.order_by(desc(AgentTraceDB.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    traces = result.scalars().all()

    return TraceListResponse(
        traces=[
            TraceListItem(
                id=t.id,
                request=t.request[:200] + "..." if len(t.request) > 200 else t.request,
                skills_used=t.skills_used,
                model=t.model,
                status=t.status,
                success=t.success,
                total_turns=t.total_turns,
                total_input_tokens=t.total_input_tokens,
                total_output_tokens=t.total_output_tokens,
                created_at=t.created_at,
                duration_ms=t.duration_ms,
                executor_name=t.executor_name,
            )
            for t in traces
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{trace_id}", response_model=TraceDetail)
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific trace.

    Includes full execution steps and LLM calls.
    """
    result = await db.execute(
        select(AgentTraceDB).where(AgentTraceDB.id == trace_id)
    )
    trace = result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    return TraceDetail(
        id=trace.id,
        request=trace.request,
        skills_used=trace.skills_used,
        model=trace.model,
        status=trace.status,
        success=trace.success,
        answer=trace.answer,
        error=trace.error,
        total_turns=trace.total_turns,
        total_input_tokens=trace.total_input_tokens,
        total_output_tokens=trace.total_output_tokens,
        steps=trace.steps,
        llm_calls=trace.llm_calls,
        created_at=trace.created_at,
        duration_ms=trace.duration_ms,
        executor_name=trace.executor_name,
    )


@router.delete("/{trace_id}")
async def delete_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a specific trace.
    """
    result = await db.execute(
        select(AgentTraceDB).where(AgentTraceDB.id == trace_id)
    )
    trace = result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    await db.delete(trace)
    await db.commit()

    return {"message": "Trace deleted successfully"}


def _trace_to_export_dict(trace: AgentTraceDB) -> dict:
    """Convert trace DB model to export dictionary."""
    return {
        "id": trace.id,
        "request": trace.request,
        "skills_used": trace.skills_used,
        "model": trace.model,
        "status": trace.status,
        "success": trace.success,
        "answer": trace.answer,
        "error": trace.error,
        "total_turns": trace.total_turns,
        "total_input_tokens": trace.total_input_tokens,
        "total_output_tokens": trace.total_output_tokens,
        "steps": trace.steps,
        "llm_calls": trace.llm_calls,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
        "duration_ms": trace.duration_ms,
        "executor_name": trace.executor_name,
    }


@router.get("/{trace_id}/export")
async def export_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Export a single trace as JSON file.
    """
    result = await db.execute(
        select(AgentTraceDB).where(AgentTraceDB.id == trace_id)
    )
    trace = result.scalar_one_or_none()

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    export_data = _trace_to_export_dict(trace)
    json_content = json.dumps(export_data, indent=2, ensure_ascii=False)

    # Create filename from trace id and date
    date_str = trace.created_at.strftime("%Y%m%d") if trace.created_at else "unknown"
    filename = f"trace_{trace_id[:8]}_{date_str}.json"

    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


class ExportTracesRequest(BaseModel):
    """Request body for bulk trace export."""
    trace_ids: Optional[List[str]] = Field(None, description="Specific trace IDs to export. If not provided, uses filters.")
    skill_name: Optional[str] = Field(None, description="Filter by skill name")
    success: Optional[bool] = Field(None, description="Filter by success status")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of traces to export")


@router.post("/export")
async def export_traces(
    request: ExportTracesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Export multiple traces as JSON file.

    Can export specific traces by ID or filter by criteria.
    """
    if request.trace_ids:
        # Export specific traces
        result = await db.execute(
            select(AgentTraceDB).where(AgentTraceDB.id.in_(request.trace_ids))
        )
        traces = result.scalars().all()
    else:
        # Export by filters
        query = select(AgentTraceDB)

        if request.success is not None:
            query = query.where(AgentTraceDB.success == request.success)

        if request.skill_name:
            query = query.where(
                cast(AgentTraceDB.skills_used, String).like(f'%"{request.skill_name}"%')
            )

        query = query.order_by(desc(AgentTraceDB.created_at)).limit(request.limit)
        result = await db.execute(query)
        traces = result.scalars().all()

    if not traces:
        raise HTTPException(status_code=404, detail="No traces found matching criteria")

    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_traces": len(traces),
        "traces": [_trace_to_export_dict(t) for t in traces]
    }

    json_content = json.dumps(export_data, indent=2, ensure_ascii=False)

    # Create filename with date
    date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"traces_export_{date_str}.json"

    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
