"""
MCP Client - Connect to MCP servers and call their tools

This module provides a wrapper around MCP (Model Context Protocol) servers,
allowing the agent to call MCP tools as if they were native tools.

Configuration is loaded from config/mcp.json in the project directory.
API keys can be configured via:
1. Environment variables (highest priority)
2. config/mcp-secrets.json (UI-managed, gitignored)
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from app.config import get_settings

_settings = get_settings()


def _get_secrets_path() -> Path:
    """Get the MCP secrets file path."""
    return Path(_settings.config_dir) / "mcp-secrets.json"


def _load_secrets() -> Dict[str, Dict[str, str]]:
    """
    Load secrets from config/mcp-secrets.json.

    Returns:
        Dict mapping server_name -> {env_var_name: value}
    """
    secrets_path = _get_secrets_path()
    if secrets_path.exists():
        try:
            with open(secrets_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_secrets(secrets: Dict[str, Dict[str, str]]) -> None:
    """Save secrets to config/mcp-secrets.json."""
    secrets_path = _get_secrets_path()
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    with open(secrets_path, 'w') as f:
        json.dump(secrets, f, indent=2)


def get_secret(server_name: str, key_name: str) -> Tuple[Optional[str], str]:
    """
    Get a secret value for an MCP server.

    Priority: UI config (secrets file) > Environment variable

    Args:
        server_name: MCP server name (e.g., "tavily")
        key_name: Environment variable name (e.g., "TAVILY_API_KEY")

    Returns:
        Tuple of (value, source) where source is "secrets", "env", or "none"
    """
    # Check UI config (secrets file) first
    secrets = _load_secrets()
    if server_name in secrets and key_name in secrets[server_name]:
        return secrets[server_name][key_name], "secrets"

    # Fallback to .env file (multi-worker safe)
    from app.config import read_env_value
    env_value = read_env_value(key_name)
    if env_value:
        return env_value, "env"

    return None, "none"


def set_secret(server_name: str, key_name: str, value: str) -> None:
    """
    Set a secret value for an MCP server.

    Args:
        server_name: MCP server name
        key_name: Environment variable name
        value: The secret value
    """
    secrets = _load_secrets()
    if server_name not in secrets:
        secrets[server_name] = {}
    secrets[server_name][key_name] = value
    _save_secrets(secrets)


def delete_secret(server_name: str, key_name: str) -> bool:
    """
    Delete a secret value for an MCP server.

    Args:
        server_name: MCP server name
        key_name: Environment variable name

    Returns:
        True if deleted, False if not found
    """
    secrets = _load_secrets()
    if server_name in secrets and key_name in secrets[server_name]:
        del secrets[server_name][key_name]
        if not secrets[server_name]:
            del secrets[server_name]
        _save_secrets(secrets)
        return True
    return False


def get_server_secrets_status(server_name: str, required_keys: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get the configuration status for all required keys of a server.

    Args:
        server_name: MCP server name
        required_keys: List of environment variable names required

    Returns:
        Dict mapping key_name -> {configured: bool, source: str}
    """
    status = {}
    for key_name in required_keys:
        value, source = get_secret(server_name, key_name)
        status[key_name] = {
            "configured": value is not None and value != "",
            "source": source
        }
    return status


@dataclass
class MCPTool:
    """Configuration for an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPServer:
    """Configuration for an MCP server."""
    name: str
    display_name: str
    description: str
    command: str
    args: List[str]
    env: Dict[str, str]
    tools: List[MCPTool] = field(default_factory=list)
    default_enabled: bool = False  # Whether this server is enabled by default for all agents


class MCPClient:
    """
    Client for connecting to and calling MCP servers.

    This class manages connections to MCP servers (like Gemini MCP Server)
    and provides a unified interface for calling their tools.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize MCP client.

        Args:
            working_dir: Working directory for resolving relative paths
        """
        self.working_dir = Path(working_dir or _settings.project_dir)
        self.servers: Dict[str, MCPServer] = {}
        self._load_mcp_config()

    def _resolve_env_vars(self, env: Dict[str, str], server_name: str) -> Dict[str, str]:
        """
        Resolve environment variable references like ${VAR_NAME}.

        Priority: Environment variable > secrets file > empty string

        Args:
            env: Environment variables dict from config
            server_name: MCP server name for looking up secrets
        """
        resolved = {}
        for key, value in env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                # Use get_secret which checks env first, then secrets file
                secret_value, _ = get_secret(server_name, var_name)
                resolved[key] = secret_value or ""
            else:
                resolved[key] = value
        return resolved

    def _load_mcp_config(self):
        """
        Load MCP server configurations from config/mcp.json.

        Uses settings.config_dir which can be overridden via CONFIG_DIR env var.
        Searches in order:
        1. <config_dir>/mcp.json (from settings)
        2. <working_dir>/config/mcp.json (fallback)
        """
        config_paths = [
            Path(_settings.config_dir) / "mcp.json",
            self.working_dir / "config" / "mcp.json",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)

                    if "mcpServers" in config:
                        for name, server_config in config["mcpServers"].items():
                            # Resolve relative command paths
                            command = server_config.get("command", "")
                            args = server_config.get("args", [])

                            # Resolve relative paths in args
                            resolved_args = []
                            for arg in args:
                                if arg.startswith("./"):
                                    arg = str(self.working_dir / arg)
                                resolved_args.append(arg)

                            # Resolve environment variables
                            env = self._resolve_env_vars(server_config.get("env", {}), name)

                            # Parse tools
                            tools = []
                            for tool_config in server_config.get("tools", []):
                                tools.append(MCPTool(
                                    name=tool_config.get("name", ""),
                                    description=tool_config.get("description", ""),
                                    input_schema=tool_config.get("inputSchema", {})
                                ))

                            self.servers[name] = MCPServer(
                                name=name,
                                display_name=server_config.get("name", name),
                                description=server_config.get("description", ""),
                                command=command,
                                args=resolved_args,
                                env=env,
                                tools=tools,
                                default_enabled=server_config.get("defaultEnabled", False)
                            )

                    # Use first config found
                    break
                except Exception as e:
                    print(f"Warning: Failed to load MCP config from {config_path}: {e}")

    def list_servers(self) -> List[str]:
        """List all configured MCP server names."""
        return list(self.servers.keys())

    def get_server(self, server_name: str) -> Optional[MCPServer]:
        """Get a specific MCP server configuration."""
        return self.servers.get(server_name)

    def get_all_servers(self) -> List[MCPServer]:
        """Get all configured MCP servers."""
        return list(self.servers.values())

    def get_default_enabled_servers(self) -> List[str]:
        """Get list of server names that are enabled by default."""
        return [name for name, server in self.servers.items() if server.default_enabled]

    def get_required_env_vars(self, server_name: str) -> List[str]:
        """
        Get list of required environment variable names for a server.

        Parses the env config to find ${VAR_NAME} references.
        """
        config = _load_raw_config()
        server_config = config.get("mcpServers", {}).get(server_name, {})
        env = server_config.get("env", {})

        required_vars = []
        for key, value in env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                required_vars.append(var_name)
        return required_vars

    def get_server_info(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get server info as a dictionary (for API responses)."""
        server = self.servers.get(server_name)
        if not server:
            return None

        # Get required env vars and their status
        required_keys = self.get_required_env_vars(server_name)
        secrets_status = get_server_secrets_status(server_name, required_keys)

        return {
            "name": server.name,
            "display_name": server.display_name,
            "description": server.description,
            "default_enabled": server.default_enabled,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema
                }
                for tool in server.tools
            ],
            "required_env_vars": required_keys,
            "secrets_status": secrets_status
        }

    def discover_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Discover tools available on an MCP server.

        Returns a list of tool definitions in Claude's expected format.
        """
        server = self.servers.get(server_name)
        if not server:
            return []

        tools = []
        for tool in server.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            })
        return tools

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            server_name: Name of the MCP server (e.g., "gemini")
            tool_name: Name of the tool to call (e.g., "gemini_analyze_image")
            arguments: Tool arguments as a dictionary

        Returns:
            Tool result as a dictionary

        Raises:
            ValueError: If server not found or tool call fails
        """
        if server_name not in self.servers:
            raise ValueError(f"MCP server '{server_name}' not configured. Available: {self.list_servers()}")

        server = self.servers[server_name]

        # For now, we'll implement a simple subprocess-based approach
        # In production, you might want to use proper MCP SDK with stdio transport
        try:
            # Create a test script that calls the MCP server
            # This is a simplified implementation - you might want to use the MCP SDK properly
            import tempfile

            # Create a temporary script to interact with MCP server
            script = f"""
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_mcp_tool():
    server_params = StdioServerParameters(
        command="{server.command}",
        args={server.args},
        env={server.env}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Call the tool
            result = await session.call_tool("{tool_name}", {json.dumps(arguments)})
            print(json.dumps(result.model_dump()))

import asyncio
asyncio.run(call_mcp_tool())
"""

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                script_path = f.name

            try:
                # Run the script
                result = subprocess.run(
                    ["python", script_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**subprocess.os.environ, **server.env}
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"MCP tool call failed: {result.stderr}"
                    }

                # Parse result
                output = json.loads(result.stdout)
                return output

            finally:
                # Clean up temporary file
                Path(script_path).unlink(missing_ok=True)

        except Exception as e:
            return {
                "success": False,
                "error": f"MCP tool call failed: {str(e)}"
            }


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None
_mcp_config_mtime: float = 0.0


def _get_config_mtime() -> float:
    """Get the modification time of the MCP config file."""
    config_path = Path(_settings.config_dir) / "mcp.json"
    try:
        return config_path.stat().st_mtime
    except OSError:
        return 0.0


def get_mcp_client(working_dir: Optional[str] = None) -> MCPClient:
    """Get or create the global MCP client instance.

    Automatically reloads if mcp.json has been modified on disk
    (handles multi-worker config sync).
    """
    global _mcp_client, _mcp_config_mtime
    current_mtime = _get_config_mtime()
    if _mcp_client is None or current_mtime != _mcp_config_mtime:
        _mcp_client = MCPClient(working_dir=working_dir)
        _mcp_config_mtime = current_mtime
    return _mcp_client


def reload_mcp_client(working_dir: Optional[str] = None) -> MCPClient:
    """Reload the MCP client (useful after config changes)."""
    global _mcp_client, _mcp_config_mtime
    _mcp_client = MCPClient(working_dir=working_dir)
    _mcp_config_mtime = _get_config_mtime()
    return _mcp_client


def list_mcp_servers() -> List[str]:
    """List all configured MCP servers."""
    client = get_mcp_client()
    return client.list_servers()


def get_mcp_server_info(server_name: str) -> Optional[Dict[str, Any]]:
    """Get info about a specific MCP server."""
    client = get_mcp_client()
    return client.get_server_info(server_name)


def get_all_mcp_servers_info() -> List[Dict[str, Any]]:
    """Get info about all configured MCP servers."""
    client = get_mcp_client()
    return [client.get_server_info(name) for name in client.list_servers()]


def get_default_enabled_mcp_servers() -> List[str]:
    """Get list of MCP server names that are enabled by default."""
    client = get_mcp_client()
    return client.get_default_enabled_servers()


def discover_mcp_tools(server_name: str) -> List[Dict[str, Any]]:
    """Discover tools available on an MCP server (from config only)."""
    client = get_mcp_client()
    return client.discover_tools(server_name)


def discover_mcp_tools_live(server_name: str) -> List[Dict[str, Any]]:
    """
    Discover tools by spawning the actual MCP server process and querying it.

    This connects to the real MCP server via stdio, calls session.list_tools(),
    and returns the discovered tool definitions.

    Args:
        server_name: Name of the MCP server to discover tools from

    Returns:
        List of tool dicts with {name, description, inputSchema}

    Raises:
        ValueError: If server not found or discovery fails
    """
    import tempfile

    client = get_mcp_client()
    server = client.get_server(server_name)
    if not server:
        raise ValueError(f"MCP server '{server_name}' not found")

    # Build the discovery script using safe JSON serialization
    script_config = json.dumps({
        "command": server.command,
        "args": server.args,
        "env": server.env,
    })

    script = f"""
import json
import sys

async def discover():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    config = json.loads({json.dumps(script_config)})
    server_params = StdioServerParameters(
        command=config["command"],
        args=config["args"],
        env=config["env"] or None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = []
            for tool in result.tools:
                tool_dict = {{"name": tool.name, "description": tool.description or ""}}
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    tool_dict["inputSchema"] = tool.inputSchema
                elif hasattr(tool, "input_schema") and tool.input_schema:
                    tool_dict["inputSchema"] = tool.input_schema
                else:
                    tool_dict["inputSchema"] = {{"type": "object", "properties": {{}}}}
                tools.append(tool_dict)
            print(json.dumps(tools))

import asyncio
asyncio.run(discover())
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        env = {**os.environ, **server.env}
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode != 0:
            raise ValueError(f"Tool discovery failed: {result.stderr.strip()}")

        tools = json.loads(result.stdout)
        return tools

    except subprocess.TimeoutExpired:
        raise ValueError(f"Tool discovery timed out after 30s for server '{server_name}'")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse discovery result: {e}")
    finally:
        Path(script_path).unlink(missing_ok=True)


def call_mcp_tool(
    server_name: str,
    tool_name: str,
    arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Call an MCP tool.

    This is a convenience function that uses the global MCP client.
    """
    client = get_mcp_client()
    return client.call_tool(server_name, tool_name, arguments)


def _get_config_path() -> Path:
    """Get the MCP config file path (uses settings.config_dir)."""
    return Path(_settings.config_dir) / "mcp.json"


def _load_raw_config() -> Dict[str, Any]:
    """Load raw config from file."""
    config_path = _get_config_path()
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"mcpServers": {}}


def _save_raw_config(config: Dict[str, Any]) -> None:
    """Save config to file."""
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def add_mcp_server(
    name: str,
    display_name: str,
    description: str,
    command: str,
    args: List[str],
    env: Optional[Dict[str, str]] = None,
    default_enabled: bool = False,
    tools: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Add a new MCP server to the configuration.

    Args:
        name: Server identifier (e.g., "fetch", "time")
        display_name: Display name (e.g., "Fetch", "Time")
        description: Server description
        command: Command to run (e.g., "uvx", "node")
        args: Command arguments
        env: Environment variables
        default_enabled: Whether enabled by default
        tools: List of tool definitions

    Returns:
        The added server info
    """
    config = _load_raw_config()

    if name in config.get("mcpServers", {}):
        raise ValueError(f"MCP server '{name}' already exists")

    server_config = {
        "name": display_name,
        "description": description,
        "command": command,
        "args": args,
        "env": env or {},
        "defaultEnabled": default_enabled,
        "tools": tools or []
    }

    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"][name] = server_config

    _save_raw_config(config)

    # Reload the client to pick up changes
    reload_mcp_client()

    return get_mcp_server_info(name)


def update_mcp_server(
    name: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    default_enabled: Optional[bool] = None,
    tools: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Update an existing MCP server configuration.

    Only provided fields will be updated.
    """
    config = _load_raw_config()

    if name not in config.get("mcpServers", {}):
        raise ValueError(f"MCP server '{name}' not found")

    server_config = config["mcpServers"][name]

    if display_name is not None:
        server_config["name"] = display_name
    if description is not None:
        server_config["description"] = description
    if command is not None:
        server_config["command"] = command
    if args is not None:
        server_config["args"] = args
    if env is not None:
        server_config["env"] = env
    if default_enabled is not None:
        server_config["defaultEnabled"] = default_enabled
    if tools is not None:
        server_config["tools"] = tools

    _save_raw_config(config)
    reload_mcp_client()

    return get_mcp_server_info(name)


def delete_mcp_server(name: str) -> bool:
    """
    Delete an MCP server from the configuration.

    Args:
        name: Server identifier to delete

    Returns:
        True if deleted, False if not found
    """
    config = _load_raw_config()

    if name not in config.get("mcpServers", {}):
        return False

    del config["mcpServers"][name]
    _save_raw_config(config)
    reload_mcp_client()

    return True


# ============ Secrets Management Functions ============

def get_mcp_secret(server_name: str, key_name: str) -> Tuple[Optional[str], str]:
    """Get a secret value. Returns (value, source) where source is 'env', 'secrets', or 'none'."""
    return get_secret(server_name, key_name)


def set_mcp_secret(server_name: str, key_name: str, value: str) -> None:
    """Set a secret value in the secrets file."""
    set_secret(server_name, key_name, value)
    # Reload client to pick up changes
    reload_mcp_client()


def delete_mcp_secret(server_name: str, key_name: str) -> bool:
    """Delete a secret value from the secrets file."""
    result = delete_secret(server_name, key_name)
    if result:
        reload_mcp_client()
    return result


def get_all_secrets_status() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Get secrets status for all MCP servers.

    Returns:
        Dict mapping server_name -> {key_name -> {configured: bool, source: str}}
    """
    client = get_mcp_client()
    result = {}
    for server_name in client.list_servers():
        required_keys = client.get_required_env_vars(server_name)
        if required_keys:
            result[server_name] = get_server_secrets_status(server_name, required_keys)
    return result
