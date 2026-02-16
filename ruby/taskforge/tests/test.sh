#!/bin/bash
# Harbor verifier script for TaskForge (Ruby/RSpec)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support (display only; scoring.py does not accept --prev-passed)

set +e
TEST_OUTPUT=$(bundle exec rspec --format progress 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse RSpec summary: "X examples, Y failures" or "X examples, Y failures, Z pending"
TOTAL=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ examples?' | grep -oE '[0-9]+' | tail -1 || echo 0)
FAILURES=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failures?' | grep -oE '[0-9]+' | tail -1 || echo 0)

TOTAL=${TOTAL:-0}
FAILURES=${FAILURES:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

PASSED=$((TOTAL - FAILURES))

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward for Senior environment
# Thresholds: [0.50, 0.75, 0.90, 1.0]
# Rewards:    [0.15, 0.35, 0.65, 1.0]
# Below 50%: 0.0
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILURES failed (total: $TOTAL)"
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
