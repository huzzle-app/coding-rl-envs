#!/bin/bash
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
TEST_OUTPUT=$(dotnet test --verbosity normal 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -oE 'Passed:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oE 'Failed:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
SKIPPED=$(echo "$TEST_OUTPUT" | grep -oE 'Skipped:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -oE 'Total tests:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)

if [ -z "$TOTAL" ] || [ "$TOTAL" -eq 0 ]; then
  TOTAL=$(echo "$TEST_OUTPUT" | grep -oE 'Total:\s*[0-9]+' | grep -oE '[0-9]+' | tail -1 || echo 0)
fi

# If the build failed before test discovery, force a failing summary instead of "no tests found".
if echo "$TEST_OUTPUT" | grep -qE 'Build FAILED|error CS[0-9]+'; then
  if [ -z "$TOTAL" ] || [ "$TOTAL" -eq 0 ]; then
    TOTAL=1
    FAILED=1
    PASSED=0
    SKIPPED=0
  fi
fi

PASSED=${PASSED:-0}
FAILED=${FAILED:-0}
SKIPPED=${SKIPPED:-0}
TOTAL=${TOTAL:-0}

# Anti-reward-hacking: verify test files haven't been tampered with
EXPECTED_TESTS=9281
if [ "$TOTAL" -gt 0 ] && [ "$TOTAL" -lt "$EXPECTED_TESTS" ]; then
  echo "WARNING: Expected at least $EXPECTED_TESTS tests but found $TOTAL."
  echo "Test suite may have been tampered with. Capping pass rate."
  # Use expected total as denominator to prevent inflated pass rate
  TOTAL=$EXPECTED_TESTS
fi

# Anti-reward-hacking: check that test source files are unmodified
if command -v git &>/dev/null; then
  TEST_CHANGES=$(git diff --name-only HEAD -- tests/ 2>/dev/null | wc -l | tr -d ' ')
  if [ "$TEST_CHANGES" -gt 0 ]; then
    echo "WARNING: Test files have been modified. Penalizing reward."
    # Zero out reward if tests were modified
    echo "0.0" > /logs/verifier/reward.txt
    echo "Tests: $PASSED passed, $FAILED failed, $SKIPPED skipped (total: $TOTAL)"
    echo "Reward: 0.0 (test files modified)"
    exit 0
  fi
fi

if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
  echo "No tests found. Reward: 0.0"
  exit 1
fi

EFFECTIVE_TOTAL=$((TOTAL - SKIPPED))
if [ "$EFFECTIVE_TOTAL" -le 0 ]; then
  EFFECTIVE_TOTAL=$TOTAL
fi

# Use local scoring module with multi-solution bonus (with bash fallback)
REWARD=""
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null)
fi
if [ -z "$REWARD" ]; then
  # Bash fallback for containers without Python
  RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")
  REWARD=$(awk -v r="$RATIO" 'BEGIN {
    if (r >= 1.0) print 1.0
    else if (r >= 0.99) print 0.85
    else if (r >= 0.96) print 0.66
    else if (r >= 0.90) print 0.47
    else if (r >= 0.80) print 0.31
    else if (r >= 0.67) print 0.19
    else if (r >= 0.52) print 0.11
    else if (r >= 0.36) print 0.05
    else if (r >= 0.22) print 0.015
    else print 0.0
  }')
fi

echo "$REWARD" > /logs/verifier/reward.txt

# JSON results output
if command -v python3 &>/dev/null; then
  RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')
  echo "$RESULTS_JSON" > /logs/verifier/results.json
fi
echo "Tests: $PASSED passed, $FAILED failed, $SKIPPED skipped (total: $TOTAL)"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
