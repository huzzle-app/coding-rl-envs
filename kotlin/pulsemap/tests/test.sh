#!/bin/bash
# Harbor verifier script for PulseMap (Kotlin/Gradle)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "$PREV_PASSED" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

set +e
TEST_OUTPUT=$(./gradlew test --no-daemon 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse JUnit XML reports from build/test-results/test/
TOTAL_TESTS=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

for xml in $(find . -path '*/test-results/test/TEST-*.xml' 2>/dev/null); do
    [ -f "$xml" ] || continue
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
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward (Senior)
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $TOTAL_FAILURES failures, $TOTAL_ERRORS errors (total: $TOTAL)"
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
