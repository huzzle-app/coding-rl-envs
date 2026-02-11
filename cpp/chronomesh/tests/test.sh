#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Provision build tools in base images that do not include CMake/GCC.
if ! command -v cmake >/dev/null 2>&1 || ! command -v ctest >/dev/null 2>&1 || ! command -v g++ >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update >/tmp/chronomesh_apt_update.log 2>&1 || true
    apt-get install -y --no-install-recommends cmake g++ make >/tmp/chronomesh_apt_install.log 2>&1 || true
  fi
fi

cmake -B build -DCMAKE_BUILD_TYPE=Debug >/tmp/chronomesh_cmake.log 2>&1 || true
cmake --build build --parallel >/tmp/chronomesh_build.log 2>&1 || true
MATRIX_OUTPUT=$(./build/chronomesh_tests hyper_matrix 2>&1)
MATRIX_STATUS=$?
CTEST_OUTPUT=$(ctest --test-dir build --output-on-failure -E '^hyper_matrix$' 2>&1 || true)
TEST_OUTPUT="$MATRIX_OUTPUT
$CTEST_OUTPUT"

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

MATRIX_SUMMARY=$(echo "$MATRIX_OUTPUT" | grep 'TB_SUMMARY' | tail -1 || true)
MATRIX_TOTAL=$(echo "$MATRIX_SUMMARY" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
MATRIX_FAILED=$(echo "$MATRIX_SUMMARY" | sed -n 's/.*failed=\([0-9]*\).*/\1/p')

CTEST_TOTAL=$(echo "$CTEST_OUTPUT" | sed -n 's/.*tests failed out of \([0-9]\+\).*/\1/p' | tail -1)
CTEST_FAILED=$(echo "$CTEST_OUTPUT" | sed -n 's/.*\([0-9]\+\) tests failed out of.*/\1/p' | tail -1)

if [ -z "$MATRIX_SUMMARY" ]; then
  # Hyper matrix must produce a summary; otherwise count as a verifier failure.
  MATRIX_TOTAL=1
  MATRIX_FAILED=1
fi

MATRIX_TOTAL=${MATRIX_TOTAL:-0}
MATRIX_FAILED=${MATRIX_FAILED:-0}

if [ "$MATRIX_STATUS" -ne 0 ] && [ "$MATRIX_FAILED" -eq 0 ]; then
  MATRIX_FAILED=1
  if [ "$MATRIX_TOTAL" -eq 0 ]; then
    MATRIX_TOTAL=1
  fi
fi
CTEST_TOTAL=${CTEST_TOTAL:-0}
CTEST_FAILED=${CTEST_FAILED:-0}

TOTAL=$((MATRIX_TOTAL + CTEST_TOTAL))
FAILED=$((MATRIX_FAILED + CTEST_FAILED))

TOTAL=${TOTAL:-0}
FAILED=${FAILED:-0}

if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "No tests found. Reward: 0.0"
  exit 0
fi

PASSED=$((TOTAL - FAILED))
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"
