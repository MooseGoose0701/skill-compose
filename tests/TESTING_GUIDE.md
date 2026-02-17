# Skills API - Testing Guide

Developer-oriented testing operations guide, including environment setup, running commands, writing conventions, and troubleshooting.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Running Tests](#2-running-tests)
3. [Writing New Tests](#3-writing-new-tests)
4. [Mock Usage Guide](#4-mock-usage-guide)
5. [Fixtures Reference](#5-fixtures-reference)
6. [E2E Testing](#6-e2e-testing)
7. [CI/CD Integration](#7-cicd-integration)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Environment Setup

### 1.1 Prerequisites

- Python 3.10+
- Docker (for PostgreSQL + pgvector)
- Node.js 18+ (only needed for E2E tests)

### 1.2 Install Test Dependencies

```bash
pip install -e ".[dev]"
```

This installs test dependencies like `pytest`, `pytest-asyncio`, `httpx`, etc.

### 1.3 Start Test Database

Tests use a separate PostgreSQL database `skills_api_test`.

**Method 1: Use Script (Recommended)**

```bash
bash tests/scripts/setup_test_db.sh
```

**Method 2: Manual Setup**

```bash
# Ensure skills-db container is running
cd docker && docker compose up -d db

# Create test database
docker exec skills-db psql -U skills -d postgres -c "CREATE DATABASE skills_api_test OWNER skills;"

# Enable pgvector extension
docker exec skills-db psql -U skills -d skills_api_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 1.4 Verify Environment

```bash
# Confirm database connection
docker exec skills-db psql -U skills -d skills_api_test -c "SELECT 1;"

# Confirm tests can be collected
python -m pytest tests/ --ignore=tests/e2e --co -q
# Expected output: 202 tests collected
```

---

## 2. Running Tests

### 2.1 Common Commands

```bash
# All backend tests
python -m pytest tests/ --ignore=tests/e2e -v

# With colored concise output
python -m pytest tests/ --ignore=tests/e2e --tb=short

# Single file
python -m pytest tests/test_api/test_agents_api.py -v

# Single test class
python -m pytest tests/test_api/test_agents_api.py::TestCreatePreset -v

# Single test method
python -m pytest tests/test_api/test_agents_api.py::TestCreatePreset::test_create_preset -v

# Match by name
python -m pytest tests/ --ignore=tests/e2e -k "agent" -v

# With coverage
python -m pytest tests/ --ignore=tests/e2e --cov=app --cov-report=html --cov-report=term-missing -v
# Report output to htmlcov/index.html
```

### 2.2 Run by Module

```bash
# API integration tests (140 tests)
python -m pytest tests/test_api/ -v

# Core module tests (30 tests)
python -m pytest tests/test_core/ -v

# Service layer tests (32 tests)
python -m pytest tests/test_services/ -v
```

### 2.3 Run All at Once

```bash
bash tests/scripts/run_all_tests.sh

# With coverage
bash tests/scripts/run_all_tests.sh --coverage
```

This script runs sequentially:
1. Backend pytest tests
2. Coverage report (when `--coverage` is used)
3. Playwright E2E tests (if frontend service is running)

### 2.4 Output Interpretation

```
tests/test_api/test_agents_api.py::TestCreatePreset::test_create_preset PASSED [ 9%]
                                    ^                ^                  ^       ^
                                    Test class       Test method        Status  Progress
```

| Status | Meaning |
|--------|---------|
| PASSED | Test passed |
| FAILED | Assertion failed |
| ERROR | Fixture/setup exception |
| SKIPPED | Skipped |

---

## 3. Writing New Tests

### 3.1 API Endpoint Tests

Create files under `tests/test_api/`, named `test_<module>.py`.

**Template**:

```python
"""
Tests for <Module> API.

Endpoints tested:
- GET    /api/v1/<path>
- POST   /api/v1/<path>
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SomeModel

API = "/api/v1/<path>"


class TestListItems:
    """Tests for GET /api/v1/<path>."""

    async def test_list_empty(self, client: AsyncClient):
        response = await client.get(API)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    async def test_list_with_data(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        # Prepare data
        item = SomeModel(id="test-1", name="test")
        db_session.add(item)
        await db_session.commit()

        # Request
        response = await client.get(API)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1


class TestCreateItem:
    """Tests for POST /api/v1/<path>."""

    async def test_create_success(self, client: AsyncClient):
        response = await client.post(API, json={"name": "new-item"})
        assert response.status_code in (200, 201)

    async def test_create_invalid(self, client: AsyncClient):
        response = await client.post(API, json={})
        assert response.status_code == 422  # Validation error
```

**Key Points**:
- Use `client` fixture to send HTTP requests
- Use `db_session` fixture to directly manipulate the database
- Each test is independent (each test has its own empty database)
- No need for `@pytest.mark.asyncio` (`asyncio_mode = "auto"` handles this automatically)

### 3.2 Service Layer Tests

Create files under `tests/test_services/`.

```python
"""Tests for SomeService."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SomeModel
from tests.factories import make_some_model


class TestSomeService:
    async def test_do_something(self, db_session: AsyncSession):
        # Prepare
        item = make_some_model(name="test")
        db_session.add(item)
        await db_session.flush()

        # Execute
        from app.services.some_service import SomeService
        service = SomeService(db_session)
        result = await service.do_something(item.id)

        # Verify
        assert result is not None
```

### 3.3 Core Module Tests

Pure logic tests that don't depend on the database go in `tests/test_core/`.

```python
"""Tests for some_module."""
from app.core.some_module import some_function


def test_some_function():
    """Synchronous test, no async needed."""
    result = some_function("input")
    assert result == "expected"
```

### 3.4 Adding Data Factories

When you need new test data models, add factory functions in `tests/factories.py`:

```python
def make_new_model(
    name: str = "default-name",
    **kwargs,
) -> NewModel:
    return NewModel(
        id=kwargs.get("id", str(uuid.uuid4())),
        name=name,
        created_at=kwargs.get("created_at", datetime.utcnow()),
    )
```

### 3.5 Adding Shared Fixtures

If multiple test files need the same preset data, add fixtures in `tests/test_api/conftest.py`:

```python
@pytest_asyncio.fixture
async def sample_new_model(db_session: AsyncSession):
    item = make_new_model(name="test-item")
    db_session.add(item)
    await db_session.flush()
    return item
```

---

## 4. Mock Usage Guide

### 4.1 Mock Agent (LLM Calls)

`/agent/run` endpoint tests need to mock `SkillsAgent`:

```python
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

@dataclass
class MockAgentResult:
    success: bool = True
    answer: str = "Mock answer"
    total_turns: int = 1
    total_input_tokens: int = 100
    total_output_tokens: int = 50
    steps: list = None
    llm_calls: list = None
    error: str = None
    output_files: list = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = []
        if self.llm_calls is None:
            self.llm_calls = []
        if self.output_files is None:
            self.output_files = []


@patch("app.api.v1.agent.SkillsAgent")
async def test_something(MockAgent, client):
    mock_instance = MagicMock()
    mock_instance.run.return_value = MockAgentResult(answer="Test result")
    mock_instance.model = "claude-sonnet-4-5-20250929"
    MockAgent.return_value = mock_instance

    response = await client.post("/api/v1/agent/run", json={"request": "hello", "session_id": "test-session-id"})
    assert response.status_code == 200
```

### 4.2 Mock File System Operations

Skills file system endpoints need to mock `find_all_skills` / `read_skill`:

```python
from unittest.mock import patch

@patch("app.api.v1.skills.find_all_skills")
async def test_list_skills(mock_find, client):
    mock_find.return_value = [
        SimpleNamespace(name="test-skill", description="A test", path="/skills/test-skill")
    ]
    response = await client.get("/api/v1/skills")
    assert response.status_code == 200
```

### 4.3 Mock MCP Configuration

MCP endpoints need to mock config file reading:

```python
@patch("app.api.v1.mcp._load_config")
async def test_list_mcp(mock_config, client):
    mock_config.return_value = {
        "mcpServers": {
            "fetch": {"name": "Fetch", "description": "Fetch URLs", "command": "node"}
        }
    }
    response = await client.get("/api/v1/mcp/servers")
```

### 4.4 Mock Code Execution

Tool execution endpoints need to mock `CodeExecutor`:

```python
@patch("app.api.v1.tools.CodeExecutor")
async def test_execute_code(MockExecutor, client):
    mock_instance = MagicMock()
    mock_result = MagicMock()
    mock_result.output = "Hello World"
    mock_result.logs = {"stdout": ["Hello World"]}
    mock_instance.execute.return_value = mock_result
    MockExecutor.return_value = mock_instance

    response = await client.post(
        "/api/v1/tools/execute/simple",
        json={"code": "print('Hello World')"}
    )
```

---

## 5. Fixtures Reference

### 5.1 Root Level Fixtures (`tests/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `db_session` | function | Provides AsyncSession, auto create/drop tables per test |
| `app` | function | Creates test FastAPI instance, overrides `get_db` |
| `client` | function | httpx AsyncClient, bound to test app |

**Dependency chain**: `client` → `app` → `db_session`

### 5.2 API Fixtures (`tests/test_api/conftest.py`)

| Fixture | Return Type | Description |
|---------|-------------|-------------|
| `sample_skill` | `SkillDB` | Pre-created skill (name="test-skill") |
| `sample_skill_version` | `SkillVersionDB` | Depends on `sample_skill` |
| `sample_skill_file` | `SkillFileDB` | Depends on `sample_skill_version` |
| `sample_preset` | `AgentPresetDB` | User preset |
| `system_preset` | `AgentPresetDB` | System preset (is_system=True) |
| `sample_trace` | `AgentTraceDB` | Execution trace (with steps/llm_calls) |
| `sample_changelog` | `SkillChangelogDB` | Changelog entry |
| `sample_background_task` | `BackgroundTaskDB` | Background task |

### 5.3 Usage Examples

```python
class TestSomething:
    async def test_with_preset(self, client, sample_preset):
        """sample_preset is already in the database, can request directly."""
        response = await client.get(f"/api/v1/agents/{sample_preset.id}")
        assert response.status_code == 200

    async def test_with_raw_db(self, client, db_session):
        """Can also directly manipulate db_session to create custom data."""
        from app.db.models import AgentPresetDB
        preset = AgentPresetDB(id="custom-1", name="custom", max_turns=10)
        db_session.add(preset)
        await db_session.commit()
        # ...
```

---

## 6. E2E Testing

### 6.1 Installation

```bash
cd tests/e2e
npm install
npx playwright install chromium
```

### 6.2 Prerequisites

E2E tests require frontend and backend services running:

```bash
# Terminal 1: Start backend
uvicorn app.main:app --host 127.0.0.1 --port 62610 --reload

# Terminal 2: Start frontend
cd web && npm run dev

# Terminal 3: Run E2E tests
cd tests/e2e && npx playwright test
```

### 6.3 Common Commands

```bash
# All E2E tests
npx playwright test

# With browser UI (for debugging)
npx playwright test --headed

# Single file
npx playwright test pages/home.spec.ts

# Generate report
npx playwright test --reporter=html
npx playwright show-report
```

### 6.4 E2E Test Coverage

| Page | Test File | Verification |
|------|-----------|--------------|
| `/` | home.spec.ts | Page load, navigation links |
| `/skills` | skills-list.spec.ts | List rendering, search, system skills on top |
| `/skills/[name]` | skills-detail.spec.ts | Detail page, versions, export |
| `/agents` | agents-list.spec.ts | Preset list, delete |
| `/agents/new` | agents-new.spec.ts | Form, Skills/Tools/MCP selection |
| `/tools` | tools.spec.ts | Tool categorization display |
| `/mcp` | mcp.spec.ts | Server list |
| `/traces` | traces.spec.ts | List, filter, detail navigation |
| Chat Panel | chat-panel.spec.ts | Open, send message, close |

---

## 7. CI/CD Integration

### 7.1 GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: skills
          POSTGRES_PASSWORD: skills123
          POSTGRES_DB: skills_api_test
        ports:
          - 62620:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install pytest-cov

      - name: Enable pgvector
        run: |
          PGPASSWORD=skills123 psql -h localhost -U skills -d skills_api_test \
            -c "CREATE EXTENSION IF NOT EXISTS vector;"

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test
          ANTHROPIC_API_KEY: test-key-not-real
        run: |
          python -m pytest tests/ --ignore=tests/e2e \
            --cov=app --cov-report=xml --cov-report=term-missing \
            -v --tb=short

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

### 7.2 Environment Variables

| Variable | Test Value | Description |
|----------|------------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test` | Auto-set by conftest.py |
| `ANTHROPIC_API_KEY` | `test-key-not-real` | Auto-set by conftest.py, all LLM calls are mocked |

When running locally, `conftest.py` automatically sets these environment variables before import, no manual configuration needed.

---

## 8. Troubleshooting

### 8.1 Database Connection Failed

```
sqlalchemy.exc.OperationalError: connection refused
```

**Cause**: PostgreSQL container is not running.

**Solution**:
```bash
cd docker && docker compose up -d db
# Wait for health check to pass
docker exec skills-db pg_isready -U skills
```

### 8.2 Test Database Does Not Exist

```
asyncpg.InvalidCatalogNameError: database "skills_api_test" does not exist
```

**Solution**:
```bash
bash tests/scripts/setup_test_db.sh
```

### 8.3 pgvector Extension Issue

```
sqlalchemy.exc.ProgrammingError: extension "vector" is not available
```

**Cause**: Docker image doesn't include pgvector.

**Solution**: Ensure you're using `pgvector/pgvector:pg16` image instead of plain `postgres` image.

### 8.4 Event Loop Conflict

```
RuntimeError: Task attached to a different loop
```
or
```
InterfaceError: connection was closed in the middle of operation
```

**Cause**: SQLAlchemy engine created in one event loop, used in another.

**Solution**: Ensure the engine in `db_session` fixture is created within the fixture (not using module-level engine), and call `engine.dispose()` in finally block.

### 8.5 Streaming Test InterfaceError

```
InterfaceError: cannot perform operation: another operation is in progress
```

**Cause**: `/agent/run/stream` endpoint uses `AsyncSessionLocal` instead of `get_db`.

**Solution**: Streaming tests need additional `AsyncSessionLocal` patch:
```python
@patch("app.api.v1.agent.AsyncSessionLocal")
@patch("app.api.v1.agent.SkillsAgent")
async def test_stream(MockAgent, MockSessionLocal, client, db_session):
    MockSessionLocal.side_effect = lambda: _mock_session_local(db_session)()
    # ...
```

### 8.6 Data Pollution Between Tests

**Symptom**: A test passes when run alone but fails when running all tests.

**Debugging**:
```bash
# Check test execution order
python -m pytest tests/test_api/ -v --tb=short 2>&1 | grep -E "PASSED|FAILED"

# Run in specific order
python -m pytest tests/test_api/test_a.py tests/test_api/test_b.py -v
```

**Cause**: Usually a test not properly cleaning up data (but this suite uses drop_all/create_all isolation, so this issue is rare).

### 8.7 pytest-asyncio Version Incompatibility

```
AttributeError: 'FixtureDef' object has no attribute 'unittest'
```

**Solution**:
```bash
pip install "pytest-asyncio>=0.24.0"
```

### 8.8 Zero Tests Collected

```
no tests ran
```

**Debugging**:
```bash
# Check pyproject.toml configuration
grep -A5 "pytest.ini_options" pyproject.toml

# Manually specify path
python -m pytest tests/test_api/test_health.py -v
```

---

## Appendix: Quick Reference Card

```bash
# === Environment Setup ===
cd docker && docker compose up -d db           # Start database
bash tests/scripts/setup_test_db.sh            # Create test database
pip install -e ".[dev]"                        # Install dependencies

# === Running Tests ===
python -m pytest tests/ --ignore=tests/e2e -v  # All backend tests
python -m pytest tests/test_api/ -v            # API tests only
python -m pytest tests/test_core/ -v           # Core modules only
python -m pytest tests/test_services/ -v       # Service layer only
python -m pytest -k "agent" -v                 # Match by name
python -m pytest --cov=app --cov-report=html   # With coverage
bash tests/scripts/run_all_tests.sh            # Run all at once

# === E2E Testing ===
cd tests/e2e && npm install                    # First-time install
npx playwright install chromium                # Install browser
npx playwright test                            # Run E2E
npx playwright test --headed                   # With UI for debugging

# === Debugging ===
python -m pytest tests/path/to/test.py -v -s   # Show print output
python -m pytest --co -q                        # List tests only (don't run)
python -m pytest --lf                           # Only run last failed
python -m pytest -x                             # Stop at first failure
```
