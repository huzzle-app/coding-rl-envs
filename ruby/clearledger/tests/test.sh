#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "${TRAINING_MODE:-}" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support (informational only; scoring.py does not use this directly)
PREV_PASSED="${PREV_PASSED:-}"

set +e
TEST_OUTPUT=$(ruby -Ilib -Itests tests/run_all.rb 2>&1)
TEST_EXIT=$?
set -e

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ runs?' | tail -1 | grep -oE '[0-9]+' || true)
FAILURES=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failures?' | tail -1 | grep -oE '[0-9]+' || true)
ERRORS=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ errors?' | tail -1 | grep -oE '[0-9]+' || true)

TOTAL=${TOTAL:-0}
FAILURES=${FAILURES:-0}
ERRORS=${ERRORS:-0}

if [ "$TOTAL" -eq 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: ruby test execution failed before any result could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi

PASSED=$((TOTAL - FAILURES - ERRORS))
if [ "$PASSED" -lt 0 ]; then
  PASSED=0
fi


# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app --no-bonus $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app --no-bonus $TRAINING_MODE_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $((FAILURES + ERRORS)) failed (total: $TOTAL)"

# Show incremental info if available
if [ -n "${PREV_PASSED:-}" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
