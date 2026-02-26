---
sidebar_position: 7
---

# Build a Custom Executor

Build Docker images that provide custom code execution environments for your agents.

## Prerequisites

- Docker installed
- Understanding of [executor concepts](/concepts/executors)

## Approach 1: From Any Base Image

Use this when you have an existing large image and want to add executor capabilities.

### Dockerfile

Create `docker/executor/Dockerfile.my-custom`:

```docker
FROM your-big-image:tag

LABEL org.opencontainers.image.title="Skills Executor - My Custom"

WORKDIR /app

# Required: install executor server dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.109.0 \
    uvicorn>=0.27.0 \
    pydantic>=2.5.0 \
    jupyter_client>=8.0.0 \
    ipykernel>=6.0.0

# Required: copy executor server and kernel module
COPY executor_server.py .
COPY ipython_kernel.py .

# Required: set environment variables
ENV EXECUTOR_NAME=my-custom
ENV WORKSPACES_DIR=/app/workspaces
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/workspaces
EXPOSE 62680
CMD ["uvicorn", "executor_server:app", "--host", "0.0.0.0", "--port", "62680"]
```

### Build and Test

```bash
cd docker/executor

# Build
docker build -f Dockerfile.my-custom -t skillcompose/executor-my-custom:latest .

# Test
docker run -d --name test-exec -p 62680:62680 skillcompose/executor-my-custom:latest

curl http://localhost:62680/health

curl -X POST http://localhost:62680/execute/python \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1+1)", "workspace_id": "test"}'

# Cleanup
docker stop test-exec && docker rm test-exec
```

## Approach 2: Extend skillcompose/executor-base

Use this when you only need to add Python packages to the base environment. Faster to build since the base image already includes the executor server.

### Dockerfile

Create `docker/executor/Dockerfile.my-extended`:

```docker
FROM skillcompose/executor-base:latest

LABEL org.opencontainers.image.title="Skills Executor - My Extended"

# Install additional packages
RUN pip install --no-cache-dir \
    numpy pandas matplotlib scikit-learn

# System dependencies if needed
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     ffmpeg && rm -rf /var/lib/apt/lists/*

# Required: set executor name
ENV EXECUTOR_NAME=my-extended

# CMD, EXPOSE, WORKSPACES_DIR inherited from base
```

### Build and Test

```bash
cd docker/executor
docker build -f Dockerfile.my-extended -t skillcompose/executor-my-extended:latest .

docker run -d --name test-exec -p 62680:62680 skillcompose/executor-my-extended:latest

curl -X POST http://localhost:62680/execute/python \
  -H "Content-Type: application/json" \
  -d '{"code": "import pandas; print(pandas.__version__)", "workspace_id": "test"}'

docker stop test-exec && docker rm test-exec
```

## Comparison

| Item | Approach 1 (Any Base) | Approach 2 (Extend Base) |
|------|----------------------|--------------------------|
| `FROM` | `your-image:tag` | `skillcompose/executor-base:latest` |
| COPY executor_server.py + ipython_kernel.py | Required | Inherited |
| Install fastapi/uvicorn/jupyter_client/ipykernel | Required | Inherited |
| Set CMD / EXPOSE | Required | Inherited |
| Set EXECUTOR_NAME | Required | Required |
| Build speed | Slower | Fast |

## Register the Executor

Custom executors are registered by adding a service definition to `docker/docker-compose.yaml` and a URL mapping in the backend config.

### Step 1: Add to docker-compose.yaml

Add the service definition in the executor section of `docker/docker-compose.yaml`:

```yaml
# Custom executor: my-custom
executor-my-custom:
  build:
    context: ./executor
    dockerfile: Dockerfile.my-custom
  image: skillcompose/executor-my-custom:latest
  container_name: skills-executor-my-custom
  restart: unless-stopped
  profiles:
    - my-custom
  volumes:
    - workspaces:/app/workspaces
    - ${SKILLS_PATH:-./volumes/skills}:/app/skills:ro
  environment:
    - EXECUTOR_NAME=my-custom
    - TZ=${TZ:-UTC}
  networks:
    - skills-network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:62680/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
  deploy:
    resources:
      limits:
        memory: 4G
```

### Step 2: Add URL mapping

Add the executor URL to `app/services/executor_client.py` in the `EXECUTOR_URLS` dict, and to `app/config.py`.

### Step 3: Start the executor

```bash
cd docker
docker compose --profile my-custom up -d
```

The executor will be auto-discovered via HTTP health check and appear on the Executors page.

## Assign to an Agent

There are three ways to use a custom executor:

### From the Chat Panel

When online executors are detected, an **Executor** dropdown appears in the chat panel and fullscreen chat page (`/chat`). Select your executor to route code execution to it.

### From Agent Configuration

1. Go to **Agents** > select an agent
2. Choose the executor from the **Executor** dropdown
3. Save

All `execute_code` and `bash` calls from this agent now route to the executor container.

### Via API

In custom mode, pass the `executor_id` in the request:

```bash
curl -X POST http://localhost:62610/api/v1/agent/run/stream \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Run my analysis",
    "executor_id": "executor-uuid-here"
  }'
```

## Environment Variables

You do **not** need to manually configure API keys or other environment variables in your executor's `docker-compose.yaml`. The API server automatically forwards all user-configured environment variables (from the Environment page / `.env` file) to the executor at runtime via the HTTP request. See [Executors — Environment Variables](/concepts/executors#environment-variables) for details.

## Troubleshooting

### Container won't start

```bash
# Check port conflicts
lsof -i :62680

# View logs
docker logs skills-executor-my-custom
```

### Health check fails

```bash
docker logs skills-executor-my-custom
```

Verify that `uvicorn executor_server:app` starts without errors.

### Package not found

```bash
docker exec skills-executor-my-custom pip list | grep your-package
```

## Related

- [Executors](/concepts/executors) — Executor concepts
- [Create an Agent](/how-to/create-agent) — Agent configuration
