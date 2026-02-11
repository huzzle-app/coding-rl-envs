#!/bin/bash
# Harbor verifier script for HealthLink (C#/dotnet test)
# Runs the test suite, computes sparse reward, writes to /logs/verifier/reward.txt
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Run dotnet test and capture output
TEST_OUTPUT=$(dotnet test --no-restore --verbosity normal 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse dotnet test summary line: "Failed! - Failed: X, Passed: Y, Skipped: Z, Total: W"
# or "Passed! - Failed: 0, Passed: Y, Skipped: Z, Total: W"
PASSED=$(echo "$TEST_OUTPUT" | grep -oE 'Passed:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oE 'Failed:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
SKIPPED=$(echo "$TEST_OUTPUT" | grep -oE 'Skipped:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -oE 'Total:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)

PASSED=${PASSED:-0}
FAILED=${FAILED:-0}
TOTAL=${TOTAL:-0}

# Fallback: count individual test result lines if summary not found
if [ "$TOTAL" -eq 0 ]; then
    PASSED=$(echo "$TEST_OUTPUT" | grep -c '✓\|Passed' || echo 0)
    FAILED=$(echo "$TEST_OUTPUT" | grep -c '✗\|Failed' || echo 0)
    TOTAL=$((PASSED + FAILED))
fi

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found or all tests skipped. Reward: 0.0"
    exit 0
fi

# Exclude skipped from denominator
EFFECTIVE_TOTAL=$((TOTAL - ${SKIPPED:-0}))
if [ "$EFFECTIVE_TOTAL" -le 0 ]; then
    EFFECTIVE_TOTAL=$TOTAL
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $EFFECTIVE_TOTAL}")

# Apply 5-threshold sparse reward function
# Thresholds: [0.25, 0.50, 0.75, 0.90, 1.0]
# Rewards:    [0.0,  0.15, 0.35, 0.65, 1.0]
# Use local scoring module with multi-solution bonus (with bash fallback)
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG 2>/dev/null)
fi
if [ -z "$REWARD" ]; then
  # Bash fallback for containers without Python
  RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")
  REWARD=$(awk -v r="$RATIO" 'BEGIN {
    if (r >= 1.0) print 1.0
    else if (r >= 0.90) print 0.65
    else if (r >= 0.75) print 0.35
    else if (r >= 0.50) print 0.15
    else print 0.0
  }')
fi

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed, ${SKIPPED:-0} skipped (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
