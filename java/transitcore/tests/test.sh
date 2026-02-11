#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Prevent stale surefire reports from previous runs contaminating counts.
if [ -d target/surefire-reports ]; then
  find target/surefire-reports -type f -name 'TEST-*.xml' -delete
fi

set +e
TEST_OUTPUT=$(mvn test -B 2>&1)
TEST_EXIT=$?
set -e

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

for report in target/surefire-reports/TEST-*.xml; do
  if [ ! -f "$report" ]; then
    continue
  fi

  LINE=$(grep -m1 '<testsuite ' "$report" || true)
  RUN=$(echo "$LINE" | sed -n 's/.*tests="\([0-9]\+\)".*/\1/p')
  FAIL=$(echo "$LINE" | sed -n 's/.*failures="\([0-9]\+\)".*/\1/p')
  ERR=$(echo "$LINE" | sed -n 's/.*errors="\([0-9]\+\)".*/\1/p')
  SKIP=$(echo "$LINE" | sed -n 's/.*skipped="\([0-9]\+\)".*/\1/p')

  RUN=${RUN:-0}
  FAIL=${FAIL:-0}
  ERR=${ERR:-0}
  SKIP=${SKIP:-0}

  TOTAL_RUN=$((TOTAL_RUN + RUN))
  TOTAL_FAILURES=$((TOTAL_FAILURES + FAIL))
  TOTAL_ERRORS=$((TOTAL_ERRORS + ERR))
  TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIP))
done

TOTAL=$((TOTAL_RUN - TOTAL_SKIPPED))
if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: mvn test failed before any test summary could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi

PASSED=$((TOTAL - TOTAL_FAILURES - TOTAL_ERRORS))
if [ "$PASSED" -lt 0 ]; then
  PASSED=0
fi


# 8-tier thresholds for principal difficulty
# Use local scoring module with multi-solution bonus (with bash fallback)
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null)
fi
if [ -z "$REWARD" ]; then
  # Bash fallback for containers without Python
  RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")
  REWARD=$(awk -v r="$RATIO" 'BEGIN {
    if (r >= 1.0) print 1.0
    else if (r >= 0.95) print 0.78
    else if (r >= 0.85) print 0.55
    else if (r >= 0.70) print 0.38
    else if (r >= 0.55) print 0.22
    else if (r >= 0.40) print 0.12
    else if (r >= 0.25) print 0.05
    else print 0.0
  }')
fi

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $((TOTAL_FAILURES + TOTAL_ERRORS)) failed (total: $TOTAL)"
