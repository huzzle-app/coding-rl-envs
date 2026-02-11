#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(ruby -Ilib -Itests tests/run_all.rb 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

SUMMARY=$(echo "$TEST_OUTPUT" | grep -E '^[0-9]+ runs, [0-9]+ assertions, [0-9]+ failures, [0-9]+ errors' | tail -1)
RUNS=$(echo "$SUMMARY" | sed -n 's/^\([0-9]\+\) runs.*/\1/p')
FAILURES=$(echo "$SUMMARY" | sed -n 's/.* \([0-9]\+\) failures.*/\1/p')
ERRORS=$(echo "$SUMMARY" | sed -n 's/.* \([0-9]\+\) errors.*/\1/p')

RUNS=${RUNS:-0}
FAILURES=${FAILURES:-0}
ERRORS=${ERRORS:-0}

if [ "$RUNS" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "No tests found. Reward: 0.0"
  exit 0
fi

FAILED=$((FAILURES + ERRORS))
PASSED=$((RUNS - FAILED))
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed (total: $RUNS)"
