---
sidebar_position: 9
---

# Run Tests

Skill Compose includes a comprehensive test suite covering unit tests, end-to-end workflows, and real LLM integration tests.

## Quick Start

Run all tests with a single command:

```bash
./scripts/run-tests.sh
```

This runs unit tests, E2E mock tests, and real LLM tests **serially** to avoid database conflicts.

:::caution Run tests serially
Do not run multiple test suites in parallel — they share the same test database (`skills_api_test`) and concurrent `DROP TABLE` / `CREATE TABLE` operations will cause deadlocks.
:::

## Prerequisites

- **PostgreSQL** running on port 62620 (Docker or local)
- **Python dependencies** installed (`pip install -r requirements.txt`)
- **Moonshot API key** in `.env` (for LLM tests only)

## Test Categories

### Unit Tests (~390 tests, ~55s)

Test individual API endpoints and services using a per-test isolated database. No API keys required.

```bash
./scripts/run-tests.sh unit
```

Or run directly:

```bash
pytest tests/test_api/ tests/test_core/ tests/test_services/ -v
```

### E2E Workflow Tests (~170 tests, ~15s)

End-to-end API workflows using mocked LLM responses. Covers skills lifecycle, agents, traces, file upload, code execution, MCP, and more.

```bash
./scripts/run-tests.sh e2e
```

### Real LLM Tests (~62 tests, ~6 min)

Tests that make real API calls to Kimi 2.5. Requires `MOONSHOT_API_KEY` in your `.env` file.

```bash
./scripts/run-tests.sh llm
```

This runs three test suites:

| Suite | Tests | Coverage |
|-------|-------|----------|
| Real Agent | 26 | Agent chat, streaming, evolve, import lifecycle |
| Published Agent | 21 | Publish, streaming/non-streaming modes, multi-turn, MCP tools |
| Data Analysis | 15 | Skill creation, file upload, agent execution, trace verification |

## Understanding Results

The script prints a color-coded summary at the end:

```
============================================
 Summary
============================================
  PASS  Unit Tests  (48s)
  PASS  E2E Workflow (mock)  (15s)
  PASS  E2E Real Agent (Kimi 2.5)  (262s)
  PASS  E2E Published Agent (Kimi 2.5)  (47s)
  PASS  E2E Data Analysis (Kimi 2.5)  (181s)

  Total: 5 passed, 0 failed, 0 skipped
```

- **PASS** — All tests in the suite passed
- **FAIL** — One or more tests failed (exit code shown)
- **SKIP** — Suite was skipped (e.g., missing API key)

## Running Individual Tests

You can also run specific test files or classes directly:

```bash
# Single test file
pytest tests/test_api/test_agents_api.py -v

# Single test class
pytest tests/test_e2e/test_e2e_workflows.py::TestSkillFullLifecycleE2E -v

# Single test
pytest tests/test_api/test_health.py::test_health_endpoint -v

# Filter by marker
pytest -m e2e -v          # E2E workflow only
pytest -m "not e2e" -v    # Exclude E2E
```

## Environment Setup for LLM Tests

LLM tests read API keys from environment variables with the `_REAL` suffix:

```bash
# The run-tests.sh script handles this automatically.
# For manual runs, set the key explicitly:
MOONSHOT_API_KEY_REAL="your-key" pytest tests/test_e2e/test_e2e_agent_real.py -v
```

The script extracts keys from `.env` automatically, handling quoted values.

## Troubleshooting

### Database connection refused

```
psycopg2.OperationalError: connection to server at "localhost", port 62620 failed
```

Ensure PostgreSQL is running:

```bash
docker start skills-db    # Docker
# or
sudo systemctl start postgresql  # Local
```

### Tests hang or deadlock

This happens when multiple pytest processes run concurrently. Kill all pytest processes and retry:

```bash
pkill -f pytest
./scripts/run-tests.sh
```

### LLM tests skipped

If LLM tests show as skipped, verify your `.env` has `MOONSHOT_API_KEY` set:

```bash
grep MOONSHOT_API_KEY .env
```

## Related

- [Development Setup](/development-setup) — Setting up the development environment
- [Configuration](/reference/configuration) — Environment variables reference
