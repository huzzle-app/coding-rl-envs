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

# Build with sanitizers (ASan + UBSan) if possible, fall back to plain Debug
if [ ! -d "build" ]; then
    cmake -B build -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON 2>&1
    if [ $? -ne 0 ]; then
        rm -rf build
        cmake -B build -DCMAKE_BUILD_TYPE=Debug 2>&1 || true
    fi
fi
cmake --build build --parallel 2>&1 || true

set +e
TEST_OUTPUT=$(cd build && ctest --output-on-failure --no-compress-output 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ tests failed out of [0-9]+' | grep -oE '[0-9]+$' || echo 0)
FAILED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ tests failed' | head -1 | grep -oE '[0-9]+' || echo 0)

TOTAL=${TOTAL:-0}
FAILED=${FAILED:-0}

if [ "$TOTAL" -eq 0 ]; then
    PASSED=$(echo "$TEST_OUTPUT" | grep -cE '\.+\s+Passed' || echo 0)
    FAILED=$(echo "$TEST_OUTPUT" | grep -cE '\.+\s+(Failed|Not Run)' || echo 0)
    TOTAL=$((PASSED + FAILED))
fi

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

PASSED=$((TOTAL - FAILED))

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
echo "Reward: $REWARD"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
