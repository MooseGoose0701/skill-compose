#!/bin/bash
# ==============================================================================
# Skills API - Entrypoint Script
# ==============================================================================
# This script initializes directories and copies default files if needed
# ==============================================================================

set -e

echo "=== Skills API Entrypoint ==="

# ------------------------------------------------------------------------------
# Initialize skills directory
# ------------------------------------------------------------------------------
# Check for actual skill folders (not just hidden files like .gitkeep)
if [ -z "$(find /app/skills -mindepth 1 -maxdepth 1 -type d 2>/dev/null)" ]; then
    echo "Initializing skills directory with default skills..."
    cp -r /app/default-skills/* /app/skills/
    echo "Skills initialized."
else
    echo "Skills directory already initialized."
fi

# ------------------------------------------------------------------------------
# Initialize config directory
# ------------------------------------------------------------------------------
# Check for the key config file (mcp.json) to determine if config needs init
if [ ! -f /app/config/mcp.json ]; then
    echo "Initializing config directory with default config..."
    cp -r /app/default-config/* /app/config/
    echo "Config initialized."
else
    echo "Config directory already initialized."
    # Always update seed files (new skills/agents/executors may have been added)
    for f in seed_agents.json seed_skills.json executors.json; do
        if [ -f /app/default-config/$f ]; then
            cp /app/default-config/$f /app/config/$f 2>/dev/null || true
        fi
    done
    echo "Updated seed files from defaults."
fi

# ------------------------------------------------------------------------------
# Initialize config/.env from process environment (for Settings page)
# ------------------------------------------------------------------------------
# On first run, seed /app/config/.env from docker-compose environment: vars.
# This is the single source of truth for the Settings API and load_dotenv.
# Subsequent restarts skip this — Settings UI changes persist in the volume.
# ------------------------------------------------------------------------------
if [ ! -f /app/config/.env ]; then
    if [ -f /app/.env.seed ]; then
        echo "Seeding /app/config/.env from docker/.env ..."
        cp /app/.env.seed /app/config/.env
    else
        echo "Warning: No .env.seed found, creating empty config/.env"
        touch /app/config/.env
    fi
    chmod 666 /app/config/.env
    echo "Config .env initialized."
else
    echo "Writable .env already exists in config directory."
fi

# Ensure .env is writable (may be owned by host root due to userns remapping)
if [ ! -w /app/config/.env ]; then
    echo "Fixing .env permissions (not writable by container process)..."
    chmod 666 /app/config/.env 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# Ensure data directory exists
# ------------------------------------------------------------------------------
mkdir -p /app/data
echo "Data directory ready."

# ------------------------------------------------------------------------------
# Ensure logs directory exists
# ------------------------------------------------------------------------------
mkdir -p /app/logs
echo "Logs directory ready."

# ------------------------------------------------------------------------------
# Ensure uploads directory exists
# ------------------------------------------------------------------------------
mkdir -p /app/uploads
echo "Uploads directory ready."

# ------------------------------------------------------------------------------
# Ensure backups directory exists
# ------------------------------------------------------------------------------
mkdir -p /app/backups
echo "Backups directory ready."

# ------------------------------------------------------------------------------
# Environment info
# ------------------------------------------------------------------------------
echo ""
echo "=== Environment ==="
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:+set}"
echo "CLAUDE_MODEL: ${CLAUDE_MODEL:-claude-sonnet-4-5-20250929}"
echo "DEBUG: ${DEBUG:-false}"
echo ""

# ------------------------------------------------------------------------------
# Initialize database (before starting workers)
# ------------------------------------------------------------------------------
echo "=== Initializing Database ==="
python -c "
import asyncio
from app.db.database import init_db
asyncio.run(init_db())
print('Database initialized successfully.')
" && echo "Database ready." || echo "Database initialization failed (may already be initialized)."

# ------------------------------------------------------------------------------
# Warmup function - call all API endpoints to ensure full initialization
# ------------------------------------------------------------------------------
warmup_api() {
    local max_attempts=30
    local attempt=1

    # Wait for API to be ready
    while [ $attempt -le $max_attempts ]; do
        if curl -sf http://localhost:62610/health > /dev/null 2>&1; then
            break
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    if [ $attempt -gt $max_attempts ]; then
        echo "Warmup timeout"
        return
    fi

    # All endpoints from home page (call 8x each to hit all workers)
    local endpoints=(
        "/api/v1/registry/skills"
        "/api/v1/registry/tags"
        "/api/v1/registry/unregistered-skills"
        "/api/v1/agents"
        "/api/v1/tools/registry"
        "/api/v1/mcp/servers"
        "/api/v1/traces"
        "/api/v1/executors"
        "/api/v1/browser/list"
        "/api/v1/settings/env"
    )

    echo "Warming up API endpoints..."
    for endpoint in "${endpoints[@]}"; do
        # Send 8 requests sequentially to hit all workers
        for i in {1..8}; do
            curl -s "http://localhost:62610${endpoint}" > /dev/null 2>&1 || true
        done
    done
    echo "API warmup complete"
}

# ------------------------------------------------------------------------------
# Start the application with warmup
# ------------------------------------------------------------------------------
echo "=== Starting Skills API ==="

# Start uvicorn in background
"$@" &
UVICORN_PID=$!

# Run warmup after uvicorn starts
warmup_api

# Wait for uvicorn
wait $UVICORN_PID
