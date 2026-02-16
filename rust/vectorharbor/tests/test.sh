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

# --- Anti-tampering: verify test file integrity ---
TAMPERED=0
verify_checksum() {
  local file="$1" expected="$2"
  if [ ! -f "$file" ]; then
    echo "TAMPERING DETECTED: $file is missing"
    TAMPERED=1
    return
  fi
  actual=$(shasum -a 256 "$file" 2>/dev/null | awk '{print $1}')
  if [ -z "$actual" ]; then
    actual=$(sha256sum "$file" 2>/dev/null | awk '{print $1}')
  fi
  if [ "$actual" != "$expected" ]; then
    echo "TAMPERING DETECTED: $file has been modified (expected $expected, got $actual)"
    TAMPERED=1
  fi
}

verify_checksum "tests/core_tests.rs"      "d647673b676e961d5b755a1f1cf0e6d37dd4fb62f39f8d4a6f1d3ce58759aa19"
verify_checksum "tests/advanced_tests.rs"   "f88dcc8c60bde24af5906d341ba81d6af33fa8180f6f369788e0594347e87afa"
verify_checksum "tests/extended_tests.rs"   "c9f65848a8810632b25c2fcd4fc3c3fe6de9a26beac677ffa4cf081f01750959"
verify_checksum "tests/chaos_tests.rs"      "896db663bd13716bf0d9be0208b488e94f2b9eb6285d1fa4d832fc30afab1dc1"
verify_checksum "tests/contracts_tests.rs"  "52cd62e887c3fae5db8b382425bd2412f4eb7fd328b34ea37746ff62a9097ac1"
verify_checksum "tests/flow_tests.rs"       "b716c20f4a6131fbde7f9df785c639a3f1f418b371a6082141f0e4c4ce5f8163"
verify_checksum "tests/hyper_matrix.rs"     "630d2ad0bf6cf3501fabb5ed857883e8fb981acd0ab7801cec3546052d48019c"

if [ "$TAMPERED" -eq 1 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "test file tampering detected"}' > /logs/verifier/results.json
  echo "FAILED: Test files have been tampered with. Reward: 0.0"
  exit 1
fi

# --- Run tests ---
# --no-fail-fast ensures ALL test binaries run even if one fails,
# so we get accurate pass/fail counts across all test suites.
BASE_OUTPUT=$(cargo test --no-fail-fast -- --skip hyper_matrix_ 2>&1 || true)
MATRIX_OUTPUT=$(cargo test --test hyper_matrix -- --nocapture 2>&1 || true)
TEST_OUTPUT="$BASE_OUTPUT
$MATRIX_OUTPUT"
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

BASE_PASSED=$(echo "$BASE_OUTPUT" | grep -oE '[0-9]+ passed;' | awk '{s+=$1} END {print s+0}')
BASE_FAILED=$(echo "$BASE_OUTPUT" | grep -oE '[0-9]+ failed;' | awk '{s+=$1} END {print s+0}')

# Sum all TB_SUMMARY lines from per-module matrix tests.
# Each module test emits its own TB_SUMMARY (8 modules x 1150 cases = 9200 total).
MATRIX_TOTAL=0
MATRIX_PASSED=0
MATRIX_FAILED=0
FOUND_SUMMARY=0
while IFS= read -r line; do
  t=$(echo "$line" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
  p=$(echo "$line" | sed -n 's/.*passed=\([0-9]*\).*/\1/p')
  f=$(echo "$line" | sed -n 's/.*failed=\([0-9]*\).*/\1/p')
  MATRIX_TOTAL=$((MATRIX_TOTAL + ${t:-0}))
  MATRIX_PASSED=$((MATRIX_PASSED + ${p:-0}))
  MATRIX_FAILED=$((MATRIX_FAILED + ${f:-0}))
  FOUND_SUMMARY=1
done < <(echo "$MATRIX_OUTPUT" | grep 'TB_SUMMARY' || true)

if [ "$FOUND_SUMMARY" -eq 0 ]; then
  # Hyper matrix did not emit any summaries: treat as full failure.
  MATRIX_TOTAL=9200
  MATRIX_PASSED=0
  MATRIX_FAILED=9200
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
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

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
