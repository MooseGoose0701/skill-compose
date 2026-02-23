"""
Tools Registry - Defines all available tools with metadata

Each tool has:
- id: Unique identifier
- name: Tool name used by agent
- description: What the tool does
- category: Tool category for grouping
- input_schema: JSON schema for parameters
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class ToolDefinition(BaseModel):
    """Definition of a single tool."""
    id: str
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any]


# Tool categories
TOOL_CATEGORIES = {
    "skill_management": {
        "name": "Skill Management",
        "description": "Tools for discovering and reading skills",
        "icon": "book",
    },
    "code_execution": {
        "name": "Code Execution",
        "description": "Tools for running code and commands",
        "icon": "terminal",
    },
    "code_exploration": {
        "name": "Code Exploration",
        "description": "Tools for searching and reading source code",
        "icon": "search",
    },
    "file_editing": {
        "name": "File Editing",
        "description": "Tools for writing and editing files",
        "icon": "edit",
    },
    "web": {
        "name": "Web",
        "description": "Tools for fetching and searching the web",
        "icon": "globe",
    },
    "output": {
        "name": "Output Management",
        "description": "Tools for reporting and managing output files",
        "icon": "download",
    },
    "user_interaction": {
        "name": "User Interaction",
        "description": "Tools for interactive communication with the user",
        "icon": "message-circle",
    },
}


# Registry of all available tools
TOOLS_REGISTRY: List[ToolDefinition] = [
    # Skill Management Tools
    ToolDefinition(
        id="list_skills",
        name="list_skills",
        description="List all available skills. Use this first to see what skills are available before reading one.",
        category="skill_management",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    ToolDefinition(
        id="get_skill",
        name="get_skill",
        description="Get the full documentation of a specific skill. Use this to learn how to use a library or perform a task before writing code.",
        category="skill_management",
        input_schema={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to read (e.g., 'data-analyzer', 'pdf-converter')",
                },
            },
            "required": ["skill_name"],
        },
    ),
    # Code Execution Tools
    ToolDefinition(
        id="execute_code",
        name="execute_code",
        description="Execute Python code. Variables, imports, and state persist across calls within the same session (powered by IPython kernel). Code runs in an isolated workspace directory, NOT the project root. To access project files, use absolute paths.",
        category="code_execution",
        input_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
            },
            "required": ["code"],
        },
    ),
    ToolDefinition(
        id="bash",
        name="bash",
        description="""Execute a shell command. Use for git, npm, pip, and other CLI tools.

IMPORTANT:
- Commands run in an isolated workspace directory, NOT the project root
- To access project files, use absolute paths
- Use for system commands, not for file operations (use read/write/edit instead)
- Supports optional timeout parameter

Examples:
- bash(command="pip install pandas")
- bash(command="ls -la")""",
        category="code_execution",
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Optional timeout in seconds (default: 120)",
                },
            },
            "required": ["command"],
        },
    ),
    # Code Exploration Tools
    ToolDefinition(
        id="glob",
        name="glob",
        description="""Search for files matching a glob pattern. Use this to find source code files in skill directories.

Examples:
- glob(pattern="**/*.py") - Find all Python files
- glob(pattern="*.md", path="skills/data-analyzer") - Find markdown files in a skill
- glob(pattern="**/*test*.py") - Find test files

Results are sorted by modification time (newest first), limited to 100 files.""",
        category="code_exploration",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '**/*.py', '*.md', '**/test_*.py')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to 'skills' directory. Can be relative or absolute path.",
                },
            },
            "required": ["pattern"],
        },
    ),
    ToolDefinition(
        id="grep",
        name="grep",
        description="""Search for content in files using regex pattern. Use this to find function definitions, class names, or specific code patterns.

Examples:
- grep(pattern="def calculate") - Find function definitions
- grep(pattern="class.*Molecule", include="*.py") - Find Molecule classes in Python files
- grep(pattern="import pandas", path="skills/data-analyzer") - Find pandas imports

Results are sorted by modification time (newest first), limited to 100 matches.""",
        category="code_exploration",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for in file contents",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to 'skills' directory.",
                },
                "include": {
                    "type": "string",
                    "description": "File pattern to include (e.g., '*.py', '*.ts', '*.{py,pyx}')",
                },
            },
            "required": ["pattern"],
        },
    ),
    ToolDefinition(
        id="read",
        name="read",
        description="""Read file contents with line numbers. Use this to read source code files after finding them with glob or grep.

Features:
- Shows line numbers for easy reference
- Supports reading large files in chunks using offset/limit
- Automatically detects and rejects binary files
- Suggests similar files if the requested file is not found

Examples:
- read(file_path="skills/data-analyzer/scripts/main.py") - Read the main module
- read(file_path="...", offset=100, limit=50) - Read lines 101-150""",
        category="code_exploration",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to working directory or absolute)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-based). Default: 0",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of lines to read. Default: 2000",
                },
            },
            "required": ["file_path"],
        },
    ),
    # File Editing Tools
    ToolDefinition(
        id="write",
        name="write",
        description="""Write content to a file. Creates the file if it doesn't exist, overwrites if it does.

IMPORTANT: This will overwrite the entire file. For modifying existing files, prefer using edit instead.

Examples:
- write(file_path="output/report.md", content="# Report\\n...")
- write(file_path="scripts/helper.py", content="def helper():\\n    pass")

Security: Cannot write to sensitive locations (.env, credentials, secrets, .git/)""",
        category="file_editing",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to working directory or absolute)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        },
    ),
    ToolDefinition(
        id="edit",
        name="edit",
        description="""Edit a file by replacing exact string matches. More precise than write for modifications.

IMPORTANT:
- You MUST read the file first using read before editing
- The old_string must match EXACTLY (including whitespace and indentation)
- By default, old_string must be unique in the file. Use replace_all=true to replace all occurrences.

Examples:
- edit(file_path="app.py", old_string="def old_func():", new_string="def new_func():")
- edit(file_path="config.py", old_string="DEBUG = True", new_string="DEBUG = False")
- edit(file_path="app.py", old_string="old_name", new_string="new_name", replace_all=true)

Security: Cannot edit sensitive files (.env, credentials, secrets)""",
        category="file_editing",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace (must match exactly including whitespace)",
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace it with",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "If true, replace all occurrences. If false (default), old_string must be unique.",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    ),
    # Web Tools
    ToolDefinition(
        id="web_fetch",
        name="web_fetch",
        description="""Fetch content from a URL and convert it to markdown.

Use this to read web pages, documentation, or API responses.

Examples:
- web_fetch(url="https://docs.python.org/3/library/json.html", prompt="How to parse JSON?")
- web_fetch(url="https://api.github.com/repos/owner/repo", prompt="Get repo info")

Notes:
- HTML is converted to markdown for easier reading
- Content is truncated at 50KB
- Some sites may block automated requests""",
        category="web",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from",
                },
                "prompt": {
                    "type": "string",
                    "description": "What information to extract from the page",
                },
            },
            "required": ["url", "prompt"],
        },
    ),
    ToolDefinition(
        id="web_search",
        name="web_search",
        description="""Search the web using DuckDuckGo.

Returns up to 10 search results with titles, URLs, and snippets.

Examples:
- web_search(query="Python asyncio tutorial 2024")
- web_search(query="FastAPI best practices")

Notes:
- Results include title, URL, and snippet
- Use web_fetch to read full content of interesting results""",
        category="web",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
            },
            "required": ["query"],
        },
    ),
    # User Interaction Tools
    ToolDefinition(
        id="ask_user",
        name="ask_user",
        description="""Ask the user a question and wait for their response. The current agent run ends and resumes when the user replies.

Supports two modes:
- **Options mode**: Provide predefined choices for the user to select from
- **Free input mode**: Ask an open-ended question (omit options)

Use proactively when:
- Multiple candidates or possibilities need user selection (e.g., matching skills, date columns, target files)
- The user's request is ambiguous — clarify before proceeding
- A destructive or irreversible action needs confirmation

Examples:
- ask_user(question="Which date column should I use for the X axis?", options=["created_at", "updated_at", "published_at"])
- ask_user(question="This will delete 15 files. Continue?", options=["Yes, delete them", "No, cancel"])
- ask_user(question="What format would you like for the output report?")""",
        category="user_interaction",
        input_schema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional predefined answer choices (rendered as buttons). If omitted, user gets a free text input.",
                    "minItems": 2,
                    "maxItems": 6,
                },
            },
            "required": ["question"],
        },
    ),
]


def get_all_tools() -> List[ToolDefinition]:
    """Get all available tools."""
    return TOOLS_REGISTRY


def get_tool_by_id(tool_id: str) -> Optional[ToolDefinition]:
    """Get a tool by its ID."""
    for tool in TOOLS_REGISTRY:
        if tool.id == tool_id:
            return tool
    return None


def get_tools_by_category(category: str) -> List[ToolDefinition]:
    """Get all tools in a category."""
    return [tool for tool in TOOLS_REGISTRY if tool.category == category]


def get_tools_by_ids(tool_ids: List[str]) -> List[ToolDefinition]:
    """Get multiple tools by their IDs."""
    return [tool for tool in TOOLS_REGISTRY if tool.id in tool_ids]


def get_tool_ids() -> List[str]:
    """Get all tool IDs."""
    return [tool.id for tool in TOOLS_REGISTRY]


def get_categories() -> Dict[str, Dict[str, str]]:
    """Get all tool categories with metadata."""
    return TOOL_CATEGORIES


def tools_to_claude_format(tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
    """Convert tools to Claude API format."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in tools
    ]
