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

BASE_OUTPUT=$(cargo test --no-fail-fast -- --skip hyper_matrix_scenarios 2>&1 || true)
MATRIX_OUTPUT=$(cargo test --test hyper_matrix -- --nocapture 2>&1 || true)
TEST_OUTPUT="$BASE_OUTPUT
$MATRIX_OUTPUT"
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

BASE_PASSED=$(echo "$BASE_OUTPUT" | grep -oE '[0-9]+ passed;' | awk '{s+=$1} END {print s+0}')
BASE_FAILED=$(echo "$BASE_OUTPUT" | grep -oE '[0-9]+ failed;' | awk '{s+=$1} END {print s+0}')

SUMMARY=$(echo "$MATRIX_OUTPUT" | grep 'TB_SUMMARY' | tail -1 || true)
if [ -n "$SUMMARY" ]; then
  MATRIX_TOTAL=$(echo "$SUMMARY" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
  MATRIX_PASSED=$(echo "$SUMMARY" | sed -n 's/.*passed=\([0-9]*\).*/\1/p')
  MATRIX_FAILED=$(echo "$SUMMARY" | sed -n 's/.*failed=\([0-9]*\).*/\1/p')
else
  MATRIX_TOTAL=1
  MATRIX_PASSED=0
  MATRIX_FAILED=1
fi

BASE_PASSED=${BASE_PASSED:-0}
BASE_FAILED=${BASE_FAILED:-0}
MATRIX_TOTAL=${MATRIX_TOTAL:-0}
MATRIX_PASSED=${MATRIX_PASSED:-0}
MATRIX_FAILED=${MATRIX_FAILED:-0}

TOTAL=$((BASE_PASSED + BASE_FAILED + MATRIX_TOTAL))
PASSED=$((BASE_PASSED + MATRIX_PASSED))
FAILED=$((BASE_FAILED + MATRIX_FAILED))

if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "No tests found. Reward: 0.0"
  exit 1
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

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
