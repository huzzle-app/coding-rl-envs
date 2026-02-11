#!/bin/bash
# TalentFlow Environment Reset Script
# Terminal Bench v2 - Reset to initial buggy state for RL training

set -e

echo "=== Resetting TalentFlow Environment ==="

# Method 1: Git reset (if using git for state management)
if [ -d ".git" ]; then
    echo "Resetting via git..."
    git checkout -- .
    git clean -fd
    echo "Git reset complete."
fi

# Method 2: If using Docker volumes, recreate them
if [ "$1" == "--full" ]; then
    echo "Full reset - removing Docker volumes..."
    docker-compose down -v 2>/dev/null || true
    docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
    echo "Docker volumes removed."
fi

# Clear Python cache
echo "Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Clear pytest cache
rm -rf .pytest_cache 2>/dev/null || true

echo "=== Environment Reset Complete ==="
echo ""
echo "To run tests: ./scripts/run_tests.sh"
echo "To start dev: docker-compose up"
