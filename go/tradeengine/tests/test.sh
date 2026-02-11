#!/bin/bash
# Harbor verifier script for TradeEngine (Go/go test)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(go test -race -v ./... 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse go test output: count "--- PASS:" and "--- FAIL:" lines
PASSED=$(echo "$TEST_OUTPUT" | grep -c '--- PASS:' || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -c '--- FAIL:' || echo 0)

PASSED=${PASSED:-0}
FAILED=${FAILED:-0}

TOTAL=$((PASSED + FAILED))

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found. Reward: 0.0"
    exit 0
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 8-threshold sparse reward for Principal difficulty
# Thresholds: [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
# Rewards:    [0.0,  0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
