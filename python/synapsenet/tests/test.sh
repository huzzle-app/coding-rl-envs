#!/bin/bash
# Harbor verifier script for SynapseNet (Python/pytest)
# Runs the test suite, computes sparse reward, writes to /logs/verifier/reward.txt
set -o pipefail
mkdir -p /logs/verifier

# ============================================================================
# Environment Variables for Training:
#   TRAINING_MODE  - Enable dense rewards: linear, sublinear, smooth
#   TEST_FILE      - Run only tests related to this file (targeted testing)
#   TEST_FAST      - Run fast subset of tests (set to "1" to enable)
#   PREV_PASSED    - Previous passed count for incremental rewards
#   PARSE_ERRORS   - Output structured errors (set to "1" to enable)
# ============================================================================

# Training mode support
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "$PREV_PASSED" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

# Build pytest command
PYTEST_CMD="python -m pytest --tb=short -q --continue-on-collection-errors"

# Targeted testing: run only tests related to specific file
if [ -n "$TEST_FILE" ]; then
  # Convert source file to test pattern
  # e.g., src/routing.py -> tests/*routing* or tests/test_routing.py
  BASE_NAME=$(basename "$TEST_FILE" .py)
  PYTEST_CMD="$PYTEST_CMD -k $BASE_NAME"
  echo "Running targeted tests for: $TEST_FILE (pattern: $BASE_NAME)"
fi

# Fast mode: run subset of tests for quick feedback
if [ "$TEST_FAST" = "1" ]; then
  # Run only first 50 tests or tests marked as 'fast'
  PYTEST_CMD="$PYTEST_CMD --maxfail=10 -x"
  echo "Running in fast mode (stop after 10 failures)"
fi

# Run pytest and capture output
set +e
TEST_OUTPUT=$($PYTEST_CMD 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse pytest summary line: "X passed, Y failed, Z errors"
PASSED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)
ERRORS=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ error' | grep -oE '[0-9]+' || echo 0)

PASSED=${PASSED:-0}
FAILED=${FAILED:-0}
ERRORS=${ERRORS:-0}

TOTAL=$((PASSED + FAILED + ERRORS))

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo '{"passed": 0, "failed": 0, "total": 0, "reward": 0.0}' > /logs/verifier/results.json
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found or all tests skipped. Reward: 0.0"
    exit 1
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Calculate reward using scoring module (8-threshold, Distinguished)
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "distinguished" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")

# Get full JSON results
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "distinguished" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json

# Parse and output structured errors if requested
if [ "$PARSE_ERRORS" = "1" ] && [ "$FAILED" -gt 0 ]; then
  python3 /app/environment/scoring.py --parse-errors /logs/verifier/test_output.txt --language python > /logs/verifier/errors.json 2>/dev/null || true
fi

echo "Tests: $PASSED passed, $FAILED failed, $ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
