#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# ---------------------------------------------------------------------------
# Anti-reward-hacking: verify test file integrity before running tests.
# Agents must fix source files only — test modifications are not allowed.
# ---------------------------------------------------------------------------
TEST_FILES_MODIFIED=0
if command -v git &> /dev/null && git rev-parse --is-inside-work-tree &> /dev/null; then
  CHANGED_TESTS=$(git diff --name-only HEAD -- 'tests/' 2>/dev/null | head -20)
  if [ -n "$CHANGED_TESTS" ]; then
    TEST_FILES_MODIFIED=1
    echo "WARNING: Test files have been modified (not allowed):"
    echo "$CHANGED_TESTS"
  fi
  CHANGED_ENV=$(git diff --name-only HEAD -- 'environment/' 2>/dev/null | head -20)
  if [ -n "$CHANGED_ENV" ]; then
    TEST_FILES_MODIFIED=1
    echo "WARNING: Environment/scoring files have been modified (not allowed):"
    echo "$CHANGED_ENV"
  fi
fi

# Anti-reward-hacking: verify test files still exist
EXPECTED_TEST_FILES=(
  "tests/unit/core_test.go"
  "tests/integration/flow_test.go"
  "tests/concurrency/race_test.go"
  "tests/chaos/replay_test.go"
  "tests/services/contracts_test.go"
  "tests/stress/advanced_bugs_test.go"
  "tests/stress/hyper_matrix_test.go"
)
for tf in "${EXPECTED_TEST_FILES[@]}"; do
  if [ ! -f "/app/$tf" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "INTEGRITY ERROR: Required test file missing: $tf"
    exit 1
  fi
done

set +e
TEST_OUTPUT=$(go test -race -v ./... 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -c -- '--- PASS:' || true)
FAILED=$(echo "$TEST_OUTPUT" | grep -c -- '--- FAIL:' || true)
TOTAL=$((PASSED + FAILED))

if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
  echo "No tests found. Reward: 0.0"
  exit 1
fi

# Anti-reward-hacking: minimum test count guard.
# The suite must have at least 14000 test cases. If tests were deleted or
# skipped to artificially inflate the pass rate, the reward is zeroed.
MIN_TESTS=14000
if [ "$TOTAL" -lt "$MIN_TESTS" ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "INTEGRITY ERROR: Expected at least $MIN_TESTS tests, got $TOTAL. Tests may have been deleted."
  exit 1
fi

# Apply penalty for test file modification
if [ "$TEST_FILES_MODIFIED" -eq 1 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "reason": "test_files_modified"}' > /logs/verifier/results.json
  echo "Reward: 0.0 (test files were modified — fix source files only)"
  exit 0
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
