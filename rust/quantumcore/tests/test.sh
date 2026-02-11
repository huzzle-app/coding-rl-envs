#!/bin/bash
# Harbor verifier script for QuantumCore (Rust/cargo test)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

TEST_OUTPUT=$(cargo test --workspace 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse cargo test summary: "test result: ok. X passed; Y failed; Z ignored"
# There may be multiple test result lines (one per test binary), sum them
TOTAL_PASSED=0
TOTAL_FAILED=0

while IFS= read -r line; do
    P=$(echo "$line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
    F=$(echo "$line" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)
    TOTAL_PASSED=$((TOTAL_PASSED + P))
    TOTAL_FAILED=$((TOTAL_FAILED + F))
done < <(echo "$TEST_OUTPUT" | grep 'test result:')

TOTAL=$((TOTAL_PASSED + TOTAL_FAILED))

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found. Reward: 0.0"
    exit 0
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $TOTAL_PASSED / $TOTAL}")

# 8-threshold sparse reward (Principal difficulty)
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $TOTAL_PASSED passed, $TOTAL_FAILED failed (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
