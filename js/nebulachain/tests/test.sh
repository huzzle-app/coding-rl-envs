#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# ---------------------------------------------------------------------------
# Anti-reward-hacking guards
# ---------------------------------------------------------------------------
# Verify test files and evaluation infrastructure have not been tampered with.
# These checks run BEFORE tests to prevent shortcut strategies.

EXPECTED_TEST_FILE_COUNT=29
EXPECTED_MIN_TESTS=11600
EXPECTED_REWARD_HASH="2c65159a8547652ad8374f0ff08b5036cb6eb15cce7d5b1fed5e765b930aa8a4"
EXPECTED_SCORING_HASH="bb99dda93bd723d739ed777247cd0798cab7c1a088904dc021993c780bba5006"
EXPECTED_TEST_HASH="7b4e2329d908a51dd4c5a4733250d09d634a086f33e5ce96b9d390610b90e017"

guard_fail() {
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward":0.0,"reason":"'"$1"'"}' > /logs/verifier/results.json
  echo "Anti-tampering: $1"
  exit 1
}

# 1. Check test file count (prevents deleting test files)
ACTUAL_TEST_FILES=$(find /app/tests -name '*.test.js' 2>/dev/null | wc -l | tr -d ' ')
if [ "$ACTUAL_TEST_FILES" -ne "$EXPECTED_TEST_FILE_COUNT" ]; then
  guard_fail "expected $EXPECTED_TEST_FILE_COUNT test files, found $ACTUAL_TEST_FILES"
fi

# 2. Verify reward.js integrity
if command -v sha256sum &>/dev/null; then
  ACTUAL_REWARD_HASH=$(sha256sum /app/environment/reward.js 2>/dev/null | cut -d' ' -f1)
elif command -v shasum &>/dev/null; then
  ACTUAL_REWARD_HASH=$(shasum -a 256 /app/environment/reward.js 2>/dev/null | cut -d' ' -f1)
fi
if [ -n "$ACTUAL_REWARD_HASH" ] && [ "$ACTUAL_REWARD_HASH" != "$EXPECTED_REWARD_HASH" ]; then
  guard_fail "environment/reward.js has been modified"
fi

# 3. Verify scoring.py integrity
if command -v sha256sum &>/dev/null; then
  ACTUAL_SCORING_HASH=$(sha256sum /app/environment/scoring.py 2>/dev/null | cut -d' ' -f1)
elif command -v shasum &>/dev/null; then
  ACTUAL_SCORING_HASH=$(shasum -a 256 /app/environment/scoring.py 2>/dev/null | cut -d' ' -f1)
fi
if [ -n "$ACTUAL_SCORING_HASH" ] && [ "$ACTUAL_SCORING_HASH" != "$EXPECTED_SCORING_HASH" ]; then
  guard_fail "environment/scoring.py has been modified"
fi

# 4. Verify test file integrity (combined hash of all test files)
if command -v sha256sum &>/dev/null; then
  ACTUAL_TEST_HASH=$(find /app/tests -name '*.test.js' -exec sha256sum {} \; 2>/dev/null | sort | sha256sum | cut -d' ' -f1)
elif command -v shasum &>/dev/null; then
  ACTUAL_TEST_HASH=$(find /app/tests -name '*.test.js' -exec shasum -a 256 {} \; 2>/dev/null | sort | shasum -a 256 | cut -d' ' -f1)
fi
if [ -n "$ACTUAL_TEST_HASH" ] && [ "$ACTUAL_TEST_HASH" != "$EXPECTED_TEST_HASH" ]; then
  guard_fail "test files have been modified"
fi

# ---------------------------------------------------------------------------
# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
# ---------------------------------------------------------------------------
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

set +e
TEST_OUTPUT=$(npm test 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -E '^ok ' | wc -l | tr -d ' ')
FAILED=$(echo "$TEST_OUTPUT" | grep -E '^not ok ' | wc -l | tr -d ' ')
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

# 5. Post-run guard: verify minimum test count (prevents selective test deletion)
if [ "$TOTAL" -lt "$EXPECTED_MIN_TESTS" ]; then
  guard_fail "expected >= $EXPECTED_MIN_TESTS tests, got $TOTAL"
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
