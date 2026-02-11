#!/bin/bash
# Harbor verifier script for DocuVault (Java/Maven)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(mvn test -B 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Maven Surefire summary: "Tests run: X, Failures: Y, Errors: Z, Skipped: W"
# There may be multiple lines (one per test class), sum them up
TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

while IFS= read -r line; do
    RUN=$(echo "$line" | grep -oE 'Tests run: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    FAIL=$(echo "$line" | grep -oE 'Failures: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    ERR=$(echo "$line" | grep -oE 'Errors: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    SKIP=$(echo "$line" | grep -oE 'Skipped: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    TOTAL_RUN=$((TOTAL_RUN + RUN))
    TOTAL_FAILURES=$((TOTAL_FAILURES + FAIL))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERR))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIP))
done < <(echo "$TEST_OUTPUT" | grep 'Tests run:')

PASSED=$((TOTAL_RUN - TOTAL_FAILURES - TOTAL_ERRORS - TOTAL_SKIPPED))
TOTAL=$((TOTAL_RUN - TOTAL_SKIPPED))

if [ "$TOTAL" -le 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found. Reward: 0.0"
    exit 0
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward
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
echo "Tests: $PASSED passed, $TOTAL_FAILURES failures, $TOTAL_ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
