#!/bin/bash
# Harbor verifier script for ShopStream (Ruby/RSpec)
# Runs the test suite, computes sparse reward with 8 thresholds, writes to /logs/verifier/reward.txt
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Run RSpec and capture output
TEST_OUTPUT=$(bundle exec rspec --format progress 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse RSpec summary: "X examples, Y failures" or "X examples, Y failures, Z pending"
TOTAL=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ examples?' | grep -oE '[0-9]+' | tail -1 || echo 0)
FAILURES=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failures?' | grep -oE '[0-9]+' | tail -1 || echo 0)

TOTAL=${TOTAL:-0}
FAILURES=${FAILURES:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found or all tests skipped. Reward: 0.0"
    exit 0
fi

PASSED=$((TOTAL - FAILURES))

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Apply 8-threshold sparse reward function (Principal level)
# Thresholds: [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
# Rewards:    [0.0,  0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILURES failed (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
