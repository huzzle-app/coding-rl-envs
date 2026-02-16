#!/bin/bash
# Harbor verifier script for CollabCanvas (JavaScript/Jest)
set -o pipefail
mkdir -p /logs/verifier

# ── Anti-reward-hacking guards ───────────────────────────────────────
# Minimum expected test file count and total tests.
# An agent that deletes tests or test files to inflate pass rate will be caught.
MIN_TEST_FILES=22
MIN_TOTAL_TESTS=256

TEST_FILE_COUNT=$(find tests -name "*.test.js" 2>/dev/null | wc -l | tr -d ' ')
if [ "$TEST_FILE_COUNT" -lt "$MIN_TEST_FILES" ]; then
  echo "INTEGRITY ERROR: Expected >= $MIN_TEST_FILES test files, found $TEST_FILE_COUNT."
  echo "Test files must not be deleted."
  echo "0.0" > /logs/verifier/reward.txt
  exit 1
fi

# Verify critical test files exist (not deleted)
CRITICAL_FILES=(
  "tests/unit/services/crdt.service.test.js"
  "tests/unit/services/sync.service.test.js"
  "tests/unit/services/jwt.service.test.js"
  "tests/security/auth.security.test.js"
  "tests/security/upload.security.test.js"
  "tests/system/collaboration.system.test.js"
  "tests/integration/websocket/presence.integration.test.js"
  "tests/unit/models/element.model.test.js"
  "tests/unit/models/board.model.test.js"
)
for crit in "${CRITICAL_FILES[@]}"; do
  if [ ! -f "$crit" ]; then
    echo "INTEGRITY ERROR: Critical test file missing: $crit"
    echo "0.0" > /logs/verifier/reward.txt
    exit 1
  fi
done
# ─────────────────────────────────────────────────────────────────────

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# ── Incremental reward / prev_passed tracking ────────────────────────
PREV_PASSED_FILE="/logs/verifier/prev_passed.txt"

# Load prev_passed from file if env var is not set
if [ -z "$PREV_PASSED" ] && [ -f "$PREV_PASSED_FILE" ]; then
  PREV_PASSED=$(cat "$PREV_PASSED_FILE" 2>/dev/null | tr -d '[:space:]')
fi

PREV_PASSED_ARG=""
if [ -n "$PREV_PASSED" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi
# ─────────────────────────────────────────────────────────────────────

set +e
TEST_OUTPUT=$(npx jest --ci --no-color 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Jest "Tests:" summary line: "Tests: X failed, Y passed, Z total"
PASSED=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ total' | grep -oE '[0-9]+' || echo 0)

PASSED=${PASSED:-0}
TOTAL=${TOTAL:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found or all tests skipped. Reward: 0.0"
    exit 1
fi

# ── Anti-reward-hacking: minimum total test count ────────────────────
if [ "$TOTAL" -lt "$MIN_TOTAL_TESTS" ]; then
  echo "INTEGRITY ERROR: Expected >= $MIN_TOTAL_TESTS tests, found $TOTAL."
  echo "Tests must not be removed or skipped."
  echo "0.0" > /logs/verifier/reward.txt
  exit 1
fi
# ─────────────────────────────────────────────────────────────────────

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward function for Senior environment
# Thresholds: [0.50, 0.75, 0.90, 1.0]
# Rewards:    [0.15, 0.35, 0.65, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed out of $TOTAL total"
echo "Pass ratio: $RATIO | Reward: $REWARD"

# ── Persist prev_passed for next run ─────────────────────────────────
echo "$PASSED" > "$PREV_PASSED_FILE"
# ─────────────────────────────────────────────────────────────────────

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
