#!/bin/bash
# TalentFlow Test Runner Script
# Terminal Bench v2 - Run tests and output results for RL evaluation

set -e

echo "=== TalentFlow Test Runner ==="
echo "Starting test infrastructure..."

# Start services
docker-compose -f docker-compose.test.yml up -d db redis

# Wait for services
echo "Waiting for PostgreSQL..."
until docker-compose -f docker-compose.test.yml exec -T db pg_isready -U talentflow -d talentflow_test > /dev/null 2>&1; do
    sleep 1
done

echo "Waiting for Redis..."
until docker-compose -f docker-compose.test.yml exec -T redis redis-cli ping > /dev/null 2>&1; do
    sleep 1
done

echo "Services ready. Running tests..."

# Run tests
docker-compose -f docker-compose.test.yml run --rm test

# Get exit code
EXIT_CODE=$?

# Cleanup
echo "Cleaning up..."
docker-compose -f docker-compose.test.yml down -v

exit $EXIT_CODE
