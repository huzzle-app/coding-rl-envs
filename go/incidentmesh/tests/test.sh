#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "${TRAINING_MODE:-}" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "${PREV_PASSED:-}" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

set +e
TEST_OUTPUT=$(go test -race -v ./... 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -c -- '--- PASS:' || true)
FAILED=$(echo "$TEST_OUTPUT" | grep -c -- '--- FAIL:' || true)
TOTAL=$((PASSED + FAILED))

if [ "$TOTAL" -eq 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: go test failed before any test result could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Use local scoring module with multi-solution bonus (8-threshold, Ultra-Principal)
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
echo "Pass rate: $RATIO  Reward: $REWARD"

# Show incremental info if available
if [ -n "${PREV_PASSED:-}" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
