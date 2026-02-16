#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Workspace detection: prefer /app, fall back to script directory's parent
if [ -d "/app/tests" ] && [ -f "/app/Cargo.toml" ]; then
  WORKSPACE="/app"
elif [ -n "${APP_DIR:-}" ] && [ -d "$APP_DIR/tests" ]; then
  WORKSPACE="$APP_DIR"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  WORKSPACE="$(dirname "$SCRIPT_DIR")"
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

# Anti-tampering: verify test files, Cargo.toml, and environment files have not been modified
EXPECTED_HASH="f53762011c40861a50f7243023629e0b9fb28b55c5e4f30151bbc24e0799e056"
CARGO_HASH="b283bf5dc63f26ae4281625147f54f321ea35e9265f6a686716f8bfe644c88a6"
SCORING_HASH="500b6d64dbb0ba4af23326f13a54fcfd0c651581a1ee92edefcd14cdba46e217"
REWARD_HASH="69fed8196888487ee375f23a2e9ebf639512c4c2efdb8c73185b8b5384828b7b"
if command -v sha256sum >/dev/null 2>&1; then
  SHA_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  SHA_CMD="shasum -a 256"
else
  SHA_CMD=""
fi

if [ -n "$SHA_CMD" ]; then
  ACTUAL_HASH=$(cat "$WORKSPACE/tests/core_tests.rs" "$WORKSPACE/tests/advanced_tests.rs" "$WORKSPACE/tests/extended_tests.rs" "$WORKSPACE/tests/contracts_tests.rs" "$WORKSPACE/tests/chaos_tests.rs" "$WORKSPACE/tests/flow_tests.rs" "$WORKSPACE/tests/hyper_matrix.rs" 2>/dev/null | $SHA_CMD | awk '{print $1}')
  ACTUAL_CARGO=$(cat "$WORKSPACE/Cargo.toml" 2>/dev/null | $SHA_CMD | awk '{print $1}')
  ACTUAL_SCORING=$(cat "$WORKSPACE/environment/scoring.py" 2>/dev/null | $SHA_CMD | awk '{print $1}')
  ACTUAL_REWARD=$(cat "$WORKSPACE/environment/reward.py" 2>/dev/null | $SHA_CMD | awk '{print $1}')
  if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: test files modified. Reward: 0.0"
    exit 1
  fi
  if [ "$ACTUAL_CARGO" != "$CARGO_HASH" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: Cargo.toml modified. Reward: 0.0"
    exit 1
  fi
  if [ "$ACTUAL_SCORING" != "$SCORING_HASH" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: scoring.py modified. Reward: 0.0"
    exit 1
  fi
  if [ "$ACTUAL_REWARD" != "$REWARD_HASH" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: reward.py modified. Reward: 0.0"
    exit 1
  fi
fi

# Backup check: git diff on protected files
if command -v git >/dev/null 2>&1; then
  PROTECTED_DIFF=$(cd "$WORKSPACE" && git diff --name-only HEAD -- tests/ Cargo.toml environment/ 2>/dev/null || true)
  if [ -n "$PROTECTED_DIFF" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: protected files changed ($PROTECTED_DIFF). Reward: 0.0"
    exit 1
  fi
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
  # Sanity: matrix must report 12500 total and cargo test result must exist
  MATRIX_HAS_RESULT=$(echo "$MATRIX_OUTPUT" | grep -c 'test result:' || true)
  if [ "${MATRIX_TOTAL:-0}" -ne 12500 ] || [ "${MATRIX_HAS_RESULT:-0}" -lt 1 ]; then
    MATRIX_TOTAL=12500
    MATRIX_PASSED=0
    MATRIX_FAILED=12500
  fi
else
  # Hyper matrix did not emit a summary: treat as all-fail to avoid false positives.
  MATRIX_TOTAL=12500
  MATRIX_PASSED=0
  MATRIX_FAILED=12500
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

# Parse per-module detail from hyper matrix
DETAIL_LINE=$(echo "$MATRIX_OUTPUT" | grep 'TB_DETAIL' | tail -1 || true)
MODULE_DATA_ARG=""
if [ -n "$DETAIL_LINE" ]; then
  # Convert TB_DETAIL line to JSON: "config=0/893 concurrency=5/893 ..." -> {"config":{"passed":0,"total":893},...}
  MODULE_JSON=$(echo "$DETAIL_LINE" | sed 's/^TB_DETAIL //' | awk '{
    printf "{"
    for (i=1; i<=NF; i++) {
      split($i, a, "=")
      split(a[2], b, "/")
      if (i > 1) printf ","
      printf "\"%s\":{\"passed\":%s,\"total\":%s}", a[1], b[1], b[2]
    }
    printf "}"
  }')
  if [ -n "$MODULE_JSON" ] && [ "$MODULE_JSON" != "{}" ]; then
    MODULE_DATA_ARG="--module-data $MODULE_JSON"
  fi
fi

# Use local scoring module with multi-solution bonus
REWARD=$(python3 "$WORKSPACE/environment/scoring.py" --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd "$WORKSPACE" $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 "$WORKSPACE/environment/scoring.py" --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd "$WORKSPACE" $TRAINING_MODE_ARG $PREV_PASSED_ARG $MODULE_DATA_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $FAILED failed (total: $TOTAL)"

# Show per-module breakdown if available
if [ -n "$DETAIL_LINE" ]; then
  echo "Module breakdown:"
  echo "$DETAIL_LINE" | sed 's/^TB_DETAIL //' | tr ' ' '\n' | while IFS='=' read -r mod counts; do
    passed_n=$(echo "$counts" | cut -d'/' -f1)
    total_n=$(echo "$counts" | cut -d'/' -f2)
    if [ "$passed_n" -eq "$total_n" ] 2>/dev/null; then
      status="PASS"
    elif [ "$passed_n" -gt 0 ] 2>/dev/null; then
      status="PARTIAL"
    else
      status="FAIL"
    fi
    echo "  $mod: $counts ($status)"
  done
fi

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
