#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward: auto-persist prev_passed between runs for multi-step RL.
# Can also be set via PREV_PASSED env var to override.
PREV_PASSED_FILE="/logs/verifier/prev_passed.txt"
PREV_PASSED_ARG=""
if [ -n "$PREV_PASSED" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
elif [ -f "$PREV_PASSED_FILE" ]; then
  STORED_PREV=$(cat "$PREV_PASSED_FILE" 2>/dev/null | tr -d '[:space:]')
  if [ -n "$STORED_PREV" ] && [ "$STORED_PREV" -eq "$STORED_PREV" ] 2>/dev/null; then
    PREV_PASSED_ARG="--prev-passed $STORED_PREV"
  fi
fi

# Provision build tools in base images that do not include CMake/GCC.
if ! command -v cmake >/dev/null 2>&1 || ! command -v ctest >/dev/null 2>&1 || ! command -v g++ >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update >/tmp/obsidianmesh_apt_update.log 2>&1 || true
    apt-get install -y --no-install-recommends cmake g++ make >/tmp/obsidianmesh_apt_install.log 2>&1 || true
  fi
fi

cmake -B build -DCMAKE_BUILD_TYPE=Debug >/tmp/obsidianmesh_cmake.log 2>&1 || true
cmake --build build --parallel >/tmp/obsidianmesh_build.log 2>&1 || true
MATRIX_OUTPUT=$(./build/obsidianmesh_tests hyper_matrix 2>&1)
MATRIX_STATUS=$?
CTEST_OUTPUT=$(ctest --test-dir build --output-on-failure -E '^hyper_matrix$' 2>&1 || true)
TEST_OUTPUT="$MATRIX_OUTPUT
$CTEST_OUTPUT"

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

MATRIX_SUMMARY=$(echo "$MATRIX_OUTPUT" | grep 'TB_SUMMARY' | tail -1 || true)
MATRIX_TOTAL=$(echo "$MATRIX_SUMMARY" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
MATRIX_FAILED=$(echo "$MATRIX_SUMMARY" | sed -n 's/.*failed=\([0-9]*\).*/\1/p')

CTEST_TOTAL=$(echo "$CTEST_OUTPUT" | sed -n 's/.*tests failed out of \([0-9]\+\).*/\1/p' | tail -1)
CTEST_FAILED=$(echo "$CTEST_OUTPUT" | sed -n 's/.*[^0-9]\([0-9][0-9]*\) tests failed out of.*/\1/p' | tail -1)
if [ -z "$CTEST_FAILED" ]; then
  CTEST_FAILED=$(echo "$CTEST_OUTPUT" | sed -n 's/^\([0-9][0-9]*\) tests failed out of.*/\1/p' | tail -1)
fi

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

# --- Regression detection ---
# Compare currently-passing base tests against the shipped baseline.
# If the agent broke previously-passing tests, apply a penalty multiplier.
BASELINE_FILE="/app/tests/baseline_passing.txt"
REGRESSIONS=0
REGRESSION_NAMES=""
if [ -f "$BASELINE_FILE" ]; then
  # Extract currently-passing test names from ctest output
  CURRENT_PASSING=$(echo "$CTEST_OUTPUT" | grep 'Passed' | sed 's/.*Test[ ]*#[0-9]*:[ ]*//' | sed 's/[ ]*\.\..*$//' | sort)

  while IFS= read -r test_name; do
    # Skip comments and blank lines
    case "$test_name" in \#*|"") continue ;; esac
    if ! echo "$CURRENT_PASSING" | grep -qx "$test_name"; then
      REGRESSIONS=$((REGRESSIONS + 1))
      REGRESSION_NAMES="$REGRESSION_NAMES $test_name"
    fi
  done < "$BASELINE_FILE"
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")

# Apply regression penalty: each regressed baseline test reduces reward by 1%.
# This ensures agents that break existing functionality are penalized even if
# they fix more tests than they break (net positive pass count).
if [ "$REGRESSIONS" -gt 0 ]; then
  PENALTY_PCT=$((REGRESSIONS > 100 ? 100 : REGRESSIONS))
  REWARD=$(python3 -c "print(round(max(0.0, $REWARD * (1.0 - $PENALTY_PCT / 100.0)), 4))" 2>/dev/null || echo "0.0")
  echo "WARNING: $REGRESSIONS baseline test(s) regressed:$REGRESSION_NAMES" >> /logs/verifier/test_output.txt
fi

echo "$REWARD" > /logs/verifier/reward.txt

# Persist current pass count for incremental tracking on next run
echo "$PASSED" > "$PREV_PASSED_FILE"

# Show progress info
if [ -n "$PREV_PASSED_ARG" ]; then
  PREV_VAL=$(echo "$PREV_PASSED_ARG" | awk '{print $2}')
  DELTA=$((PASSED - PREV_VAL))
  if [ "$DELTA" -gt 0 ]; then
    echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL), regressions: $REGRESSIONS [+$DELTA new]"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL), regressions: $REGRESSIONS [$DELTA regressed]"
  else
    echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL), regressions: $REGRESSIONS [no change]"
  fi
else
  echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL), regressions: $REGRESSIONS"
fi
