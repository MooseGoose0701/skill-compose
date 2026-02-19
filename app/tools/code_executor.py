"""
Code Executor - Python code and shell command execution

This module provides code execution using a persistent IPython kernel with
subprocess fallback.

Features:
- Persistent IPython kernel: variables, imports, state persist across calls
- Automatic fallback to subprocess if kernel fails to start or crashes
- Working directory is the project root (so scripts can access skills/, etc.)
- Temporary scripts are stored in /tmp to avoid polluting the project
- Natural concurrency: Multiple agents can run in parallel
- Simple cleanup: Delete temp directory and kernel when done
"""
import logging
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Constants
MAX_OUTPUT_CHARS = 30000
DEFAULT_TIMEOUT = 300
TEMP_SCRIPTS_BASE_DIR = "/tmp/agent_workspaces"
WORKSPACES_BASE_DIR = Path(os.environ.get("WORKSPACES_DIR", "/app/workspaces"))


def _load_env_file() -> Dict[str, str]:
    """Load variables from .env file (config dir > project dir > cwd)."""
    try:
        from app.config import get_settings
        settings = get_settings()
        candidates = [
            Path(settings.config_dir) / ".env",
            Path(settings.project_dir) / ".env",
            Path(".env"),
        ]
    except Exception:
        candidates = [Path("/app/config/.env"), Path(".env")]
    for p in candidates:
        if p.exists():
            result = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if key and value:  # skip empty values
                        result[key] = value
            return result
    return {}


@dataclass
class ExecutionResult:
    """Result of code execution"""
    success: bool
    output: str
    error: Optional[str] = None
    return_value: Optional[str] = None


class AgentWorkspace:
    """
    Workspace for Agent code execution.

    - working_dir: The cwd for subprocess (typically project root)
    - temp_path: Where temporary scripts are stored (/tmp/agent_workspaces/xxx)

    This allows Agent to:
    - Execute scripts in the project directory (e.g., python skills/xxx/script.py)
    - Access project files with relative paths
    - Keep temp scripts separate from the project
    """

    def __init__(
        self,
        working_dir: Optional[str] = None,
        temp_base_dir: str = TEMP_SCRIPTS_BASE_DIR,
        timeout: int = DEFAULT_TIMEOUT,
        max_output_chars: int = MAX_OUTPUT_CHARS,
        env_vars: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize a new workspace.

        Args:
            working_dir: Working directory for command execution (default: cwd)
            temp_base_dir: Base directory for temporary scripts
            timeout: Default execution timeout in seconds
            max_output_chars: Maximum characters in output
            env_vars: Additional environment variables for execution
        """
        self.workspace_id = str(uuid.uuid4())

        # Working directory for subprocess cwd (project root)
        self.working_dir = Path(working_dir).resolve() if working_dir else Path.cwd()

        # Per-session workspace directory for code execution output
        # This is where execute_code/bash cwd points, and file_scanner scans
        self.workspace_dir = WORKSPACES_BASE_DIR / self.workspace_id
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Temp directory for scripts (isolated in /tmp)
        self.temp_path = Path(temp_base_dir) / self.workspace_id
        self.temp_path.mkdir(parents=True, exist_ok=True)

        # Legacy: self.path for backward compatibility
        self.path = self.temp_path

        self.timeout = timeout
        self.max_output_chars = max_output_chars
        self._script_counter = 0

        # IPython kernel state
        self._kernel = None
        self._kernel_failed = False

        # Build execution environment
        # Reload from .env file to pick up changes made by other worker processes
        # (uvicorn --workers N: os.environ updates are per-process only)
        self.env = os.environ.copy()
        self.env.update(_load_env_file())
        if env_vars:
            self.env.update(env_vars)

    def set_env_vars(self, env_vars: Dict[str, str]) -> None:
        """
        Add environment variables for future executions.

        Args:
            env_vars: Dict of environment variable name -> value
        """
        if env_vars:
            self.env.update(env_vars)

    def write_file(self, filename: str, content: str) -> Path:
        """
        Write a file to the temp directory.

        Args:
            filename: Name of the file (relative to temp_path)
            content: File content

        Returns:
            Full path to the written file
        """
        filepath = self.temp_path / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        return filepath

    def _get_or_start_kernel(self):
        """
        Lazily start the IPython kernel. Returns the kernel or None.

        If the kernel previously failed to start, returns None immediately
        to avoid repeated startup attempts.
        """
        if self._kernel_failed:
            return None
        if self._kernel is not None and self._kernel.is_alive:
            return self._kernel
        # Kernel died or not started yet — try (re)starting
        try:
            from app.tools.ipython_kernel import IPythonKernel

            self._kernel = IPythonKernel(
                execute_timeout=self.timeout,
                max_output_chars=self.max_output_chars,
                working_dir=str(self.workspace_dir),
                env=self.env,
            )
            self._kernel.start()
            logger.info("IPython kernel started for workspace %s", self.workspace_id)
            return self._kernel
        except Exception as e:
            logger.warning(
                "IPython kernel failed to start for workspace %s: %s. "
                "Falling back to subprocess.",
                self.workspace_id,
                e,
            )
            self._kernel = None
            self._kernel_failed = True
            return None

    def execute(self, code: str) -> ExecutionResult:
        """
        Execute Python code with persistent state.

        Uses an IPython kernel so that variables, imports, and state persist
        across calls within the same workspace. Falls back to subprocess
        if the kernel is unavailable.

        Args:
            code: Python code to execute

        Returns:
            ExecutionResult with success status, output, and any errors
        """
        kernel = self._get_or_start_kernel()
        if kernel is not None:
            try:
                kr = kernel.execute(code)
                return ExecutionResult(
                    success=kr.success,
                    output=kr.output,
                    error=kr.error,
                    return_value=kr.return_value,
                )
            except Exception as e:
                logger.warning(
                    "Kernel execution failed for workspace %s: %s. "
                    "Falling back to subprocess.",
                    self.workspace_id,
                    e,
                )
                # Kernel crashed — fall through to subprocess
                self._kernel = None
                self._kernel_failed = True

        return self._execute_subprocess(code)

    def _execute_subprocess(self, code: str) -> ExecutionResult:
        """
        Execute Python code by writing to a temp file and running it.

        The script is written to temp_path but executed with working_dir as cwd,
        so relative paths in the code refer to the project directory.

        Args:
            code: Python code to execute

        Returns:
            ExecutionResult with success status, output, and any errors
        """
        # Generate unique script filename in temp directory
        self._script_counter += 1
        script_name = f"_script_{self._script_counter}.py"
        script_path = self.write_file(script_name, code)

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.workspace_dir),  # Use per-session workspace as cwd
                env=self.env,
            )

            output = result.stdout
            if result.stderr:
                output = output + "\n" + result.stderr if output else result.stderr

            # Truncate if too long
            if len(output) > self.max_output_chars:
                output = output[:self.max_output_chars] + "\n... [OUTPUT TRUNCATED]"

            # Check for errors
            has_error = result.returncode != 0

            return ExecutionResult(
                success=not has_error,
                output=output.strip(),
                error=output.strip() if has_error else None,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Execution timed out after {self.timeout} seconds",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {str(e)}",
            )

    def execute_command(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        """
        Execute a shell command with working_dir as cwd.

        Args:
            command: Shell command to execute
            timeout: Optional timeout in seconds (uses default if not specified)

        Returns:
            ExecutionResult with command output
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(self.workspace_dir),  # Use per-session workspace as cwd
                env=self.env,
            )

            output = result.stdout
            if result.stderr:
                output = output + "\n" + result.stderr if output else result.stderr

            # Truncate if too long
            if len(output) > self.max_output_chars:
                output = output[:self.max_output_chars] + "\n... [OUTPUT TRUNCATED]"

            return ExecutionResult(
                success=result.returncode == 0,
                output=output.strip(),
                error=output.strip() if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command timed out after {effective_timeout} seconds",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {str(e)}",
            )

    def cleanup(self) -> None:
        """
        Shutdown kernel and delete the temp directory.

        Call this when the Agent request is complete.
        Workspace directory is intentionally preserved so output files
        remain downloadable. Old workspaces are reaped on server startup.
        """
        # Shutdown kernel first
        try:
            if self._kernel is not None:
                self._kernel.shutdown()
                self._kernel = None
        except Exception:
            pass  # Best effort
        # Delete temp directory
        try:
            if self.temp_path.exists():
                shutil.rmtree(self.temp_path, ignore_errors=True)
        except Exception:
            pass  # Best effort cleanup

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup workspace."""
        self.cleanup()
        return False


# ============ Legacy Compatibility Layer ============
# For backward compatibility with code that uses the old CodeExecutor API

class CodeExecutor:
    """
    Legacy compatibility wrapper around AgentWorkspace.

    WARNING: This creates a single shared workspace, which means:
    - State is shared between all callers (not ideal for concurrent requests)
    - Use AgentWorkspace directly for proper request isolation

    This class is provided for backward compatibility only.
    New code should use AgentWorkspace instead.
    """

    def __init__(
        self,
        working_dir: str = ".",
        timeout: int = DEFAULT_TIMEOUT,
        verbose: bool = False,
        max_output_chars: int = MAX_OUTPUT_CHARS,
    ):
        self.working_dir = os.path.abspath(working_dir)
        self.timeout = timeout
        self.verbose = verbose
        self.max_output_chars = max_output_chars
        self._workspace: Optional[AgentWorkspace] = None
        self._env_vars: Dict[str, str] = {}

    def _get_workspace(self) -> AgentWorkspace:
        """Get or create the workspace."""
        if self._workspace is None:
            self._workspace = AgentWorkspace(
                working_dir=self.working_dir,
                timeout=self.timeout,
                max_output_chars=self.max_output_chars,
                env_vars=self._env_vars,
            )
        return self._workspace

    @property
    def backend(self) -> str:
        """Return the backend name."""
        return "subprocess"

    def execute(self, code: str, code_type: str = "python") -> ExecutionResult:
        """Execute Python code."""
        return self._get_workspace().execute(code)

    def execute_command(self, command: str) -> ExecutionResult:
        """Execute a shell command."""
        return self._get_workspace().execute_command(command)

    def set_env_vars(self, env_vars: Dict[str, str]) -> None:
        """Set environment variables for execution."""
        self._env_vars.update(env_vars)
        if self._workspace:
            self._workspace.set_env_vars(env_vars)

    def reset(self) -> None:
        """Reset by creating a new workspace."""
        if self._workspace:
            self._workspace.cleanup()
            self._workspace = None

    def shutdown(self) -> None:
        """Shutdown and cleanup."""
        self.reset()


# Singleton instance for legacy compatibility
_executor_instance: Optional[CodeExecutor] = None


def get_code_executor(
    working_dir: str = ".",
    timeout: int = DEFAULT_TIMEOUT,
    force_new: bool = False,
) -> CodeExecutor:
    """
    Get or create a CodeExecutor instance (legacy API).

    For new code, use AgentWorkspace directly instead.
    """
    global _executor_instance

    if _executor_instance is None or force_new:
        _executor_instance = CodeExecutor(
            working_dir=working_dir,
            timeout=timeout,
        )

    return _executor_instance
