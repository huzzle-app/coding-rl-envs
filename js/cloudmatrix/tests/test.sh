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

# ──────────────────────────────────────────────
# Anti-reward-hacking: verify test file integrity
# ──────────────────────────────────────────────
EXPECTED_TEST_HASH="2c0ee6fcd8df2290a7b7d94c47b43d20fa7db00ee2ea14964681f463cc5025e2"
ACTUAL_TEST_HASH=$(find /app/tests -name '*.test.js' -o -name 'setup.js' | sort | xargs cat 2>/dev/null | sha256sum | awk '{print $1}')

if [ -n "$EXPECTED_TEST_HASH" ] && [ "$EXPECTED_TEST_HASH" != "__TESTS_HASH__" ] && [ "$ACTUAL_TEST_HASH" != "$EXPECTED_TEST_HASH" ]; then
  echo "INTEGRITY VIOLATION: Test files have been modified."
  echo "Expected hash: $EXPECTED_TEST_HASH"
  echo "Actual hash:   $ACTUAL_TEST_HASH"
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "test_file_tampering"}' > /logs/verifier/results.json
  exit 1
fi

# Verify environment/scoring files are intact
ENV_EXPECTED_HASH="b9b2801aa41aec4f1b8c3135b09a78cd22add63b9ea8d1106a4937ed0d51fce0"
ENV_ACTUAL_HASH=$(cat /app/environment/scoring.py /app/environment/reward.js 2>/dev/null | sha256sum | awk '{print $1}')

if [ -n "$ENV_EXPECTED_HASH" ] && [ "$ENV_EXPECTED_HASH" != "__ENV_HASH__" ] && [ "$ENV_ACTUAL_HASH" != "$ENV_EXPECTED_HASH" ]; then
  echo "INTEGRITY VIOLATION: Environment files have been modified."
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "environment_file_tampering"}' > /logs/verifier/results.json
  exit 1
fi

# Verify jest config hasn't been tampered to skip tests
JEST_CONFIG=$(cat /app/jest.config.js 2>/dev/null)
if echo "$JEST_CONFIG" | grep -qE 'testPathIgnorePatterns|modulePathIgnorePatterns.*tests|coverageOnly|bail.*true|--skip|testMatch.*\[\]'; then
  echo "INTEGRITY VIOLATION: Jest config tampered to skip tests."
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "jest_config_tampering"}' > /logs/verifier/results.json
  exit 1
fi

# Verify minimum test file count (prevents deletion of test files)
TEST_FILE_COUNT=$(find /app/tests -name '*.test.js' | wc -l)
if [ "$TEST_FILE_COUNT" -lt 25 ]; then
  echo "INTEGRITY VIOLATION: Expected at least 25 test files, found $TEST_FILE_COUNT."
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "test_files_deleted"}' > /logs/verifier/results.json
  exit 1
fi

# ──────────────────────────────────────────────
# Run Jest test suite
# ──────────────────────────────────────────────
set +e
TEST_OUTPUT=$(npx jest --ci --no-color 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Jest output for test results
# Jest summary format: "Tests: X failed, Y passed, Z total"
PASSED=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ total' | grep -oE '[0-9]+' || echo 0)

# Ensure defaults if parsing fails
PASSED=${PASSED:-0}
TOTAL=${TOTAL:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

# ──────────────────────────────────────────────
# Anti-reward-hacking: validate test count sanity
# Tests should not drop significantly (agent deleting test expectations)
# ──────────────────────────────────────────────
MIN_EXPECTED_TESTS=700
if [ "$TOTAL" -lt "$MIN_EXPECTED_TESTS" ]; then
  echo "WARNING: Suspiciously low test count ($TOTAL < $MIN_EXPECTED_TESTS). Possible test deletion or skipping."
  echo "0.0" > /logs/verifier/reward.txt
  echo "{\"reward\": 0.0, \"error\": \"suspiciously_low_test_count\", \"total\": $TOTAL}" > /logs/verifier/results.json
  exit 1
fi

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Apply 8-threshold reward function (Distinguished environment)
# Thresholds: [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
# Rewards:    [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "distinguished" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "distinguished" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

# Write reward to file
echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json

# Display results
echo "Tests: $PASSED passed out of $TOTAL total"
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
