#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

set +e
TEST_OUTPUT=$(cargo test --no-fail-fast 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL_PASSED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ passed' | awk '{sum+=$1} END {print sum+0}')
TOTAL_FAILED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failed' | awk '{sum+=$1} END {print sum+0}')
TOTAL=$((TOTAL_PASSED + TOTAL_FAILED))

if [ "$TOTAL" -eq 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: cargo test failed before any test result could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi


# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $TOTAL_PASSED passed, $TOTAL_FAILED failed (total: $TOTAL)"
