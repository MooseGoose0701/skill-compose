"""Tools API - code execution, tools registry, and other utilities"""
import sys
import traceback
from io import StringIO
from typing import Optional, Literal, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools import get_code_executor
from app.config import settings
from app.core.tools_registry import (
    get_all_tools,
    get_tool_by_id,
    get_tools_by_category,
    get_categories,
    ToolDefinition,
)

router = APIRouter(prefix="/tools", tags=["Tools"])


class CodeExecuteRequest(BaseModel):
    """Code execution request"""
    code: str = Field(..., description="Python code to execute")
    timeout: int = Field(30, description="Timeout in seconds", ge=1, le=300)
    executor: Literal["subprocess", "simple"] = Field(
        "subprocess",
        description="Executor type: 'subprocess' runs in isolated process, 'simple' uses basic exec()"
    )


class CommandExecuteRequest(BaseModel):
    """Command execution request"""
    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(30, description="Timeout in seconds", ge=1, le=300)


class CodeExecuteResponse(BaseModel):
    """Code execution response"""
    success: bool
    output: str
    error: Optional[str] = None
    return_value: Optional[str] = None


@router.post("/execute", response_model=CodeExecuteResponse)
async def execute_code(request: CodeExecuteRequest):
    """
    Execute Python code and return results.

    Supports two execution modes:
    - 'subprocess': Runs in isolated subprocess (recommended, each call is independent)
    - 'simple': Uses basic exec() for lightweight execution

    Example:
        POST /api/v1/tools/execute
        {"code": "print(1+1)", "executor": "subprocess"}

        Response: {"success": true, "output": "2\\n", "return_value": null}
    """
    if request.executor == "subprocess":
        return await _execute_with_subprocess(request)
    else:
        return await _execute_simple(request)


async def _execute_with_subprocess(request: CodeExecuteRequest) -> CodeExecuteResponse:
    """Execute code using subprocess."""
    try:
        executor = get_code_executor(
            timeout=request.timeout,
        )
        result = executor.execute(request.code)

        return CodeExecuteResponse(
            success=result.success,
            output=result.output,
            error=result.error,
            return_value=result.return_value,
        )

    except Exception as e:
        return CodeExecuteResponse(
            success=False,
            output="",
            error=f"Executor error: {type(e).__name__}: {str(e)}",
            return_value=None,
        )


async def _execute_simple(request: CodeExecuteRequest) -> CodeExecuteResponse:
    """Execute code using simple exec() - fallback mode."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_output = StringIO()
    captured_error = StringIO()

    sys.stdout = captured_output
    sys.stderr = captured_error

    return_value = None
    error_msg = None
    success = True

    try:
        exec_globals = {
            "__builtins__": __builtins__,
            "__name__": "__main__",
        }
        exec(request.code, exec_globals)

        if 'result' in exec_globals:
            return_value = str(exec_globals['result'])

    except Exception as e:
        success = False
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    output = captured_output.getvalue()
    stderr = captured_error.getvalue()

    if stderr:
        output += f"\n[stderr]\n{stderr}"

    return CodeExecuteResponse(
        success=success,
        output=output,
        error=error_msg,
        return_value=return_value,
    )


@router.post("/execute_command", response_model=CodeExecuteResponse)
async def execute_command(request: CommandExecuteRequest):
    """
    Execute a shell command and return results.

    Execute a shell command and return results.

    Example:
        POST /api/v1/tools/execute_command
        {"command": "ls -la"}

        Response: {"success": true, "output": "...", "return_value": null}
    """
    try:
        executor = get_code_executor(
            timeout=request.timeout,
        )
        result = executor.execute_command(request.command)

        return CodeExecuteResponse(
            success=result.success,
            output=result.output,
            error=result.error,
            return_value=None,
        )

    except Exception as e:
        return CodeExecuteResponse(
            success=False,
            output="",
            error=f"Command execution error: {type(e).__name__}: {str(e)}",
            return_value=None,
        )


@router.post("/reset_kernel")
async def reset_kernel():
    """
    Reset the code executor.

    Clears any cached state (workspace cleanup).
    Note: With subprocess executor, each call is already isolated,
    so this is mainly for compatibility.
    """
    try:
        executor = get_code_executor()
        executor.reset()
        return {"success": True, "message": "Executor reset successfully"}
    except Exception as e:
        return {"success": False, "message": f"Reset failed: {str(e)}"}


# ============ Tools Registry Endpoints ============

class ToolResponse(BaseModel):
    """Response for a single tool."""
    id: str
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any]


class ToolCategoryResponse(BaseModel):
    """Response for a tool category."""
    id: str
    name: str
    description: str
    icon: str


class ToolListResponse(BaseModel):
    """Response for tools list."""
    tools: List[ToolResponse]
    categories: Dict[str, ToolCategoryResponse]
    total: int


def _tool_to_response(tool: ToolDefinition) -> ToolResponse:
    """Convert ToolDefinition to ToolResponse."""
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        category=tool.category,
        input_schema=tool.input_schema,
    )


@router.get("/registry", response_model=ToolListResponse)
async def list_registry_tools(category: Optional[str] = None) -> ToolListResponse:
    """
    List all available agent tools from the registry.

    Optionally filter by category.
    """
    if category:
        tools = get_tools_by_category(category)
    else:
        tools = get_all_tools()

    categories = get_categories()
    category_responses = {
        cat_id: ToolCategoryResponse(
            id=cat_id,
            name=cat_info["name"],
            description=cat_info["description"],
            icon=cat_info["icon"],
        )
        for cat_id, cat_info in categories.items()
    }

    return ToolListResponse(
        tools=[_tool_to_response(t) for t in tools],
        categories=category_responses,
        total=len(tools),
    )


@router.get("/registry/{tool_id}", response_model=ToolResponse)
async def get_registry_tool(tool_id: str) -> ToolResponse:
    """
    Get a specific tool from the registry by ID.
    """
    tool = get_tool_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

    return _tool_to_response(tool)


@router.get("/registry/categories/all")
async def list_tool_categories() -> dict:
    """
    List all tool categories.
    """
    categories = get_categories()
    return {
        "categories": [
            ToolCategoryResponse(
                id=cat_id,
                name=cat_info["name"],
                description=cat_info["description"],
                icon=cat_info["icon"],
            )
            for cat_id, cat_info in categories.items()
        ]
    }
