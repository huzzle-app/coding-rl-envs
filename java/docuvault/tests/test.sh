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

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "$PREV_PASSED" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

# Anti-tampering: verify test files haven't been modified
TAMPERED=0
if command -v git &>/dev/null; then
  TEST_DIFF=$(git diff --name-only -- src/test/ 2>/dev/null || true)
  if [ -n "$TEST_DIFF" ]; then
    echo "WARNING: Test files have been modified. Restoring originals."
    git checkout -- src/test/ 2>/dev/null || true
    TAMPERED=1
  fi
  ENV_DIFF=$(git diff --name-only -- environment/ tests/test.sh 2>/dev/null || true)
  if [ -n "$ENV_DIFF" ]; then
    echo "WARNING: Environment/scoring files have been modified. Restoring originals."
    git checkout -- environment/ tests/test.sh 2>/dev/null || true
    TAMPERED=1
  fi
fi

# Sanity check: total tests should be >= 150 (expected 158)
# Prevents agents from deleting test files to inflate pass rate
MIN_EXPECTED_TESTS=155

set +e
TEST_OUTPUT=$(mvn test -B 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Maven Surefire summary: "Tests run: X, Failures: Y, Errors: Z, Skipped: W"
# There may be multiple lines (one per test class), sum them up
TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

## Maven outputs "Tests run:" both per-class (with "-- in ClassName") and as a
## final summary (without "-- in"). Only sum summary lines to avoid double-counting.
while IFS= read -r line; do
    RUN=$(echo "$line" | grep -oE 'Tests run: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    FAIL=$(echo "$line" | grep -oE 'Failures: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    ERR=$(echo "$line" | grep -oE 'Errors: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    SKIP=$(echo "$line" | grep -oE 'Skipped: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    TOTAL_RUN=$((TOTAL_RUN + RUN))
    TOTAL_FAILURES=$((TOTAL_FAILURES + FAIL))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERR))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIP))
done < <(echo "$TEST_OUTPUT" | grep 'Tests run:' | grep -v -- '-- in')

PASSED=$((TOTAL_RUN - TOTAL_FAILURES - TOTAL_ERRORS - TOTAL_SKIPPED))
TOTAL=$((TOTAL_RUN - TOTAL_SKIPPED))

if [ "$TOTAL" -le 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

# Anti-tampering: ensure test count hasn't dropped significantly
if [ "$TOTAL" -lt "$MIN_EXPECTED_TESTS" ]; then
    echo "ERROR: Only $TOTAL tests found (expected >= $MIN_EXPECTED_TESTS). Possible test deletion detected."
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: test count too low. Reward: 0.0"
    exit 1
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward
# Use local scoring module with multi-solution bonus (with bash fallback)
REWARD=""
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null)
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

# JSON results output
if command -v python3 &>/dev/null; then
  RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')
  echo "$RESULTS_JSON" > /logs/verifier/results.json
fi
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
