#!/bin/bash
# ==============================================================================
# Skills API - Docker Redeploy Script (Development)
# ==============================================================================
# Stop, rebuild images from source, and restart services.
# Uses docker-compose.dev.yaml (with build: sections).
#
# Usage: ./redeploy.sh [service] [--no-cache]
#   ./redeploy.sh              # Redeploy all services (uses cache for fast build)
#   ./redeploy.sh api          # Redeploy API only
#   ./redeploy.sh web          # Redeploy Web only
#   ./redeploy.sh --no-cache   # No-cache rebuild (only when dependencies change)
# ==============================================================================

set -e

cd "$(dirname "$0")"

SERVICE=""
NO_CACHE=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-cache)
            NO_CACHE="--no-cache"
            ;;
        *)
            SERVICE="$arg"
            ;;
    esac
done

SERVICE=${SERVICE:-all}

echo "=== Skills API Docker Redeploy ==="
echo "Service: $SERVICE"
if [ -n "$NO_CACHE" ]; then
    echo "Mode: no-cache (full rebuild)"
else
    echo "Mode: cached (fast, only changed layers rebuild)"
fi
echo ""

COMPOSE_FILE="docker-compose.dev.yaml"

# Step 1: Stop containers
echo "[1/3] Stopping containers..."
docker compose -f $COMPOSE_FILE down

# Step 2: Rebuild
echo "[2/3] Building images..."
if [ "$SERVICE" = "all" ]; then
    docker compose -f $COMPOSE_FILE build $NO_CACHE
else
    docker compose -f $COMPOSE_FILE build $NO_CACHE "$SERVICE"
fi

# Step 3: Start services
echo "[3/3] Starting services..."
docker compose -f $COMPOSE_FILE up -d

echo ""
echo "=== Redeploy Complete ==="
echo "Services status:"
docker compose -f $COMPOSE_FILE ps
