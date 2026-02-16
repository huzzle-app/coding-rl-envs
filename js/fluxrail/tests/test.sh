#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# ── Anti-reward-hacking: detect test file tampering ──
TESTS_MODIFIED=$(cd /app && git diff --name-only HEAD -- tests/ 2>/dev/null | wc -l || echo "0")
if [ "$TESTS_MODIFIED" -gt 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward":0,"reason":"test_files_modified"}' > /logs/verifier/results.json
  echo "TAMPERING DETECTED: test files were modified. Reward set to 0."
  echo "Modified test files:"
  cd /app && git diff --name-only HEAD -- tests/ 2>/dev/null
  exit 0
fi

# ── Anti-reward-hacking: detect environment/reward file tampering ──
ENV_MODIFIED=$(cd /app && git diff --name-only HEAD -- environment/ 2>/dev/null | wc -l || echo "0")
if [ "$ENV_MODIFIED" -gt 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward":0,"reason":"environment_files_modified"}' > /logs/verifier/results.json
  echo "TAMPERING DETECTED: environment files were modified. Reward set to 0."
  exit 0
fi

# ── Anti-reward-hacking: verify minimum test count ──
# The environment must produce at least 8500 tests (actual count is ~9039)
MIN_EXPECTED_TESTS=8500

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "${TRAINING_MODE:-}" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "${PREV_PASSED:-}" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

set +e
TEST_OUTPUT=$(npm test 2>&1)
TEST_EXIT=$?
set -e

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -c '^ok ' || true)
FAILED=$(echo "$TEST_OUTPUT" | grep -c '^not ok ' || true)
TOTAL=$((PASSED + FAILED))

if [ "$TOTAL" -eq 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: node tests failed before any TAP result could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi

# ── Anti-reward-hacking: verify test count hasn't dropped ──
if [ "$TOTAL" -lt "$MIN_EXPECTED_TESTS" ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "{\"reward\":0,\"reason\":\"test_count_too_low\",\"total\":$TOTAL,\"min_expected\":$MIN_EXPECTED_TESTS}" > /logs/verifier/results.json
  echo "TAMPERING DETECTED: Only $TOTAL tests found (expected >= $MIN_EXPECTED_TESTS). Reward set to 0."
  exit 0
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"

# Show incremental info if available
if [ -n "${PREV_PASSED:-}" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
