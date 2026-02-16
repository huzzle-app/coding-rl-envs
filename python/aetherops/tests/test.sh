#!/bin/bash
# Harbor verifier script for AetherOps (Python/unittest)
# Runs the test suite, computes sparse reward, writes to /logs/verifier/reward.txt
set -o pipefail
mkdir -p /logs/verifier

# ============================================================================
# Environment Variables for Training:
#   TRAINING_MODE  - Enable dense rewards: linear, sublinear, smooth
#   PREV_PASSED    - Previous passed count for incremental rewards
#   PARSE_ERRORS   - Output structured errors (set to "1" to enable)
# ============================================================================

# Training mode support
TRAINING_MODE_ARG=""
if [ -n "${TRAINING_MODE:-}" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "${PREV_PASSED:-}" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

# Run the unified test runner (unittest-based) and capture output
set +e
TEST_OUTPUT=$(cd /app && python tests/run_all.py 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# ============================================================================
# Anti-reward-hacking: verify test file integrity
# ============================================================================
EXPECTED_TEST_FILES=31
ACTUAL_TEST_FILES=$(find /app/tests -name '*_test.py' -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$ACTUAL_TEST_FILES" -lt "$EXPECTED_TEST_FILES" ]; then
    echo "INTEGRITY FAILURE: Expected at least $EXPECTED_TEST_FILES test files, found $ACTUAL_TEST_FILES"
    echo "0.0" > /logs/verifier/reward.txt
    echo '{"passed": 0, "failed": 0, "total": 0, "reward": 0.0, "error": "test file integrity check failed"}' > /logs/verifier/results.json
    exit 1
fi

# Verify TB_SUMMARY line present in output
if echo "$TEST_OUTPUT" | grep -q "TB_SUMMARY"; then
    : # Summary line present, good
else
    echo "INTEGRITY FAILURE: TB_SUMMARY line missing from test output"
    echo "0.0" > /logs/verifier/reward.txt
    echo '{"passed": 0, "failed": 0, "total": 0, "reward": 0.0, "error": "test runner integrity check failed"}' > /logs/verifier/results.json
    exit 1
fi

# Parse TB_SUMMARY line: "TB_SUMMARY total=X passed=Y failed=Z errors=W"
PASSED=$(echo "$TEST_OUTPUT" | grep -oP 'TB_SUMMARY.*passed=\K[0-9]+' || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oP 'TB_SUMMARY.*failed=\K[0-9]+' || echo 0)
ERRORS=$(echo "$TEST_OUTPUT" | grep -oP 'TB_SUMMARY.*errors=\K[0-9]+' || echo 0)

PASSED=${PASSED:-0}
FAILED=${FAILED:-0}
ERRORS=${ERRORS:-0}

TOTAL=$((PASSED + FAILED + ERRORS))

# Anti-reward-hacking: minimum test count threshold
MIN_EXPECTED_TESTS=7000
if [ "$TOTAL" -gt 0 ] && [ "$TOTAL" -lt "$MIN_EXPECTED_TESTS" ]; then
    echo "INTEGRITY FAILURE: Expected at least $MIN_EXPECTED_TESTS tests, only $TOTAL found"
    echo "0.0" > /logs/verifier/reward.txt
    echo "{\"passed\": $PASSED, \"failed\": $FAILED, \"total\": $TOTAL, \"reward\": 0.0, \"error\": \"test count below minimum threshold\"}" > /logs/verifier/results.json
    exit 1
fi

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo '{"passed": 0, "failed": 0, "total": 0, "reward": 0.0}' > /logs/verifier/results.json
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found or all tests skipped. Reward: 0.0"
    exit 1
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Calculate reward using scoring module (8-threshold, Hyper-Principal)
REWARD=""
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")

# Get full JSON results
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json

# Parse and output structured errors if requested
if [ "${PARSE_ERRORS:-}" = "1" ] && [ "$FAILED" -gt 0 ]; then
  python3 /app/environment/scoring.py --parse-errors /logs/verifier/test_output.txt --language python > /logs/verifier/errors.json 2>/dev/null || true
fi

echo "Tests: $PASSED passed, $FAILED failed, $ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"

# Show incremental info if available
if [ -n "${PREV_PASSED:-}" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
