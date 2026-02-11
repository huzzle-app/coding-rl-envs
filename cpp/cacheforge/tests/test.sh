#!/bin/bash
# Harbor verifier script for CacheForge (C++/CTest)
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Build first if needed
if [ ! -d "build" ]; then
    cmake -B build -DCMAKE_BUILD_TYPE=Debug 2>&1 || true
fi
cmake --build build --parallel 2>&1 || true

# Run CTest and capture output
TEST_OUTPUT=$(cd build && ctest --output-on-failure --no-compress-output 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse CTest summary: "X% tests passed, Y tests failed out of Z"
# or "X tests passed, Y tests failed out of Z"
TOTAL=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ tests failed out of [0-9]+' | grep -oE '[0-9]+$' | head -1 || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ tests failed' | head -1 | grep -oE '[0-9]+' || echo 0)

TOTAL=${TOTAL:-0}
FAILED=${FAILED:-0}

# Fallback: count individual test results if summary not found
if [ "$TOTAL" -eq 0 ]; then
    PASSED=$(echo "$TEST_OUTPUT" | grep -cE 'Test\s+#[0-9]+:.*\.+\s+Passed' || echo 0)
    FAILED=$(echo "$TEST_OUTPUT" | grep -cE 'Test\s+#[0-9]+:.*\.+\s+(Failed|Not Run|\*\*\*Failed)' || echo 0)
    TOTAL=$((PASSED + FAILED))
fi

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "No tests found or build failed. Reward: 0.0"
    exit 0
fi

PASSED=$((TOTAL - FAILED))

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 5-threshold sparse reward for Senior environment
# Thresholds: [0.25, 0.50, 0.75, 0.90, 1.0]
# Rewards:    [0.0,  0.15, 0.35, 0.65, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "senior" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
