"""
Executor Server - Code execution service for Skills API.

This service runs in a Docker container and provides HTTP endpoints
for executing Python code and shell commands in an isolated environment.

Python execution uses a persistent IPython kernel per workspace so that
variables, imports, and state persist across calls.  Falls back to
subprocess if the kernel is unavailable.

API Endpoints:
- POST /execute/python - Execute Python code
- POST /execute/bash - Execute shell commands
- POST /kernel/shutdown - Shutdown a workspace kernel
- GET /health - Health check
"""

import logging
import os
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Executor Server",
    description="Code execution service for Skills API",
    version="1.0.0"
)

# Configuration
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", "/app/workspaces"))
EXECUTOR_NAME = os.environ.get("EXECUTOR_NAME", "unknown")
MAX_OUTPUT_SIZE = 100000  # 100KB max output

# Per-workspace kernel management
_workspace_kernels: Dict[str, object] = {}
_kernel_failed: Dict[str, bool] = {}


def _get_or_start_kernel(workspace_id: str, workspace_path: Path, timeout: int = 300):
    """Get or start an IPython kernel for the given workspace."""
    if _kernel_failed.get(workspace_id):
        return None
    kernel = _workspace_kernels.get(workspace_id)
    if kernel is not None and kernel.is_alive:
        return kernel
    try:
        from ipython_kernel import IPythonKernel
        kernel = IPythonKernel(
            execute_timeout=timeout,
            max_output_chars=MAX_OUTPUT_SIZE,
            working_dir=str(workspace_path),
        )
        kernel.start()
        _workspace_kernels[workspace_id] = kernel
        logger.info("IPython kernel started for workspace %s", workspace_id)
        return kernel
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        logger.warning(
            "IPython kernel failed for workspace %s: %s. Using subprocess.",
            workspace_id, e,
        )
        print(f"[KERNEL FAIL] workspace={workspace_id} error={e}\n{err_detail}", flush=True)
        _kernel_failed[workspace_id] = True
        return None


class ExecuteRequest(BaseModel):
    """Request model for code execution."""
    code: str
    workspace_id: str
    timeout: int = 300
    env: Optional[dict] = None


class BashRequest(BaseModel):
    """Request model for bash command execution."""
    command: str
    workspace_id: str
    timeout: int = 300
    env: Optional[dict] = None


class ExecuteResponse(BaseModel):
    """Response model for execution results."""
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def truncate_output(output: str, max_size: int = MAX_OUTPUT_SIZE) -> str:
    """Truncate output if it exceeds max size."""
    if len(output) <= max_size:
        return output
    half = max_size // 2
    return (
        output[:half]
        + f"\n\n... (truncated {len(output) - max_size} characters) ...\n\n"
        + output[-half:]
    )


def get_workspace(workspace_id: str) -> Path:
    """Get or create workspace directory."""
    workspace = WORKSPACES_DIR / workspace_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@app.post("/execute/python", response_model=ExecuteResponse)
async def execute_python(request: ExecuteRequest):
    """
    Execute Python code in the workspace.

    Uses a persistent IPython kernel per workspace so variables persist
    across calls.  Falls back to subprocess if the kernel is unavailable.
    """
    workspace = get_workspace(request.workspace_id)

    # Inject env vars into kernel before executing user code
    env_setup_code = ""
    if request.env:
        env_setup_code = "import os\nos.environ.update(%r)\n" % request.env

    # Try kernel first
    kernel = _get_or_start_kernel(request.workspace_id, workspace, request.timeout)
    if kernel is not None:
        try:
            # Set env vars in kernel (silently, before user code)
            if env_setup_code:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: kernel.execute(env_setup_code)
                )
            kr = await asyncio.get_event_loop().run_in_executor(
                None, lambda: kernel.execute(request.code)
            )
            return ExecuteResponse(
                stdout=kr.output if kr.success else "",
                stderr=kr.error or "" if not kr.success else "",
                exit_code=0 if kr.success else 1,
            )
        except Exception as e:
            import traceback
            print(f"[KERNEL EXEC FAIL] workspace={request.workspace_id} error={e}\n{traceback.format_exc()}", flush=True)
            logger.warning(
                "Kernel execution failed for workspace %s: %s. Falling back.",
                request.workspace_id, e,
            )
            _workspace_kernels.pop(request.workspace_id, None)
            _kernel_failed[request.workspace_id] = True

    # Subprocess fallback
    script_path = workspace / "_script.py"
    script_path.write_text(request.code)

    env = os.environ.copy()
    env["WORKSPACE"] = str(workspace)
    env["PYTHONUNBUFFERED"] = "1"
    if request.env:
        env.update(request.env)

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ["python", str(script_path)],
                cwd=workspace,
                capture_output=True,
                timeout=request.timeout,
                env=env
            )
        )

        return ExecuteResponse(
            stdout=truncate_output(result.stdout.decode(errors="replace")),
            stderr=truncate_output(result.stderr.decode(errors="replace")),
            exit_code=result.returncode
        )

    except subprocess.TimeoutExpired:
        return ExecuteResponse(
            stdout="",
            stderr=f"Execution timed out after {request.timeout} seconds",
            exit_code=-1,
            timed_out=True
        )
    except Exception as e:
        return ExecuteResponse(
            stdout="",
            stderr=f"Execution error: {str(e)}",
            exit_code=-1
        )


@app.post("/execute/bash", response_model=ExecuteResponse)
async def execute_bash(request: BashRequest):
    """
    Execute a shell command in the workspace.
    """
    workspace = get_workspace(request.workspace_id)

    # Build environment
    env = os.environ.copy()
    env["WORKSPACE"] = str(workspace)
    if request.env:
        env.update(request.env)

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                request.command,
                shell=True,
                cwd=workspace,
                capture_output=True,
                timeout=request.timeout,
                env=env
            )
        )

        return ExecuteResponse(
            stdout=truncate_output(result.stdout.decode(errors="replace")),
            stderr=truncate_output(result.stderr.decode(errors="replace")),
            exit_code=result.returncode
        )

    except subprocess.TimeoutExpired:
        return ExecuteResponse(
            stdout="",
            stderr=f"Execution timed out after {request.timeout} seconds",
            exit_code=-1,
            timed_out=True
        )
    except Exception as e:
        return ExecuteResponse(
            stdout="",
            stderr=f"Execution error: {str(e)}",
            exit_code=-1
        )


@app.post("/kernel/shutdown")
async def shutdown_kernel(workspace_id: str):
    """Shutdown the IPython kernel for a workspace."""
    kernel = _workspace_kernels.pop(workspace_id, None)
    _kernel_failed.pop(workspace_id, None)
    if kernel is not None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, kernel.shutdown
            )
        except Exception:
            pass
        return {"status": "shutdown", "workspace_id": workspace_id}
    return {"status": "not_found", "workspace_id": workspace_id}


@app.get("/health")
async def health():
    """Health check endpoint."""
    python_version = subprocess.getoutput("python --version")

    # Get installed packages summary
    try:
        pip_list = subprocess.getoutput("pip list --format=freeze | wc -l")
        package_count = int(pip_list.strip())
    except:
        package_count = -1

    return {
        "status": "ok",
        "executor": EXECUTOR_NAME,
        "python_version": python_version,
        "package_count": package_count,
        "workspaces_dir": str(WORKSPACES_DIR)
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Executor Server",
        "executor": EXECUTOR_NAME,
        "endpoints": [
            "POST /execute/python",
            "POST /execute/bash",
            "POST /kernel/shutdown",
            "GET /health"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("EXECUTOR_PORT", "62680")))
