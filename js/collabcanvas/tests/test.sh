#!/bin/bash
# Harbor verifier script for CollabCanvas (JavaScript/Jest)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(npx jest --ci --no-color 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Jest "Tests:" summary line: "Tests: X failed, Y passed, Z total"
PASSED=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ total' | grep -oE '[0-9]+' || echo 0)

PASSED=${PASSED:-0}
TOTAL=${TOTAL:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found or all tests skipped. Reward: 0.0"
    exit 0
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward function for senior environment
# Thresholds: [0.25, 0.50, 0.75, 0.90, 1.0]
# Rewards:    [0.0,  0.15, 0.35, 0.65, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed out of $TOTAL total"
echo "Pass ratio: $RATIO | Reward: $REWARD"
