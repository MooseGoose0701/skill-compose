-- Create test database for running tests
-- This script runs automatically when PostgreSQL container starts for the first time

-- Create test database if not exists
SELECT 'CREATE DATABASE skills_api_test OWNER skills'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'skills_api_test')\gexec

-- Connect to test database
\c skills_api_test
