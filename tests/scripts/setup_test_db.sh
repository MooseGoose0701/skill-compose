#!/bin/bash
# Setup test database for Skills API tests
# Only needed if running tests against PostgreSQL instead of SQLite in-memory

set -e

DB_CONTAINER="skill-composer-db-1"
DB_USER="${DB_USER:-skills}"
DB_PASSWORD="${DB_PASSWORD:-skills123}"
DB_NAME="skills_api_test"

echo "Creating test database '${DB_NAME}'..."

if ! docker ps --format "{{.Names}}" | grep -q "$DB_CONTAINER"; then
    echo "Error: PostgreSQL container '$DB_CONTAINER' is not running."
    echo "Start it with: cd docker && docker compose up -d db"
    exit 1
fi

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
    "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
    "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

echo "Test database '${DB_NAME}' is ready."
echo "Connection string: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
