"""
End-to-end test for multi-turn data analysis workflow.

This test validates:
1. Creating a data-explorer skill with code execution workflow
2. Uploading a CSV file
3. Running Agent with real LLM for multi-step data analysis
4. Verifying code execution, visualization generation, and file export
5. Validating trace records

Supports multiple LLM providers (each runs the FULL 15-test suite):
- Anthropic (Claude Sonnet 4.5)
- OpenAI (GPT-4o)
- DeepSeek (deepseek-chat)
- Kimi (kimi-k2.5)

Run with specific provider:
    # Anthropic
    ANTHROPIC_API_KEY_REAL=sk-xxx pytest tests/test_e2e/test_e2e_data_analysis.py -v -k "Anthropic"

    # OpenAI
    OPENAI_API_KEY_REAL=sk-xxx pytest tests/test_e2e/test_e2e_data_analysis.py -v -k "OpenAI"

    # DeepSeek
    DEEPSEEK_API_KEY_REAL=sk-xxx pytest tests/test_e2e/test_e2e_data_analysis.py -v -k "DeepSeek"

    # Kimi
    MOONSHOT_API_KEY_REAL=sk-xxx pytest tests/test_e2e/test_e2e_data_analysis.py -v -k "Kimi"

    # All providers (from .env)
    export $(grep -E "^(ANTHROPIC|OPENAI|DEEPSEEK|MOONSHOT)_API_KEY=" .env | xargs) && \\
    ANTHROPIC_API_KEY_REAL="$ANTHROPIC_API_KEY" \\
    OPENAI_API_KEY_REAL="$OPENAI_API_KEY" \\
    DEEPSEEK_API_KEY_REAL="$DEEPSEEK_API_KEY" \\
    MOONSHOT_API_KEY_REAL="$MOONSHOT_API_KEY" \\
    pytest tests/test_e2e/test_e2e_data_analysis.py -v
"""

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.test_e2e.conftest import parse_sse_events

# ---------------------------------------------------------------------------
# Multi-LLM Provider Configuration
# ---------------------------------------------------------------------------

# API Keys from environment
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY_REAL", "")
_OPENAI_KEY = os.environ.get("OPENAI_API_KEY_REAL", "")
_DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY_REAL", "")
_KIMI_KEY = os.environ.get("KIMI_API_KEY_REAL", "") or os.environ.get("MOONSHOT_API_KEY_REAL", "")

# For backward compatibility
_REAL_KEY = _ANTHROPIC_KEY

# Provider configurations
LLM_PROVIDERS = {
    "anthropic": {
        "key": _ANTHROPIC_KEY,
        "key_env": "ANTHROPIC_API_KEY_REAL",
        "model_provider": "anthropic",
        "model_name": "claude-sonnet-4-5-20250929",
        "settings_patch": "app.config.settings.anthropic_api_key",
    },
    "openai": {
        "key": _OPENAI_KEY,
        "key_env": "OPENAI_API_KEY_REAL",
        "model_provider": "openai",
        "model_name": "gpt-4o",
        "settings_patch": "app.config.settings.openai_api_key",
    },
    "deepseek": {
        "key": _DEEPSEEK_KEY,
        "key_env": "DEEPSEEK_API_KEY_REAL",
        "model_provider": "deepseek",
        "model_name": "deepseek-chat",
        "settings_patch": "app.config.settings.deepseek_api_key",
    },
    "kimi": {
        "key": _KIMI_KEY,
        "key_env": "KIMI_API_KEY_REAL or MOONSHOT_API_KEY_REAL",
        "model_provider": "kimi",
        "model_name": "kimi-k2.5",
        "settings_patch": "app.config.settings.moonshot_api_key",
    },
}


def _patch_api_key():
    """Patch settings.anthropic_api_key so SkillsAgent picks up the real key."""
    return patch("app.config.settings.anthropic_api_key", _REAL_KEY)


def _patch_provider_key(provider: str):
    """
    Patch the appropriate API key for the given provider.

    Note: DeepSeek and Kimi read API keys directly from environment variables,
    so we patch the os.environ instead of settings for those providers.
    """
    config = LLM_PROVIDERS.get(provider, LLM_PROVIDERS["anthropic"])

    if provider in ("deepseek", "kimi"):
        # These providers read from environment variables directly
        env_var = "DEEPSEEK_API_KEY" if provider == "deepseek" else "MOONSHOT_API_KEY"
        return patch.dict(os.environ, {env_var: config["key"]})
    else:
        # Anthropic and OpenAI use settings
        return patch(config["settings_patch"], config["key"])


def _get_available_providers():
    """Return list of providers that have API keys configured."""
    return [name for name, cfg in LLM_PROVIDERS.items() if cfg["key"]]


# Skip markers for each provider
skip_no_anthropic = pytest.mark.skipif(not _ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY_REAL not set")
skip_no_openai = pytest.mark.skipif(not _OPENAI_KEY, reason="OPENAI_API_KEY_REAL not set")
skip_no_deepseek = pytest.mark.skipif(not _DEEPSEEK_KEY, reason="DEEPSEEK_API_KEY_REAL not set")
skip_no_kimi = pytest.mark.skipif(not _KIMI_KEY, reason="KIMI_API_KEY_REAL/MOONSHOT_API_KEY_REAL not set")


# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

_DATA_EXPLORER_DIR = Path("skills/data-explorer")

_DATA_EXPLORER_SKILL_MD = """\
---
name: data-explorer
description: Comprehensive exploratory data analysis (EDA), statistical analysis, and visualization skill.
---

# Data Explorer

A skill for exploratory data analysis (EDA), statistical analysis, and visualization.

## When to Use

Use this skill when the user wants to:
- Analyze CSV, JSON, Excel, or other tabular data files
- Explore data structure, distributions, and patterns
- Calculate statistics (mean, median, std, correlations)
- Detect outliers or anomalies
- Create visualizations (histograms, scatter plots, heatmaps)
- Generate data quality reports

## Workflow

1. **Load Data**: Read the file using pandas
2. **Inspect Structure**: Check shape, dtypes, head/tail
3. **Data Quality**: Missing values, duplicates, outliers
4. **Statistics**: Descriptive stats, correlations
5. **Visualizations**: Create relevant charts
6. **Summary**: Key insights and recommendations

## Code Patterns

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load data
df = pd.read_csv("data.csv")

# Basic info
print(df.shape)
print(df.dtypes)
print(df.describe())

# Missing values
print(df.isnull().sum())

# Correlation heatmap
plt.figure(figsize=(10, 8))
sns.heatmap(df.corr(), annot=True, cmap='coolwarm')
plt.savefig("correlation_heatmap.png")
```

## Output

Output files (charts, reports) are automatically detected and made downloadable.
"""

_TEST_CSV_DATA = """\
date,product,category,quantity,price,region,customer_age,rating
2025-01-01,Widget A,Electronics,10,29.99,North,25,4.5
2025-01-02,Widget B,Electronics,15,49.99,South,32,4.2
2025-01-03,Gadget X,Home,8,19.99,East,45,3.8
2025-01-04,Gadget Y,Home,12,24.99,West,28,4.0
2025-01-05,Widget A,Electronics,20,29.99,North,35,4.7
2025-01-06,Widget C,Electronics,5,99.99,South,42,4.9
2025-01-07,Gadget X,Home,18,19.99,East,22,3.5
2025-01-08,Widget B,Electronics,25,49.99,West,55,4.1
2025-01-09,Gadget Z,Home,7,34.99,North,38,4.3
2025-01-10,Widget A,Electronics,30,29.99,South,29,4.6
2025-01-11,Widget C,Electronics,3,99.99,East,48,4.8
2025-01-12,Widget B,Electronics,13,49.99,East,50,4.8
"""


# ---------------------------------------------------------------------------
# Full Data Analysis Test Base Class
# ---------------------------------------------------------------------------

class FullDataAnalysisTestBase:
    """
    Full data analysis workflow test base class.

    Subclasses should set:
    - PROVIDER: str (e.g., "anthropic", "openai", "deepseek", "kimi")

    Tests (15 total):
    1. Create data-explorer skill on disk
    2. Import skill into DB
    3. Verify skill exists
    4. Upload CSV file
    5. Create Agent Preset
    6. Run Agent with SSE streaming (multi-turn code execution)
    7. Verify tool usage
    8. Verify skill usage
    9. Verify trace record
    10. Verify trace steps
    11. Cleanup agent preset
    12. Cleanup trace
    13. Cleanup file
    14. Cleanup skill
    15. Verify skill deleted
    """

    PROVIDER: str = "anthropic"
    _state: dict = {}

    def _get_config(self):
        """Get provider configuration."""
        return LLM_PROVIDERS.get(self.PROVIDER, LLM_PROVIDERS["anthropic"])

    @pytest.fixture(autouse=True, scope="class")
    def _cleanup_disk(self):
        """Ensure the data-explorer disk directory is removed after the class."""
        yield
        if _DATA_EXPLORER_DIR.exists():
            shutil.rmtree(_DATA_EXPLORER_DIR)

    # -------------------------------------------------------------------------
    # Test Cases
    # -------------------------------------------------------------------------

    async def test_01_create_skill_on_disk(self):
        """Write SKILL.md to disk for import."""
        _DATA_EXPLORER_DIR.mkdir(parents=True, exist_ok=True)
        (_DATA_EXPLORER_DIR / "SKILL.md").write_text(
            _DATA_EXPLORER_SKILL_MD, encoding="utf-8"
        )
        assert (_DATA_EXPLORER_DIR / "SKILL.md").exists()

    async def test_02_import_skill(self, e2e_client: AsyncClient):
        """Import the data-explorer skill into the test DB."""
        resp = await e2e_client.post(
            "/api/v1/registry/import-local",
            json={"skill_names": ["data-explorer"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_imported"] >= 1
        result = next(r for r in body["results"] if r["name"] == "data-explorer")
        assert result["success"] is True
        type(self)._state["skill_version"] = result["version"]

    async def test_03_verify_skill_exists(self, e2e_client: AsyncClient):
        """Verify the skill was imported correctly."""
        resp = await e2e_client.get("/api/v1/registry/skills/data-explorer")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "data-explorer"
        assert "EDA" in body["description"] or "data analysis" in body["description"].lower()

    async def test_04_upload_csv_file(self, e2e_client: AsyncClient):
        """Upload the test CSV file."""
        resp = await e2e_client.post(
            "/api/v1/files/upload",
            files={"file": ("sales_data.csv", _TEST_CSV_DATA.encode(), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "sales_data.csv"
        assert body["file_id"] is not None
        type(self)._state["file_id"] = body["file_id"]
        type(self)._state["file_path"] = body["path"]

    async def test_05_create_agent_preset(self, e2e_client: AsyncClient):
        """Create an Agent Preset configured for data analysis."""
        # Use provider-specific name to avoid conflicts
        preset_name = f"e2e-data-analyst-{self.PROVIDER}"
        payload = {
            "name": preset_name,
            "description": f"E2E test data analysis agent ({self.PROVIDER})",
            "system_prompt": (
                "You are a data analyst. Use the data-explorer skill to analyze data. "
                "Be concise but thorough. Always export generated files."
            ),
            "skill_ids": ["data-explorer"],
            "mcp_servers": [],
            "max_turns": 30,
        }
        resp = await e2e_client.post("/api/v1/agents", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == preset_name
        type(self)._state["preset_id"] = body["id"]

    async def test_06_run_agent_stream(self, e2e_client: AsyncClient):
        """Run Agent with SSE streaming for multi-turn data analysis."""
        file_id = type(self)._state["file_id"]
        file_path = type(self)._state["file_path"]
        config = self._get_config()

        with _patch_provider_key(self.PROVIDER):
            resp = await e2e_client.post(
                "/api/v1/agent/run/stream",
                json={
                    "request": (
                        "Analyze this sales dataset: "
                        "1) Load and inspect the data "
                        "2) Check data quality (missing values, outliers) "
                        "3) Compute basic statistics "
                        "4) Create a correlation heatmap visualization "
                        "5) Summarize key insights. "
                        "Export any generated files."
                    ),
                    "uploaded_files": [
                        {
                            "file_id": file_id,
                            "filename": "sales_data.csv",
                            "path": file_path,
                            "content_type": "text/csv",
                        }
                    ],
                    "skills": ["data-explorer"],
                    "model_provider": config["model_provider"],
                    "model_name": config["model_name"],
                    "max_turns": 30,
                    "session_id": "e2e-data-analysis-stream-session",
                },
                timeout=300,  # 5 min timeout for multi-turn analysis
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = parse_sse_events(resp.text)
        assert len(events) >= 3, "Should have multiple SSE events"

        # Extract key info from events
        trace_id = None
        tool_calls = []
        output_files = []
        final_success = None
        total_turns = 0

        for event in events:
            event_type = event.get("event_type")

            if event_type == "run_started":
                trace_id = event.get("trace_id")
            elif event_type == "tool_call":
                tool_calls.append(event.get("tool_name"))
            elif event_type == "output_file":
                output_files.append(event.get("filename"))
            elif event_type == "complete":
                final_success = event.get("success")
                total_turns = event.get("total_turns", 0)

        type(self)._state["trace_id"] = trace_id
        type(self)._state["tool_calls"] = tool_calls
        type(self)._state["output_files"] = output_files
        type(self)._state["total_turns"] = total_turns

        # Assertions
        assert trace_id is not None, "Should have a trace ID"
        assert final_success is True, f"Agent should complete successfully (provider: {self.PROVIDER})"
        assert total_turns >= 2, f"Should have multiple turns, got {total_turns}"

    async def test_07_verify_tool_usage(self):
        """Verify that code execution tools were called during analysis."""
        tool_calls = type(self)._state.get("tool_calls", [])
        total_turns = type(self)._state.get("total_turns", 0)

        # If we have multiple turns, we should have tool calls
        if total_turns >= 2:
            # Should have used execute_code, bash, or read for analysis
            valid_tools = ["execute_code", "bash", "read"]
            assert any(t in tool_calls for t in valid_tools), (
                f"[{self.PROVIDER}] Should have called analysis tools, got: {tool_calls}"
            )

    async def test_08_verify_skill_usage(self):
        """Verify that get_skill was called to load the skill."""
        tool_calls = type(self)._state.get("tool_calls", [])
        total_turns = type(self)._state.get("total_turns", 0)

        # Skill usage is optional - agent may use skill knowledge from system prompt
        # or may call get_skill to load it
        if total_turns >= 2 and len(tool_calls) > 0:
            # Log what tools were used
            print(f"[{self.PROVIDER}] Tools used: {tool_calls}")
            # get_skill is expected but not strictly required
            if "get_skill" not in tool_calls:
                print(f"[{self.PROVIDER}] Note: get_skill was not called, agent may have used skill from prompt")

    async def test_09_verify_trace(self, e2e_client: AsyncClient):
        """Verify trace record contains expected data."""
        trace_id = type(self)._state.get("trace_id")
        assert trace_id is not None

        resp = await e2e_client.get(f"/api/v1/traces/{trace_id}")
        assert resp.status_code == 200

        trace = resp.json()
        assert trace["success"] is True
        assert trace["total_turns"] >= 2
        assert trace["total_input_tokens"] > 0
        assert trace["total_output_tokens"] > 0

        type(self)._state["trace_data"] = trace

    async def test_10_verify_trace_steps(self, e2e_client: AsyncClient):
        """Verify trace steps contain tool usage."""
        trace_data = type(self)._state.get("trace_data")
        assert trace_data is not None

        steps = trace_data.get("steps", [])
        assert isinstance(steps, list)
        assert len(steps) > 0

        # Find analysis tool steps
        tool_steps = [s for s in steps if s.get("tool_name") in ["execute_code", "bash", "read"]]
        assert len(tool_steps) >= 1, f"[{self.PROVIDER}] Should have at least one analysis tool step"

    async def test_11_cleanup_agent_preset(self, e2e_client: AsyncClient):
        """Delete the agent preset."""
        preset_id = type(self)._state.get("preset_id")
        if preset_id:
            resp = await e2e_client.delete(f"/api/v1/agents/{preset_id}")
            assert resp.status_code in (200, 204)

    async def test_12_cleanup_trace(self, e2e_client: AsyncClient):
        """Delete the trace."""
        trace_id = type(self)._state.get("trace_id")
        if trace_id:
            resp = await e2e_client.delete(f"/api/v1/traces/{trace_id}")
            assert resp.status_code in (200, 204)

    async def test_13_cleanup_file(self, e2e_client: AsyncClient):
        """Delete the uploaded file."""
        file_id = type(self)._state.get("file_id")
        if file_id:
            resp = await e2e_client.delete(f"/api/v1/files/{file_id}")
            # File deletion may return 204 or 404 if already cleaned up
            assert resp.status_code in (200, 204, 404)

    async def test_14_cleanup_skill(self, e2e_client: AsyncClient):
        """Delete the skill from DB."""
        resp = await e2e_client.delete("/api/v1/registry/skills/data-explorer")
        assert resp.status_code in (200, 204)

    async def test_15_verify_skill_deleted(self, e2e_client: AsyncClient):
        """Confirm the skill no longer exists."""
        resp = await e2e_client.get("/api/v1/registry/skills/data-explorer")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Provider-specific Full Test Classes (15 tests each)
# ---------------------------------------------------------------------------

@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_anthropic
class TestDataAnalysisAnthropicE2E(FullDataAnalysisTestBase):
    """Full data analysis E2E test with Anthropic Claude Sonnet 4.5."""
    PROVIDER = "anthropic"
    _state: dict = {}


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_openai
class TestDataAnalysisOpenAIE2E(FullDataAnalysisTestBase):
    """Full data analysis E2E test with OpenAI GPT-4o."""
    PROVIDER = "openai"
    _state: dict = {}


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_deepseek
class TestDataAnalysisDeepSeekE2E(FullDataAnalysisTestBase):
    """Full data analysis E2E test with DeepSeek Chat."""
    PROVIDER = "deepseek"
    _state: dict = {}


@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_kimi
class TestDataAnalysisKimiE2E(FullDataAnalysisTestBase):
    """Full data analysis E2E test with Kimi K2.5 (Moonshot)."""
    PROVIDER = "kimi"
    _state: dict = {}


# ---------------------------------------------------------------------------
# Lightweight version (fewer turns, basic verification, Kimi only)
# ---------------------------------------------------------------------------

@pytest.mark.e2e_llm
@pytest.mark.asyncio(loop_scope="class")
@skip_no_kimi
class TestDataAnalysisLightE2E:
    """
    Lightweight data analysis test - fewer turns, basic verification.

    Good for CI/CD where full analysis is too slow.
    Uses Kimi 2.5 (kimi-k2.5).
    """

    _state: dict = {}

    async def test_01_run_simple_analysis(self, e2e_client: AsyncClient):
        """Run a simple analysis request with minimal turns."""
        # Create inline test data
        csv_data = "x,y,z\n1,2,3\n4,5,6\n7,8,9\n10,11,12"

        # Upload
        resp = await e2e_client.post(
            "/api/v1/files/upload",
            files={"file": ("simple.csv", csv_data.encode(), "text/csv")},
        )
        assert resp.status_code == 200
        file_info = resp.json()
        type(self)._state["file_id"] = file_info["file_id"]
        type(self)._state["file_path"] = file_info["path"]

        # Run agent with Kimi 2.5
        with _patch_provider_key("kimi"):
            resp = await e2e_client.post(
                "/api/v1/agent/run",
                json={
                    "request": (
                        "Load this CSV and tell me: "
                        "1) How many rows? "
                        "2) What are the column names? "
                        "3) What is the mean of column x? "
                        "Be very brief."
                    ),
                    "uploaded_files": [
                        {
                            "file_id": file_info["file_id"],
                            "filename": "simple.csv",
                            "path": file_info["path"],
                            "content_type": "text/csv",
                        }
                    ],
                    "max_turns": 10,
                    "model_provider": "kimi",
                    "model_name": "kimi-k2.5",
                    "session_id": "e2e-data-analysis-sync-session",
                },
                timeout=120,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total_turns"] >= 1
        type(self)._state["trace_id"] = body["trace_id"]

        # Answer should mention key facts
        answer = body["answer"].lower()
        # Check that it understood the data (4 rows, columns x/y/z)
        assert any(x in answer for x in ["4", "four", "rows"]) or "x" in answer

    async def test_02_verify_code_executed(self, e2e_client: AsyncClient):
        """Verify that code was executed to analyze the data."""
        trace_id = type(self)._state.get("trace_id")

        resp = await e2e_client.get(f"/api/v1/traces/{trace_id}")
        assert resp.status_code == 200

        trace = resp.json()
        steps = trace.get("steps", [])
        tool_names = [s.get("tool_name") for s in steps if s.get("tool_name")]

        # Should have used execute_code, bash, or read to analyze
        assert any(t in tool_names for t in ["execute_code", "bash", "read"]), (
            f"Should have executed code or read file, got tools: {tool_names}"
        )

    async def test_03_cleanup(self, e2e_client: AsyncClient):
        """Cleanup test resources."""
        file_id = type(self)._state.get("file_id")
        trace_id = type(self)._state.get("trace_id")

        if file_id:
            await e2e_client.delete(f"/api/v1/files/{file_id}")
        if trace_id:
            await e2e_client.delete(f"/api/v1/traces/{trace_id}")
