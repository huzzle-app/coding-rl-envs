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
TEST_OUTPUT=$(go test -race -v ./... 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -c -- 'PASS:' || true)
FAILED=$(echo "$TEST_OUTPUT" | grep -c -- 'FAIL:' || true)
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


# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
echo "Pass rate: $RATIO  Reward: $REWARD"
