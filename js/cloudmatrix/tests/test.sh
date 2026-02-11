#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Run Jest test suite
TEST_OUTPUT=$(npx jest --ci --no-color 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Jest output for test results
# Jest summary format: "Tests: X failed, Y passed, Z total"
PASSED=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ total' | grep -oE '[0-9]+' || echo 0)

# Ensure defaults if parsing fails
PASSED=${PASSED:-0}
TOTAL=${TOTAL:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found. Reward: 0.0"
    exit 0
fi

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Apply 8-threshold reward function (Distinguished environment)
# Thresholds: [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
# Rewards:    [0.0,  0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "distinguished" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

# Write reward to file
echo "$REWARD" > /logs/verifier/reward.txt

# Display results
echo "Tests: $PASSED passed out of $TOTAL total"
echo "Pass ratio: $RATIO | Reward: $REWARD"
