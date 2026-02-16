#!/bin/bash
# Harbor verifier script for CacheForge (C++/CTest)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "$PREV_PASSED" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

# Build first if needed
if [ ! -d "build" ]; then
    cmake -B build -DCMAKE_BUILD_TYPE=Debug 2>&1 || true
fi
cmake --build build --parallel 2>&1 || true

# Run CTest and capture output
set +e
TEST_OUTPUT=$(cd build && ctest --output-on-failure --no-compress-output 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse CTest summary: "X% tests passed, Y tests failed out of Z"
# or "X tests passed, Y tests failed out of Z"
TOTAL=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ tests failed out of [0-9]+' | grep -oE '[0-9]+$' | head -1 || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ tests failed' | head -1 | grep -oE '[0-9]+' || echo 0)

TOTAL=${TOTAL:-0}
FAILED=${FAILED:-0}

# Fallback: count individual test results if summary not found
if [ "$TOTAL" -eq 0 ]; then
    PASSED=$(echo "$TEST_OUTPUT" | grep -cE 'Test\s+#[0-9]+:.*\.+\s+Passed' || echo 0)
    FAILED_COUNT=$(echo "$TEST_OUTPUT" | grep -cE 'Test\s+#[0-9]+:.*\.+\s+(Failed|Not Run|\*\*\*Failed)' || echo 0)
    NOT_RUN=$(echo "$TEST_OUTPUT" | grep -cE 'Test\s+#[0-9]+:.*\.+\s+Not Run' || echo 0)
    FAILED=$((FAILED_COUNT))
    TOTAL=$((PASSED + FAILED))
fi

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found or build failed. Reward: 0.0"
    exit 1
fi

PASSED=$((TOTAL - FAILED))

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Code correctness score (source-level checks for 11 previously-untested bugs)
CODE_SCORE=$(python3 /app/environment/code_checks.py /app 2>/dev/null | tail -1 | grep -oE '[0-9]+\.[0-9]+' || echo "0.0")
echo "Code correctness score: $CODE_SCORE"

# 5-threshold sparse reward for Senior environment (blended with code correctness)
# Thresholds: [0.50, 0.75, 0.90, 1.0]
# Rewards:    [0.15, 0.35, 0.65, 1.0]
# Below 50%: 0.0
# Final reward = 0.70 * test_pass_reward + 0.30 * code_correctness
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
echo "Pass ratio: $RATIO | Code correctness: $CODE_SCORE | Reward: $REWARD"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
