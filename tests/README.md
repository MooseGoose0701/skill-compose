# Skills API - Test Suite Documentation

## Overview

Skills API automated test suite covering all backend APIs and frontend E2E tests, runnable with a single command.

| Type | Framework | Test Count | Runtime |
|------|-----------|------------|---------|
| Backend Unit/Integration | pytest + pytest-asyncio + httpx | 202 | ~20s |
| Frontend E2E | Playwright | 39 | Requires frontend service running |
| **Total** | | **241** | |

---

## Directory Structure

```
tests/
├── conftest.py                         # Root fixtures: test DB, AsyncClient, dependency overrides
├── factories.py                        # Test data factory functions
├── mocks/
│   ├── __init__.py
│   ├── mock_anthropic.py               # Claude LLM Mock (MockTextBlock, MockResponse, etc.)
│   └── mock_code_executor.py           # Code executor Mock
├── test_api/                           # API integration tests (140 tests)
│   ├── conftest.py                     # API fixtures: sample_skill, sample_preset, etc.
│   ├── test_health.py                  # GET /, GET /health                      (4)
│   ├── test_agents_api.py              # Agent Presets CRUD                      (18)
│   ├── test_agent_run.py               # POST /agent/run + Mock LLM             (8)
│   ├── test_agent_stream.py            # POST /agent/run/stream SSE             (6)
│   ├── test_skills_api.py              # /skills/ file system endpoints          (6)
│   ├── test_registry_skills.py         # /registry/skills CRUD                  (14)
│   ├── test_registry_versions.py       # Version management                      (10)
│   ├── test_registry_evolve.py         # Evolution + async tasks                 (6)
│   ├── test_registry_import_export.py  # Import/export .skill                    (6)
│   ├── test_files_api.py              # File upload/download                     (10)
│   ├── test_traces_api.py             # Traces CRUD                             (10)
│   ├── test_mcp_api.py                # MCP server management                    (12)
│   └── test_tools_api.py              # Tool registry + code execution           (10)
├── test_core/                          # Core module tests (30 tests)
│   ├── test_skill_manager.py           # find_all_skills, read_skill, YAML parsing (16)
│   └── test_schema_validator.py        # Skill validator                          (14)
├── test_services/                      # Service layer tests (32 tests)
│   ├── test_skill_service.py           # SkillService business logic              (20)
│   └── test_task_manager.py            # TaskManager state machine                (12)
├── e2e/                                # Playwright E2E tests (39 tests)
│   ├── package.json
│   ├── playwright.config.ts
│   └── pages/
│       ├── home.spec.ts                # Home page                                (3)
│       ├── skills-list.spec.ts         # Skills list                              (5)
│       ├── skills-detail.spec.ts       # Skill detail                             (6)
│       ├── agents-list.spec.ts         # Preset list                              (4)
│       ├── agents-new.spec.ts          # Create preset                            (4)
│       ├── tools.spec.ts               # Tools page                               (3)
│       ├── mcp.spec.ts                 # MCP page                                 (4)
│       ├── traces.spec.ts              # Traces page                              (4)
│       └── chat-panel.spec.ts          # Chat panel                               (6)
└── scripts/
    ├── run_all_tests.sh                # Run all tests at once
    └── setup_test_db.sh                # Create test database
```

---

## Architecture Design

### Test Database

Uses a separate PostgreSQL test database `skills_api_test`, completely isolated from production `skills_api`.

```
Production: postgresql+asyncpg://skills:skills123@localhost:62620/skills_api
Test:       postgresql+asyncpg://skills:skills123@localhost:62620/skills_api_test
```

### Test Isolation Strategy

Each test case runs independently without interference:

```
Test starts

  → Base.metadata.create_all()     # Create tables
  → Run test
  → Base.metadata.drop_all()       # Drop tables
  → engine.dispose()               # Release connections
Test ends
```

Each test creates an independent SQLAlchemy AsyncEngine to avoid conflicts between pytest-asyncio's per-test event loop and shared engines.

### Lifespan Skip

Tests use `_create_test_app()` to build FastAPI instance, **not** `create_app()`:

- `create_app()`'s lifespan calls `init_db()`, executing PostgreSQL migrations and file system scans
- Test app uses no-op lifespan, table creation is managed by fixtures
- Routes, middleware, and exception handling are identical to production

### LLM Mock

All tests involving Claude API use `unittest.mock.patch` to replace `SkillsAgent`, zero API cost:

```python
@patch("app.api.v1.agent.SkillsAgent")
async def test_agent_run(MockAgent, client):
    mock_instance = MagicMock()
    mock_instance.run.return_value = MockAgentResult(...)
    MockAgent.return_value = mock_instance
    # ... test ...
```

### Dependency Injection Override

Uses FastAPI's `dependency_overrides` to replace `get_db` with test session:

```python
async def override_get_db():
    yield db_session

application.dependency_overrides[get_db] = override_get_db
```

**Note**: Streaming endpoint (`/agent/run/stream`) directly uses `AsyncSessionLocal` instead of `get_db`, so streaming tests additionally mock `AsyncSessionLocal`.

### Data Factories

`tests/factories.py` provides 7 factory functions generating pre-populated ORM objects:

| Function | Model | Purpose |
|----------|-------|---------|
| `make_skill()` | `SkillDB` | Skill record |
| `make_skill_version()` | `SkillVersionDB` | Version record (with SKILL.md content) |
| `make_skill_file()` | `SkillFileDB` | Version file attachment |
| `make_trace()` | `AgentTraceDB` | Execution trace (with steps, llm_calls) |
| `make_preset()` | `AgentPresetDB` | Agent preset configuration |
| `make_background_task()` | `BackgroundTaskDB` | Background task |
| `make_changelog()` | `SkillChangelogDB` | Changelog entry |

All factory functions support `**kwargs` to override defaults.

---

## Dependencies

### Backend Tests

```
pytest >= 7.4.0
pytest-asyncio >= 0.24.0
httpx >= 0.25.0
```

Declared in `pyproject.toml` under `[project.optional-dependencies] dev`.

### E2E Tests

```
@playwright/test (defined in package.json)
```

---

## pytest Configuration

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
markers = ["slow: slow tests"]
```

`asyncio_mode = "auto"` makes all `async def test_*` functions automatically treated as async tests, no need for manual `@pytest.mark.asyncio` (but already marked ones are unaffected).

---

## Coverage

### Backend API Coverage

| API Module | Endpoints | Test File | Coverage Scenarios |
|------------|-----------|-----------|-------------------|
| Health | `GET /`, `GET /health` | test_health.py | Normal return, 405 method |
| Agent Presets | `GET/POST/PUT/DELETE /agents` | test_agents_api.py | CRUD, system protection, filter, validation |
| Agent Run | `POST /agent/run` | test_agent_run.py | Single/multi turn, tool calls, trace saving |
| Agent Stream | `POST /agent/run/stream` | test_agent_stream.py | SSE event stream, error handling |
| Skills (File System) | `GET /skills` | test_skills_api.py | List, detail, resource files |
| Registry Skills | `GET/POST/PUT/DELETE /registry/skills` | test_registry_skills.py | CRUD, search, pagination, system protection |
| Registry Versions | `/registry/skills/{id}/versions` | test_registry_versions.py | Version create/list/rollback/diff |
| Registry Evolve | `/registry/skills/{id}/evolve` | test_registry_evolve.py | Async tasks, task polling |
| Import/Export | `/registry/skills/export/import` | test_registry_import_export.py | .skill export/import, conflict |
| Files | `GET/POST/DELETE /files` | test_files_api.py | Upload, download, output file registration |
| Traces | `GET/DELETE /traces` | test_traces_api.py | List pagination, filter, detail, delete |
| MCP | `GET/POST/PUT/DELETE /mcp` | test_mcp_api.py | Server management, key management |
| Tools | `GET /tools`, `POST /execute` | test_tools_api.py | Tool registry, code execution |

### Core Module Coverage

| Module | Test File | Coverage Scenarios |
|--------|-----------|-------------------|
| `skill_manager.py` | test_skill_manager.py | Skill discovery, reading, YAML parsing, deduplication |
| `schema_validator.py` | test_schema_validator.py | Name/version/status/SKILL.md validation |

### Service Layer Coverage

| Service | Test File | Coverage Scenarios |
|---------|-----------|-------------------|
| `SkillService` | test_skill_service.py | CRUD, version management, search, changelog |
| `TaskManager` | test_task_manager.py | Task status enum, dataclass, DB mapping |

---

## Known Limitations

1. **Streaming tests use mock session**: `/agent/run/stream` endpoint directly uses `AsyncSessionLocal`, tests use mock replacement, actual trace writing not verified
2. **E2E tests require running services**: Playwright tests need frontend and backend services running on localhost:62600/62610
3. **No real LLM calls**: All Agent tests mock Claude API, actual LLM interaction quality not verified
