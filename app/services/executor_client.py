"""
Executor Client - HTTP client for calling executor containers.

This client provides async methods to execute code in executor containers
via their HTTP API.
"""

import logging
from typing import Optional

import httpx

from app.services.executor_config import get_executor_url, get_all_executor_names

logger = logging.getLogger(__name__)


class ExecutorClient:
    """
    HTTP client for executor container API.

    Each executor runs a FastAPI service with endpoints:
    - POST /execute/python - Execute Python code
    - POST /execute/bash - Execute shell commands
    - GET /health - Health check
    """

    def __init__(self, executor_name: str):
        """
        Initialize executor client.

        Args:
            executor_name: Name of the executor (base, chemscout, remotion, diagram, or custom)
        """
        self.executor_name = executor_name
        self.base_url = get_executor_url(executor_name)

    async def execute_python(
        self,
        code: str,
        workspace_id: str,
        timeout: int = 300,
        env: Optional[dict] = None
    ) -> dict:
        """
        Execute Python code in the executor container.

        Args:
            code: Python code to execute
            workspace_id: Workspace ID for isolation
            timeout: Execution timeout in seconds
            env: Optional environment variables

        Returns:
            dict with stdout, stderr, exit_code, timed_out
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/execute/python",
                    json={
                        "code": code,
                        "workspace_id": workspace_id,
                        "timeout": timeout,
                        "env": env
                    },
                    timeout=timeout + 30  # HTTP timeout slightly larger than execution timeout
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error(f"Timeout calling executor {self.executor_name}")
            return {
                "stdout": "",
                "stderr": f"HTTP timeout after {timeout + 30} seconds",
                "exit_code": -1,
                "timed_out": True
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from executor {self.executor_name}: {e}")
            return {
                "stdout": "",
                "stderr": f"Executor HTTP error: {e.response.status_code}",
                "exit_code": -1,
                "timed_out": False
            }
        except Exception as e:
            logger.error(f"Error calling executor {self.executor_name}: {e}")
            return {
                "stdout": "",
                "stderr": f"Executor error: {str(e)}",
                "exit_code": -1,
                "timed_out": False
            }

    async def execute_bash(
        self,
        command: str,
        workspace_id: str,
        timeout: int = 300,
        env: Optional[dict] = None
    ) -> dict:
        """
        Execute a shell command in the executor container.

        Args:
            command: Shell command to execute
            workspace_id: Workspace ID for isolation
            timeout: Execution timeout in seconds
            env: Optional environment variables

        Returns:
            dict with stdout, stderr, exit_code, timed_out
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/execute/bash",
                    json={
                        "command": command,
                        "workspace_id": workspace_id,
                        "timeout": timeout,
                        "env": env
                    },
                    timeout=timeout + 30
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error(f"Timeout calling executor {self.executor_name}")
            return {
                "stdout": "",
                "stderr": f"HTTP timeout after {timeout + 30} seconds",
                "exit_code": -1,
                "timed_out": True
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from executor {self.executor_name}: {e}")
            return {
                "stdout": "",
                "stderr": f"Executor HTTP error: {e.response.status_code}",
                "exit_code": -1,
                "timed_out": False
            }
        except Exception as e:
            logger.error(f"Error calling executor {self.executor_name}: {e}")
            return {
                "stdout": "",
                "stderr": f"Executor error: {str(e)}",
                "exit_code": -1,
                "timed_out": False
            }

    async def health_check(self) -> dict:
        """
        Check health of the executor container.

        Returns:
            Health info dict or error dict
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=10
                )
                response.raise_for_status()
                return {
                    "healthy": True,
                    **response.json()
                }
        except Exception as e:
            logger.warning(f"Health check failed for executor {self.executor_name}: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }

    @classmethod
    async def check_all_executors(cls) -> dict[str, dict]:
        """
        Check health of all known executors.

        Returns:
            Dict mapping executor name to health info
        """
        results = {}
        for name in get_all_executor_names():
            client = cls(name)
            results[name] = await client.health_check()
        return results


# Convenience function for getting an executor client
def get_executor_client(executor_name: str = "base") -> ExecutorClient:
    """
    Get an executor client instance.

    Args:
        executor_name: Name of the executor (default: 'base')

    Returns:
        ExecutorClient instance
    """
    return ExecutorClient(executor_name)
