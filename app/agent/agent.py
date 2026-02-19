"""
Skills Agent - An async agent that uses skills and tools to complete tasks

The agent:
1. Receives a user request
2. Uses an LLM (via native SDK) to decide what to do
3. Calls tools (list_skills, get_skill, execute_code, etc.)
4. Loops until task is complete
5. Returns the final result

Supports multiple LLM providers:
- Anthropic (Claude)
- OpenRouter (access to many models)
- OpenAI (GPT-4o, o1)
- Google (Gemini)
"""
import asyncio
import copy
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field, asdict

from app.config import settings
from app.agent.tools import TOOLS, call_tool, acall_tool, get_tools_for_agent, BASE_TOOLS, get_mcp_client, WORKING_DIR
from app.core.tools_registry import get_all_tools, get_tools_by_ids, tools_to_claude_format
from app.llm import LLMClient, LLMTextBlock, LLMToolCall
from app.llm.models import MODEL_CONTEXT_LIMITS, DEFAULT_CONTEXT_LIMIT, get_context_limit

if TYPE_CHECKING:
    from app.agent.event_stream import EventStream

# Context window compression constants
COMPRESSION_THRESHOLD_RATIO = 0.5  # Trigger compression when input tokens exceed 50% of limit
MAX_RECENT_TURNS = 3               # Keep at most 3 recent logical turns
RECENT_TURNS_TOKEN_BUDGET = 0.25   # Recent turns can use up to 25% of context limit
CHARS_PER_TOKEN = 3.5              # Conservative estimate for mixed CJK/English text

# Tool result truncation for LLM messages
TOOL_RESULT_MAX_CHARS = 2000          # Max chars for tool results sent to LLM
TOOL_RESULT_HEAD_CHARS = 1500         # Head portion to keep
TOOL_RESULT_TAIL_CHARS = 500          # Tail portion to keep
# Tools whose results should NOT be truncated (LLM needs full content)
TOOL_RESULT_NO_TRUNCATE = {"list_skills", "get_skill"}


def truncate_tool_result(tool_name: str, result: str) -> str:
    """Truncate tool result for LLM messages. Preserves head + tail for error visibility."""
    if tool_name in TOOL_RESULT_NO_TRUNCATE:
        return result
    if len(result) <= TOOL_RESULT_MAX_CHARS:
        return result
    return (
        result[:TOOL_RESULT_HEAD_CHARS]
        + f"\n\n... [truncated {len(result) - TOOL_RESULT_HEAD_CHARS - TOOL_RESULT_TAIL_CHARS} chars] ...\n\n"
        + result[-TOOL_RESULT_TAIL_CHARS:]
    )


SUMMARY_SYSTEM_PROMPT = """You have been given a partial transcript of a conversation between a user and an AI assistant. Write a summary that provides continuity so the assistant can continue making progress in a future context where the raw history is replaced by this summary.

You must wrap your summary in a <summary></summary> block with the following sections:

<summary>
## Primary Request and Intent
The user's explicit goals and overall task. Include any clarifications or constraints the user provided.

## Key Technical Concepts
Technologies, frameworks, models, APIs, and domain-specific terms discussed. Include exact model names, package versions, and configuration values.

## Files and Code Sections
Specific files read, created, or modified, with brief notes on what was done. Include exact file paths. For critical code changes, preserve the key snippets verbatim.

## Problem Solving
Completed troubleshooting efforts — what was tried, what worked, what failed and why. Include exact error messages if relevant.

## All User Messages
Every non-tool-use user statement, summarized chronologically. Capture feedback, course corrections, and preferences.

## Current State
What was just completed immediately before this summary. Be specific about the last action taken and its result.

## Pending Tasks
Outstanding work items and next steps, in priority order. Include any blockers.
</summary>

Be concise but thorough. Preserve exact file paths, variable names, model names, API parameters, and configuration values. Do not omit details that would be needed to continue the work."""


@dataclass
class LLMCall:
    """Record of a single LLM API call."""
    turn: int
    timestamp: str
    model: str
    request_messages: List[Dict]
    response_content: List[Dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int


@dataclass
class AgentStep:
    """A single step in the agent's execution."""
    role: str  # "assistant" or "tool"
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict] = None
    tool_result: Optional[str] = None


@dataclass
class AgentResult:
    """Result of agent execution."""
    success: bool
    answer: str
    steps: List[AgentStep] = field(default_factory=list)
    llm_calls: List[LLMCall] = field(default_factory=list)
    total_turns: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    error: Optional[str] = None
    log_file: Optional[str] = None
    skills_used: List[str] = field(default_factory=list)
    output_files: List[Dict] = field(default_factory=list)
    final_messages: List[Dict] = field(default_factory=list)


@dataclass
class StreamEvent:
    """Event emitted during streaming execution."""
    event_type: str  # "turn_start", "text_delta", "assistant", "tool_call", "tool_result", "output_file", "turn_complete", "complete", "error"
    turn: int
    data: Dict[str, Any] = field(default_factory=dict)


BASE_SYSTEM_PROMPT = """You are a helpful assistant with access to skills and tools.
{custom_instructions}
## Current Date
Today is {current_date}. Use this date when searching for recent news or time-sensitive information.

## Equipped Skills
{equipped_skills_section}

**IMPORTANT:** When user request matches a skill's trigger words, you MUST:
1. Call `get_skill(skill_name)` to read the full documentation
2. Follow the skill's workflow exactly as documented
3. Use the tools specified in the skill (e.g., tavily_search for topic-collector)

## Available Tools

### Skill Management
- list_skills: List all available skills
- get_skill: Read skill documentation

### Code Execution
- execute_code: Execute Python code (variables persist across calls via IPython kernel)
- execute_command: Execute shell commands

### Code Exploration (for reading skill source code)
- glob_files: Search for files by pattern (e.g., "**/*.py")
- grep_search: Search for content in files using regex
- read_file: Read file contents with line numbers

{mcp_tools_section}

## Workflow
1. First, list available skills to see what's available
2. Read relevant skill documentation to learn the API
3. **If you need more details about the implementation**, use the code exploration tools:
   - Use `glob_files` to find source files in the skill directory
   - Use `grep_search` to find specific functions, classes, or patterns
   - Use `read_file` to read the actual source code
4. Write and execute code based on what you learned
5. If code fails, debug and retry
6. Return the final result to the user

## Code Exploration Tips
When using skills, you can explore the source code to understand:
- Function signatures and parameters
- Implementation details
- Available classes and methods
- Example usage patterns

Example workflow:
```
# Find all Python files in a skill
glob_files(pattern="**/*.py", path="skills/data-analyzer")

# Search for a specific function
grep_search(pattern="def analyze", include="*.py", path="skills/data-analyzer")

# Read the source file
read_file(file_path="skills/data-analyzer/scripts/main.py")
```

## Working Directories
- `glob`, `grep`, `read`, `write`, `edit` resolve relative paths from the **project root** ({working_dir})
- `execute_code` and `bash` run in an **isolated workspace directory** (different from project root). The current working directory (cwd) IS the workspace.
- **Saving output files:** Use relative paths directly (e.g., `open("output.png", "wb")`, `df.to_csv("result.csv")`). They will be saved to the workspace and auto-detected as downloadable output files. **NEVER use `/tmp/` for output files** — files in `/tmp/` cannot be detected or downloaded.
- **Reading project files:** Use absolute paths: `bash(command="python {working_dir}/skills/my-skill/scripts/main.py")`

## Important Notes
- Always read skill documentation before writing code
- Variables, imports, and state persist across execute_code calls within the same session
- If the kernel crashes, it automatically falls back to subprocess mode (variables won't persist)
- Use code exploration tools when skill docs are insufficient
- When task is complete, provide a clear final answer
"""


def _build_mcp_tools_section(tools: list) -> str:
    """Build the MCP tools section for system prompt."""
    # Get MCP tool names (tools not in BASE_TOOLS)
    base_tool_names = set(t["name"] for t in BASE_TOOLS)
    mcp_tools = [t for t in tools if t["name"] not in base_tool_names]

    if not mcp_tools:
        return ""

    lines = ["### MCP Tools (External Services)"]
    for tool in mcp_tools:
        # Get first line of description
        desc = tool.get("description", "").split("\n")[0].strip()
        lines.append(f"- {tool['name']}: {desc}")

    return "\n".join(lines)


class SkillsAgent:
    """Agent that uses skills and tools to complete tasks."""

    def __init__(
        self,
        model: str = None,
        model_provider: str = None,
        max_turns: int = 60,
        verbose: bool = True,
        log_dir: str = "./logs",
        allowed_skills: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None,
        equipped_mcp_servers: Optional[List[str]] = None,
        custom_system_prompt: Optional[str] = None,
        executor_name: Optional[str] = None,
    ):
        # Model configuration
        self.model_provider = model_provider or settings.default_model_provider
        self.model = model or settings.default_model_name
        self.max_turns = max_turns
        self.verbose = verbose
        self.log_dir = log_dir
        self.allowed_skills = allowed_skills  # None means all skills are available
        self.allowed_tools = allowed_tools  # None means all tools are available
        self.equipped_mcp_servers = equipped_mcp_servers  # None means default MCP servers
        self.executor_name = executor_name  # Remote executor for code execution

        # Initialize LLM client with provider-specific configuration
        self.client = LLMClient(
            provider=self.model_provider,
            model=self.model,
        )

        # Build the tools list and create workspace
        # Workspace is created per-agent instance for request isolation
        # If executor_name is provided, code execution runs in remote container
        all_tools, all_tool_functions, self.workspace = get_tools_for_agent(
            equipped_mcp_servers=equipped_mcp_servers,
            skill_names=allowed_skills,
            executor_name=executor_name,
        )

        # Filter tools if allowed_tools is specified
        # Note: MCP tools from equipped servers are always included (not filtered out)
        if allowed_tools is not None:
            # Get MCP tool names from equipped servers
            mcp_tool_names = set()
            if equipped_mcp_servers:
                mcp_client = get_mcp_client()
                for server_name in equipped_mcp_servers:
                    server = mcp_client.get_server(server_name)
                    if server:
                        for tool in server.tools:
                            mcp_tool_names.add(tool.name)

            # Include tool if: in allowed_tools OR is an MCP tool from equipped server
            self.tools = [t for t in all_tools if t["name"] in allowed_tools or t["name"] in mcp_tool_names]
            self.tool_functions = {k: v for k, v in all_tool_functions.items() if k in allowed_tools or k in mcp_tool_names}
        else:
            self.tools = all_tools
            self.tool_functions = all_tool_functions

        # Build dynamic system prompt with equipped skills and MCP tools info
        skills_section = self._build_equipped_skills_section()
        mcp_section = _build_mcp_tools_section(self.tools)
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Build custom instructions section
        custom_instructions = ""
        if custom_system_prompt:
            custom_instructions = f"\n## Custom Instructions\n{custom_system_prompt}\n"

        self.system_prompt = BASE_SYSTEM_PROMPT.format(
            current_date=current_date,
            equipped_skills_section=skills_section,
            mcp_tools_section=mcp_section,
            custom_instructions=custom_instructions,
            working_dir=WORKING_DIR
        )

        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)

    def _build_equipped_skills_section(self) -> str:
        """Build the equipped skills section for system prompt."""
        from app.agent.tools import _fetch_skill_content_from_registry
        from app.core.skill_config import check_skill_env_ready

        if not self.allowed_skills:
            return "No skills equipped. Use `list_skills` to see available skills."

        lines = ["The following skills are equipped and ready to use:\n"]

        for skill_name in self.allowed_skills:
            try:
                registry_skill = _fetch_skill_content_from_registry(skill_name)
                if not registry_skill:
                    lines.append(f"### {skill_name}")
                    lines.append("(Skill not found)")
                    lines.append("")
                    continue

                description = registry_skill.get("description", "")
                content_text = registry_skill.get("content", "")

                triggers = []
                # Look for trigger words in content
                content_lower = content_text.lower()
                if "trigger" in content_lower:
                    # Extract trigger section
                    for line in content_text.split("\n"):
                        if "- \"" in line or "- '" in line or '- "' in line:
                            trigger = line.strip().lstrip("-").strip().strip('"\'')
                            if trigger and len(trigger) < 50:
                                triggers.append(trigger)

                lines.append(f"### {skill_name}")
                if description:
                    lines.append(f"**Description:** {description}")
                if triggers:
                    lines.append(f"**Triggers:** {', '.join(triggers[:5])}")

                # Check for missing environment variables
                try:
                    ready, missing = check_skill_env_ready(skill_name)
                    if not ready and missing:
                        lines.append(f"**WARNING:** Missing environment variables: {', '.join(missing)}")
                        lines.append("This skill may not work properly until these are configured.")
                except Exception:
                    pass  # Silently ignore if config check fails

                lines.append("")
            except Exception as e:
                lines.append(f"### {skill_name}")
                lines.append(f"(Error loading skill: {e})")
                lines.append("")

        return "\n".join(lines)

    def _get_context_limit(self) -> int:
        """Get the context window limit for the current model."""
        return get_context_limit(self.model_provider, self.model)

    def _should_compress(self, last_input_tokens: int) -> bool:
        """Check if context compression is needed based on the last API call's input token count."""
        threshold = int(self._get_context_limit() * COMPRESSION_THRESHOLD_RATIO)
        return last_input_tokens > threshold

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """Check if an LLM error is retryable (transient network/server issue)."""
        err_str = str(error).lower()
        retryable_patterns = [
            "connection", "timeout", "rate limit", "rate_limit",
            "429", "500", "502", "503", "504",
            "overloaded", "service unavailable", "service_unavailable",
            "server error", "internal error",
            "incomplete chunked read", "peer closed",
            "reset by peer", "broken pipe", "fetch failed",
        ]
        return any(p in err_str for p in retryable_patterns)

    def _serialize_messages_for_summary(self, messages: List[Dict]) -> str:
        """Serialize messages into readable text for summarization.

        Truncates tool_use inputs to 500 chars and tool_results to 1000 chars.
        If total text exceeds 100K chars, takes first and last halves with a truncation marker.
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, str):
                parts.append(f"[{role}]: {content}")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type == "text":
                            parts.append(f"[{role}]: {block.get('text', '')}")
                        elif block_type == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_input = json.dumps(block.get("input", {}), ensure_ascii=False)
                            if len(tool_input) > 500:
                                tool_input = tool_input[:500] + "...(truncated)"
                            parts.append(f"[{role} -> tool_use({tool_name})]: {tool_input}")
                        elif block_type == "tool_result":
                            tool_content = block.get("content", "")
                            if isinstance(tool_content, str) and len(tool_content) > 1000:
                                tool_content = tool_content[:1000] + "...(truncated)"
                            parts.append(f"[tool_result]: {tool_content}")
                    elif isinstance(block, str):
                        parts.append(f"[{role}]: {block}")

        text = "\n\n".join(parts)

        # If total text exceeds 100K characters, take head + tail
        max_chars = 100_000
        if len(text) > max_chars:
            half = max_chars // 2
            text = text[:half] + "\n\n[... truncated middle section ...]\n\n" + text[-half:]

        return text

    async def _compress_messages(self, messages: List[Dict]) -> tuple:
        """Compress old messages into a structured summary, keeping recent turns.

        Returns:
            (compressed_messages, summary_input_tokens, summary_output_tokens)
        """
        # Find logical turn boundaries: indices of real user messages (not tool_result).
        turn_boundaries = []
        for i, msg in enumerate(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                turn_boundaries.append(i)
            elif isinstance(content, list):
                is_tool_result = any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in content
                )
                if not is_tool_result:
                    turn_boundaries.append(i)

        # Need at least 2 turn boundaries (1 to compress + 1 to keep)
        if len(turn_boundaries) < 2:
            if self.verbose:
                print("[Context Compression] Not enough logical turns to compress, skipping")
            return messages, 0, 0

        # Dynamically select how many recent turns to keep within token budget.
        max_recent_tokens = int(self._get_context_limit() * RECENT_TURNS_TOKEN_BUDGET)
        accumulated_tokens = 0
        keep_turns = 0

        for idx in range(len(turn_boundaries) - 1, -1, -1):
            turn_start = turn_boundaries[idx]
            turn_end = turn_boundaries[idx + 1] if idx + 1 < len(turn_boundaries) else len(messages)
            turn_chars = sum(
                len(json.dumps(messages[i].get("content", ""), ensure_ascii=False))
                for i in range(turn_start, turn_end)
            )
            turn_tokens = turn_chars / CHARS_PER_TOKEN
            if accumulated_tokens + turn_tokens > max_recent_tokens and keep_turns >= 1:
                break
            accumulated_tokens += turn_tokens
            keep_turns += 1
            if keep_turns >= MAX_RECENT_TURNS:
                break

        # Ensure we have something left to compress
        if keep_turns >= len(turn_boundaries):
            if self.verbose:
                print("[Context Compression] All turns fit in budget, skipping")
            return messages, 0, 0

        split_point = turn_boundaries[-keep_turns]

        if self.verbose:
            print(f"[Context Compression] Keeping {keep_turns} recent logical turns (~{int(accumulated_tokens)} tokens)")

        old_messages = messages[:split_point]
        recent_messages = messages[split_point:]

        if self.verbose:
            print(f"\n[Context Compression] Compressing {len(old_messages)} old messages, keeping {len(recent_messages)} recent messages")

        # Serialize old messages for summarization
        serialized = self._serialize_messages_for_summary(old_messages)

        # Call LLM to generate a structured summary
        summary_input_tokens = 0
        summary_output_tokens = 0
        try:
            summary_response = await self.client.acreate(
                messages=[{
                    "role": "user",
                    "content": f"Please summarize the following conversation:\n\n{serialized}"
                }],
                system=SUMMARY_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            summary_input_tokens = summary_response.usage.input_tokens
            summary_output_tokens = summary_response.usage.output_tokens

            summary_text = summary_response.text_content

            if self.verbose:
                print(f"[Context Compression] Summary generated ({summary_input_tokens} in / {summary_output_tokens} out)")

        except Exception as e:
            # Fallback: use truncated serialized text as summary
            if self.verbose:
                print(f"[Context Compression] Summary API call failed: {e}, using fallback")
            summary_text = serialized
            if len(summary_text) > 10000:
                summary_text = summary_text[:5000] + "\n\n[... truncated ...]\n\n" + summary_text[-5000:]

        # Build the compression message.
        if "<summary>" not in summary_text:
            summary_text = f"<summary>\n{summary_text}\n</summary>"

        compression_content = (
            "This session is being continued from a previous conversation that ran out of context. "
            "The summary below covers the earlier portion of the conversation.\n\n"
            f"{summary_text}\n\n"
            "Please continue the conversation from where we left off without asking the user any further questions. "
            "Continue with the last task that you were asked to work on."
        )

        # Build compressed messages: summary as first user message + recent messages
        compressed = [{"role": "user", "content": compression_content}]

        # If recent_messages starts with a user message, we need an assistant acknowledgment
        if recent_messages and recent_messages[0].get("role") == "user":
            compressed.append({
                "role": "assistant",
                "content": [{"type": "text", "text": "I understand the context. Let me continue from where we left off."}]
            })

        compressed.extend(recent_messages)

        if self.verbose:
            print(f"[Context Compression] Messages reduced from {len(messages)} to {len(compressed)}")

        return compressed, summary_input_tokens, summary_output_tokens

    def _save_log(self, request: str, result: AgentResult) -> str:
        """Save the conversation log to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.log_dir, f"agent_log_{timestamp}.json")

        log_data = {
            "timestamp": timestamp,
            "request": request,
            "model": self.model,
            "success": result.success,
            "total_turns": result.total_turns,
            "total_input_tokens": result.total_input_tokens,
            "total_output_tokens": result.total_output_tokens,
            "answer": result.answer,
            "llm_calls": [asdict(call) for call in result.llm_calls],
            "steps": [asdict(step) for step in result.steps],
        }

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

        return log_file

    async def run(
        self,
        request: str,
        conversation_history: Optional[List[Dict]] = None,
        image_contents: Optional[List[Dict]] = None,
        event_stream: Optional["EventStream"] = None,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> AgentResult:
        """
        Run the agent on a user request (async).

        When event_stream is provided, pushes StreamEvent objects for SSE streaming.
        When event_stream is None, runs silently and returns the result.

        Args:
            request: The user's request/task
            conversation_history: Optional list of previous messages for multi-turn conversation.
            image_contents: Optional list of Anthropic-format image blocks.
            event_stream: Optional EventStream for pushing streaming events.
            cancellation_event: Optional asyncio.Event — set to signal cancellation.

        Returns:
            AgentResult with the final answer and execution steps
        """
        streaming = event_stream is not None

        # Build the user message content (text or multipart with images)
        if image_contents:
            user_content = image_contents + [{"type": "text", "text": request}]
        else:
            user_content = request

        # Build messages from conversation history + new request
        if conversation_history:
            messages = list(conversation_history)  # Copy to avoid mutation
            messages.append({"role": "user", "content": user_content})
        else:
            messages = [{"role": "user", "content": user_content}]

        steps: List[AgentStep] = []
        llm_calls: List[LLMCall] = []
        used_skills: set = set()
        output_files: List[Dict] = []
        output_file_paths: set = set()  # For deduplication
        turns = 0
        total_input_tokens = 0
        total_output_tokens = 0
        last_input_tokens = 0

        while turns < self.max_turns:
            # Check cancellation
            if cancellation_event and cancellation_event.is_set():
                if self.verbose:
                    print("\n[Cancelled] Agent execution cancelled by user")
                break

            turns += 1

            # Context compression check
            if last_input_tokens > 0 and self._should_compress(last_input_tokens):
                if self.verbose:
                    print(f"\n[Context Compression] Input tokens ({last_input_tokens}) exceeded threshold, compressing...")
                messages, s_in, s_out = await self._compress_messages(messages)
                total_input_tokens += s_in
                total_output_tokens += s_out

                if streaming:
                    await event_stream.push(StreamEvent(
                        event_type="context_compressed",
                        turn=turns,
                        data={
                            "previous_tokens": last_input_tokens,
                            "context_limit": self._get_context_limit(),
                        }
                    ))

            # Emit turn start event
            if streaming:
                await event_stream.push(StreamEvent(
                    event_type="turn_start",
                    turn=turns,
                    data={"max_turns": self.max_turns}
                ))

            if self.verbose:
                print(f"\n{'='*50}")
                print(f"Turn {turns}")
                print(f"{'='*50}")

            # Call LLM — streaming vs non-streaming
            response = None

            if streaming:
                # Streaming: yield text deltas, collect final response
                try:
                    async for resp in self.client.acreate_stream(
                        messages=messages,
                        system=self.system_prompt,
                        tools=self.tools,
                        max_tokens=16384,
                    ):
                        # Check cancellation during streaming
                        if cancellation_event and cancellation_event.is_set():
                            break

                        if resp.is_delta:
                            for block in resp.content:
                                if isinstance(block, LLMTextBlock) and block.text:
                                    await event_stream.push(StreamEvent(
                                        event_type="text_delta",
                                        turn=turns,
                                        data={"text": block.text}
                                    ))
                        else:
                            response = resp
                except Exception as stream_err:
                    if self.verbose:
                        print(f"\n[Stream Error] {stream_err}")
                    if self._is_retryable_error(stream_err):
                        # Retry with exponential backoff (up to 3 attempts)
                        for attempt in range(1, 4):
                            delay = 2 ** attempt  # 2s, 4s, 8s
                            if self.verbose:
                                print(f"[Stream Retry] Attempt {attempt}/3 with non-streaming call after {delay}s...")
                            await asyncio.sleep(delay)
                            try:
                                response = await self.client.acreate(
                                    messages=messages,
                                    system=self.system_prompt,
                                    tools=self.tools,
                                    max_tokens=16384,
                                )
                                break  # Success
                            except Exception as retry_err:
                                if self.verbose:
                                    print(f"[Stream Retry] Attempt {attempt}/3 failed: {retry_err}")
                                if attempt == 3 or not self._is_retryable_error(retry_err):
                                    break  # Give up
            else:
                # Non-streaming: single call with retry
                for attempt in range(4):  # 1 initial + 3 retries
                    try:
                        response = await self.client.acreate(
                            messages=messages,
                            system=self.system_prompt,
                            tools=self.tools,
                            max_tokens=16384,
                        )
                        break
                    except Exception as call_err:
                        if attempt < 3 and self._is_retryable_error(call_err):
                            delay = 2 ** (attempt + 1)
                            if self.verbose:
                                print(f"\n[LLM Retry] Attempt {attempt+1}/3 failed: {call_err}")
                                print(f"[LLM Retry] Retrying after {delay}s...")
                            await asyncio.sleep(delay)
                        else:
                            if self.verbose:
                                print(f"\n[LLM Error] Non-retryable: {call_err}")
                            break

            # Check cancellation after LLM call
            if cancellation_event and cancellation_event.is_set():
                if self.verbose:
                    print("\n[Cancelled] Agent execution cancelled by user")
                break

            # Guard against missing response
            if response is None:
                error_msg = "LLM stream failed and retry was unsuccessful"
                if streaming:
                    await event_stream.push(StreamEvent(
                        event_type="error",
                        turn=turns,
                        data={"message": error_msg}
                    ))
                result = AgentResult(
                    success=False,
                    answer=error_msg,
                    steps=steps,
                    llm_calls=llm_calls,
                    total_turns=turns,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    error=error_msg,
                    skills_used=sorted(used_skills),
                    output_files=output_files,
                    final_messages=messages,
                )
                if streaming:
                    await event_stream.push(StreamEvent(
                        event_type="complete",
                        turn=turns,
                        data={
                            "success": False,
                            "answer": error_msg,
                            "total_turns": turns,
                            "total_input_tokens": total_input_tokens,
                            "total_output_tokens": total_output_tokens,
                            "skills_used": sorted(used_skills),
                            "output_files": output_files,
                        }
                    ))
                    await event_stream.close()
                return result

            # Record token usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            last_input_tokens = input_tokens

            if self.verbose:
                print(f"Stop reason: {response.stop_reason}")
                print(f"Tokens: {input_tokens} in / {output_tokens} out")

            # Process response
            assistant_content = []
            tool_calls = []

            for block in response.content:
                if isinstance(block, LLMTextBlock):
                    assistant_content.append({"type": "text", "text": block.text})
                    if self.verbose:
                        print(f"Assistant: {block.text[:3000]}")
                        if len(block.text) > 3000:
                            print('...(truncated)')

                    steps.append(AgentStep(
                        role="assistant",
                        content=block.text,
                    ))

                elif isinstance(block, LLMToolCall):
                    tool_input = copy.deepcopy(block.input) if block.input else {}
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": tool_input,
                    })
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": tool_input,
                    })

                    if streaming:
                        await event_stream.push(StreamEvent(
                            event_type="tool_call",
                            turn=turns,
                            data={
                                "tool_name": block.name,
                                "tool_input": tool_input,
                            }
                        ))

            # Add assistant message
            messages.append({"role": "assistant", "content": assistant_content})

            # Record LLM call
            llm_calls.append(LLMCall(
                turn=turns,
                timestamp=datetime.now().isoformat(),
                model=self.model,
                request_messages=messages[:-1],  # Messages before this response
                response_content=assistant_content,
                stop_reason=response.stop_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ))

            # Handle max_tokens truncation — tool calls may be incomplete
            if response.stop_reason == "max_tokens" and tool_calls:
                if self.verbose:
                    print(f"\n[Warning] Response truncated (max_tokens). Discarding {len(tool_calls)} potentially incomplete tool call(s).")

                truncation_msg = (
                    "Your previous response was truncated because it exceeded the maximum output length. "
                    "The tool call(s) were incomplete and could not be executed. "
                    "Please try again with a shorter approach — for example, break the task into smaller steps "
                    "or generate less code at once."
                )
                tool_results = []
                for tool_call in tool_calls:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": json.dumps({"error": truncation_msg}),
                        "is_error": True,
                    })
                    steps.append(AgentStep(
                        role="tool",
                        content=json.dumps({"error": "Response truncated (max_tokens) — tool call incomplete"}),
                        tool_name=tool_call["name"],
                        tool_input=tool_call["input"],
                    ))
                    if streaming:
                        await event_stream.push(StreamEvent(
                            event_type="tool_result",
                            turn=turns,
                            data={
                                "tool_name": tool_call["name"],
                                "tool_result": "Error: Response truncated (max_tokens). Tool call was incomplete.",
                                "tool_input": tool_call["input"],
                            }
                        ))
                messages.append({"role": "user", "content": tool_results})
                continue

            # If no tool calls, we're done — unless there's a steering message
            if response.stop_reason == "end_turn" and not tool_calls:
                # Check for steering message before finishing
                if event_stream and event_stream.has_injection():
                    steering_msg = event_stream.get_injection_nowait()
                    if steering_msg:
                        messages.append({
                            "role": "user",
                            "content": f"[User Steering Message]: {steering_msg}"
                        })
                        if streaming:
                            await event_stream.push(StreamEvent(
                                event_type="steering_received",
                                turn=turns,
                                data={"message": steering_msg}
                            ))
                        continue  # Don't finish, loop back to LLM with steering message

                final_answer = response.text_content

                result = AgentResult(
                    success=True,
                    answer=final_answer,
                    steps=steps,
                    llm_calls=llm_calls,
                    total_turns=turns,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    skills_used=sorted(used_skills),
                    output_files=output_files,
                    final_messages=messages,
                )
                result.log_file = self._save_log(request, result)

                if streaming:
                    await event_stream.push(StreamEvent(
                        event_type="complete",
                        turn=turns,
                        data={
                            "success": True,
                            "answer": final_answer,
                            "total_turns": turns,
                            "total_input_tokens": total_input_tokens,
                            "total_output_tokens": total_output_tokens,
                            "skills_used": sorted(used_skills),
                            "output_files": output_files,
                            "final_messages": messages,
                        }
                    ))
                    await event_stream.close()

                return result

            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                # Check cancellation before each tool
                if cancellation_event and cancellation_event.is_set():
                    if self.verbose:
                        print("\n[Cancelled] Agent execution cancelled before tool execution")
                    break

                tool_name = tool_call["name"]

                if self.verbose:
                    print(f"\nTool: {tool_name}")
                    print(f"Input: {json.dumps(tool_call['input'], ensure_ascii=False)[:3000]}")

                tool_result = await acall_tool(
                    tool_name,
                    tool_call["input"],
                    allowed_skills=self.allowed_skills,
                    tool_functions=self.tool_functions
                )

                # Track actually used skills
                if tool_name == "get_skill" and tool_call["input"].get("skill_name"):
                    used_skills.add(tool_call["input"]["skill_name"])

                if self.verbose:
                    print(f"Result: {tool_result[:3000]}")
                    if len(tool_result) > 3000:
                        print('...(truncated)')

                # Truncate tool result for LLM context (preserve full result for logs/steps)
                llm_result = truncate_tool_result(tool_name, tool_result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": llm_result,
                })

                steps.append(AgentStep(
                    role="tool",
                    content=tool_result,
                    tool_name=tool_name,
                    tool_input=tool_call["input"],
                    tool_result=tool_result,
                ))

                if streaming:
                    # Emit tool result event (truncate for SSE display)
                    await event_stream.push(StreamEvent(
                        event_type="tool_result",
                        turn=turns,
                        data={
                            "tool_name": tool_name,
                            "tool_input": tool_call["input"],
                            "tool_result": tool_result[:3000],
                        }
                    ))

                # Auto-detect output files from execute_code/bash/write
                if tool_name in ("execute_code", "bash", "write"):
                    try:
                        rd = json.loads(tool_result)
                        for nf in rd.get("new_files", []):
                            url = nf.get("download_url", "")
                            if url and url not in output_file_paths:
                                output_file_paths.add(url)
                                file_id = str(uuid.uuid4())
                                nf["file_id"] = file_id
                                output_files.append(nf)
                                if streaming:
                                    await event_stream.push(StreamEvent(
                                        event_type="output_file",
                                        turn=turns,
                                        data={
                                            "file_id": file_id,
                                            "filename": nf.get("filename"),
                                            "size": nf.get("size"),
                                            "content_type": nf.get("content_type"),
                                            "download_url": nf.get("download_url"),
                                        }
                                    ))
                    except (json.JSONDecodeError, TypeError):
                        pass

            # If cancelled during tool execution, break out
            if cancellation_event and cancellation_event.is_set():
                break

            # Add tool results
            messages.append({"role": "user", "content": tool_results})

            # Check for steering message injection after tool results
            if event_stream and event_stream.has_injection():
                steering_msg = event_stream.get_injection_nowait()
                if steering_msg:
                    messages.append({
                        "role": "user",
                        "content": f"[User Steering Message]: {steering_msg}"
                    })
                    if streaming:
                        await event_stream.push(StreamEvent(
                            event_type="steering_received",
                            turn=turns,
                            data={"message": steering_msg}
                        ))

            # Emit turn_complete checkpoint (all tool_use/tool_result pairs matched)
            if streaming:
                await event_stream.push(StreamEvent(
                    event_type="turn_complete",
                    turn=turns,
                    data={"messages_snapshot": messages.copy()}
                ))

        # Exited the loop — either max turns or cancellation

        # Determine if cancelled
        was_cancelled = cancellation_event and cancellation_event.is_set()

        if was_cancelled:
            final_answer = "Agent execution was cancelled."
            error_msg = "cancelled"
        else:
            # Max turns reached — give Claude one final turn to summarize progress
            if self.verbose:
                print(f"\n[Max Turns] Reached {self.max_turns} turns, requesting final summary...")

            messages.append({
                "role": "user",
                "content": (
                    f"You have reached the maximum number of turns ({self.max_turns}). "
                    "You cannot make any more tool calls. Please provide a final summary of "
                    "what you have accomplished so far and what remains to be done."
                ),
            })

            final_answer = "Max turns reached without completing the task."
            error_msg = "max_turns_exceeded"
            try:
                final_response = await self.client.acreate(
                    messages=messages,
                    system=self.system_prompt,
                    max_tokens=4096,
                )
                final_input = final_response.usage.input_tokens
                final_output = final_response.usage.output_tokens
                total_input_tokens += final_input
                total_output_tokens += final_output

                final_answer = final_response.text_content
                if final_answer:
                    steps.append(AgentStep(role="assistant", content=final_answer))
                    if streaming:
                        await event_stream.push(StreamEvent(
                            event_type="assistant",
                            turn=turns + 1,
                            data={"content": final_answer}
                        ))
            except Exception as e:
                if self.verbose:
                    print(f"[Max Turns] Final summary call failed: {e}")

        result = AgentResult(
            success=False,
            answer=final_answer,
            steps=steps,
            llm_calls=llm_calls,
            total_turns=turns,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            error=error_msg,
            skills_used=sorted(used_skills),
            output_files=output_files,
            final_messages=messages,
        )
        result.log_file = self._save_log(request, result)

        if streaming:
            await event_stream.push(StreamEvent(
                event_type="complete",
                turn=turns,
                data={
                    "success": False,
                    "answer": final_answer,
                    "total_turns": turns,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "error": error_msg,
                    "output_files": output_files,
                    "final_messages": messages,
                }
            ))
            await event_stream.close()

        return result

    def run_sync(
        self,
        request: str,
        conversation_history: Optional[List[Dict]] = None,
        image_contents: Optional[List[Dict]] = None,
    ) -> AgentResult:
        """Synchronous wrapper for background tasks (registry.py).

        Creates a new event loop and runs the async run() method.
        Must NOT be called from within an existing event loop.
        """
        return asyncio.run(self.run(request, conversation_history, image_contents))

    def cleanup(self) -> None:
        """
        Cleanup the agent's workspace.

        Call this when the agent request is complete to free resources.
        """
        if hasattr(self, 'workspace') and self.workspace:
            self.workspace.cleanup()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup workspace."""
        self.cleanup()
        return False
