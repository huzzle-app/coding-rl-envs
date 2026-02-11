#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(mvn -q test 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL=0
FAILED=0
ERRORS=0
SKIPPED=0
for xml in $(find . -path '*/surefire-reports/TEST-*.xml' 2>/dev/null); do
  T=$(grep -oE 'tests="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
  F=$(grep -oE 'failures="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
  E=$(grep -oE 'errors="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
  S=$(grep -oE 'skipped="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
  TOTAL=$((TOTAL + T))
  FAILED=$((FAILED + F))
  ERRORS=$((ERRORS + E))
  SKIPPED=$((SKIPPED + S))
done

if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "No tests found. Reward: 0.0"
  exit 0
fi

PASSED=$((TOTAL - FAILED - ERRORS - SKIPPED))
EFFECTIVE_TOTAL=$((TOTAL - SKIPPED))
if [ "$EFFECTIVE_TOTAL" -le 0 ]; then
  EFFECTIVE_TOTAL=$TOTAL
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed, $ERRORS errors (total: $EFFECTIVE_TOTAL)"
