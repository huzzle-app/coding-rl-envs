#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(./gradlew test --no-daemon 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse JUnit XML from all modules
TOTAL_TESTS=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

for xml in $(find . -path '*/test-results/test/TEST-*.xml' 2>/dev/null); do
    T=$(grep -oE 'tests="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    F=$(grep -oE 'failures="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    E=$(grep -oE 'errors="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    S=$(grep -oE 'skipped="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    TOTAL_TESTS=$((TOTAL_TESTS + T))
    TOTAL_FAILURES=$((TOTAL_FAILURES + F))
    TOTAL_ERRORS=$((TOTAL_ERRORS + E))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + S))
done

PASSED=$((TOTAL_TESTS - TOTAL_FAILURES - TOTAL_ERRORS - TOTAL_SKIPPED))
TOTAL=$((TOTAL_TESTS - TOTAL_SKIPPED))

if [ "$TOTAL" -le 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found. Reward: 0.0"
    exit 0
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 8-threshold sparse reward (Principal)
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $TOTAL_FAILURES failures, $TOTAL_ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
