# ==============================================================================
# Skills API - Backend Dockerfile
# ==============================================================================
# Lightweight image for the FastAPI backend service
# Includes: Python, Node.js (for MCP servers), Jupyter kernel
# ==============================================================================

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ==============================================================================
# Build Stage - Install dependencies
# ==============================================================================
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 (for MCP servers)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Jupyter kernel for code execution
RUN pip install --no-cache-dir ipykernel \
    && python -m ipykernel install --name python3 --user

# ==============================================================================
# Production Stage - Final image
# ==============================================================================
FROM base AS production

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv/uvx for MCP servers (fetch, time, git)
RUN pip install --no-cache-dir uv

# Pre-cache MCP server packages so first invocation doesn't need network access
RUN uvx mcp-server-fetch --help > /dev/null 2>&1 || true && \
    uvx mcp-server-time --help > /dev/null 2>&1 || true && \
    uvx mcp-server-git --help > /dev/null 2>&1 || true

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY app/ ./app/

# Create directories for mounted volumes
RUN mkdir -p /app/skills /app/data /app/logs /app/uploads /app/config

# Copy default skills (will be overwritten by volume mount if exists)
COPY seed_skills/ ./default-skills/

# Copy default config
COPY config/ ./default-config/

# Copy entrypoint script
COPY docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set Python path
ENV PYTHONPATH=/app

# Expose API port
EXPOSE 62610

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:62610/ || exit 1

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (8 workers to handle concurrent requests during long-running tasks)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "62610", "--workers", "8"]
