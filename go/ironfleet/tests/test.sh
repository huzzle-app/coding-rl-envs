#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# ──────────────────────────────────────────────────────────────────────────────
# Anti-reward-hacking: verify test suite integrity before running
# ──────────────────────────────────────────────────────────────────────────────
EXPECTED_TEST_FILES=(
  "tests/unit/core_test.go"
  "tests/integration/flow_test.go"
  "tests/chaos/replay_test.go"
  "tests/services/contracts_test.go"
  "tests/services/gateway_service_test.go"
  "tests/services/audit_service_test.go"
  "tests/services/analytics_service_test.go"
  "tests/services/notifications_service_test.go"
  "tests/services/policy_service_test.go"
  "tests/services/resilience_service_test.go"
  "tests/services/routing_service_test.go"
  "tests/services/security_service_test.go"
  "tests/stress/hyper_matrix_test.go"
  "tests/stress/service_mesh_matrix_test.go"
  "tests/stress/advanced_bugs_test.go"
)

INTEGRITY_FAIL=0
for tf in "${EXPECTED_TEST_FILES[@]}"; do
  if [ ! -f "/app/$tf" ]; then
    echo "INTEGRITY ERROR: test file $tf missing or deleted"
    INTEGRITY_FAIL=1
  fi
done

# Verify scoring module not tampered
if [ ! -f "/app/environment/scoring.py" ]; then
  echo "INTEGRITY ERROR: scoring.py missing"
  INTEGRITY_FAIL=1
fi
if [ ! -f "/app/environment/reward.go" ]; then
  echo "INTEGRITY ERROR: reward.go missing"
  INTEGRITY_FAIL=1
fi

# Check test files haven't been truncated (min size check)
for tf in "${EXPECTED_TEST_FILES[@]}"; do
  if [ -f "/app/$tf" ]; then
    SIZE=$(wc -c < "/app/$tf" | tr -d ' ')
    if [ "$SIZE" -lt 200 ]; then
      echo "INTEGRITY ERROR: $tf appears truncated (${SIZE} bytes)"
      INTEGRITY_FAIL=1
    fi
  fi
done

if [ "$INTEGRITY_FAIL" -eq 1 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "integrity_check_failed"}' > /logs/verifier/results.json
  echo "Reward hacking detected. Reward: 0.0"
  exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
# ──────────────────────────────────────────────────────────────────────────────
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
TEST_OUTPUT=$(go test -race -v ./... 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

PASSED=$(echo "$TEST_OUTPUT" | grep -c -- '--- PASS:' || true)
FAILED=$(echo "$TEST_OUTPUT" | grep -c -- '--- FAIL:' || true)
TOTAL=$((PASSED + FAILED))

# ──────────────────────────────────────────────────────────────────────────────
# Anti-reward-hacking: verify minimum test count
# The full suite should produce at least 9000 test results.
# If significantly fewer tests ran, tests may have been deleted or skipped.
# ──────────────────────────────────────────────────────────────────────────────
MIN_EXPECTED_TESTS=9000
if [ "$TOTAL" -gt 0 ] && [ "$TOTAL" -lt "$MIN_EXPECTED_TESTS" ]; then
  echo "WARNING: Only $TOTAL tests ran (expected >= $MIN_EXPECTED_TESTS). Possible test deletion."
  echo "0.0" > /logs/verifier/reward.txt
  echo "{\"reward\": 0.0, \"error\": \"insufficient_tests\", \"total\": $TOTAL}" > /logs/verifier/results.json
  echo "Reward: 0.0 (insufficient test count)"
  exit 1
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

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

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
