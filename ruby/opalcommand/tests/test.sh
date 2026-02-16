#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Anti-tampering: verify test file integrity before running
TAMPER_DETECTED=0
declare -A EXPECTED_CHECKSUMS
EXPECTED_CHECKSUMS=(
  ["tests/run_all.rb"]="a232861de7c004d3aebd7dcaa91324bb7adb5cededd037d4e5bc945185249239"
  ["tests/test_helper.rb"]="6ef247f1105796e76ed3a0d180d04d3ceaaa602b8ed8f99c1366adcf0342c039"
  ["tests/stress/hyper_matrix_test.rb"]="53edaad362702a47025d44161c9edd7872da651b7d566ff9f313d94d25ffc891"
  ["tests/stress/advanced_matrix_test.rb"]="a60e305d2a59a3969a719ae17a64db1e0c95226dcaaea64ad9342f3cfd2239ac"
  ["tests/stress/service_mesh_matrix_test.rb"]="de6a9bff16ee899475620d93a0461cf2a3a6d06686258f2932effecd63239dda"
  ["tests/unit/advanced_core_test.rb"]="e5a5b6a0a27745d443d5e183e1c020c6d20cf9b49565c012649693cff8493add"
  ["tests/integration/advanced_integration_test.rb"]="3035fe89ffd584a816c24b1ec57e1b26170b329f4d10bc415429c2d60cb559dc"
)

cd /app 2>/dev/null || true
for file in "${!EXPECTED_CHECKSUMS[@]}"; do
  if [ -f "$file" ]; then
    ACTUAL=$(shasum -a 256 "$file" 2>/dev/null | awk '{print $1}')
    if [ "$ACTUAL" != "${EXPECTED_CHECKSUMS[$file]}" ]; then
      echo "TAMPER DETECTED: $file has been modified"
      TAMPER_DETECTED=1
    fi
  else
    echo "TAMPER DETECTED: $file is missing"
    TAMPER_DETECTED=1
  fi
done

if [ "$TAMPER_DETECTED" -eq 1 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"error": "test file tampering detected"}' > /logs/verifier/results.json
  echo "Reward: 0.0 (test files were modified)"
  exit 1
fi

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
TEST_OUTPUT=$(ruby -Ilib -Itests tests/run_all.rb 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

SUMMARY=$(echo "$TEST_OUTPUT" | grep -E '^[0-9]+ runs, [0-9]+ assertions, [0-9]+ failures, [0-9]+ errors' | tail -1)
RUNS=$(echo "$SUMMARY" | sed -n 's/^\([0-9]\+\) runs.*/\1/p')
FAILURES=$(echo "$SUMMARY" | sed -n 's/.* \([0-9]\+\) failures.*/\1/p')
ERRORS=$(echo "$SUMMARY" | sed -n 's/.* \([0-9]\+\) errors.*/\1/p')

RUNS=${RUNS:-0}
FAILURES=${FAILURES:-0}
ERRORS=${ERRORS:-0}

EXPECTED_MIN_TESTS=10000
if [ "$RUNS" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
  echo "No tests found. Reward: 0.0"
  exit 1
fi

if [ "$RUNS" -lt "$EXPECTED_MIN_TESTS" ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"error": "test count below minimum threshold"}' > /logs/verifier/results.json
  echo "Reward: 0.0 (only $RUNS tests found, expected >= $EXPECTED_MIN_TESTS)"
  exit 1
fi

FAILED=$((FAILURES + ERRORS))
PASSED=$((RUNS - FAILED))
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$RUNS" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$RUNS" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $RUNS)"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
