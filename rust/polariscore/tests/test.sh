#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# ── Anti-tampering: verify test file integrity ────────────────────────
declare -A EXPECTED_CHECKSUMS=(
  ["tests/hyper_matrix_tests.rs"]="a5e50e30bf68aa01493181c3e187abc0126424f8e83a0ededc07df4438827ed5"
  ["tests/routing_tests.rs"]="a085878e59b61a3befad05333eb613b8e596e35beffb199a2f10396c47b7b011"
  ["tests/allocator_tests.rs"]="8ceb82f9c49ad05e97f4151c3e1d4c9dd2dbc2c8c0a6f8bb6fa1f6a080f6ec47"
  ["tests/policy_tests.rs"]="10d0f004499a18b063dbfa4cf16abf3f6e045694b01c07ee18bf50b5d506ab9b"
  ["tests/resilience_tests.rs"]="8f4ad3458b021aafcc7018d463dcb37a6c38f355a4239bed793e560235776af7"
  ["tests/security_tests.rs"]="ff92bcd148a4c6bbcc5728b8454892e8a35c168a7e5b58915f2f4d5467fa56ec"
  ["tests/queue_statistics_tests.rs"]="d9023cb0e0289e9d34f818f67bf75ee38bb3fbe0fd4ab2b5f56ddf565599a20a"
  ["tests/workflow_integration_tests.rs"]="b653c52ab46790b98e85939ef34ded431cc4602aea435d4c787a0d2698493824"
  ["tests/chaos_replay_tests.rs"]="3d932d6a2dd58bf8515ff1321d16c885b6100ee4ebb821c962dab2c14bb5f03b"
  ["tests/services_contracts.rs"]="c39bfbaec3a4f93f4d5eb05cbc8c95b0b468463c7aa6835f208e8dd6ac6a46ea"
  ["tests/statistics_targeted_tests.rs"]="412ba14ffb6a11de6c516ff8422e7ddc9f61ce7f5ee7cb87e51414472a9ae7ad"
  ["tests/economics_targeted_tests.rs"]="223e3aab3551b26edf57ca10429b7615a3f85caebae14b8685ebe69a467e233f"
  ["tests/workflow_targeted_tests.rs"]="46441778d7993fc3df5f935a67815d0c525638d79edd29900dfce749d67ccb1a"
  ["tests/queue_targeted_tests.rs"]="11a3c2a101d7851dcd058163e6bb57cee994bfa889bc055ea0b1ce5cb5f1b594"
)

TAMPERED=0
for file in "${!EXPECTED_CHECKSUMS[@]}"; do
  if [ -f "/app/$file" ]; then
    ACTUAL=$(sha256sum "/app/$file" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "/app/$file" 2>/dev/null | cut -d' ' -f1)
    if [ "$ACTUAL" != "${EXPECTED_CHECKSUMS[$file]}" ]; then
      echo "INTEGRITY VIOLATION: $file has been modified"
      TAMPERED=1
    fi
  else
    echo "INTEGRITY VIOLATION: $file is missing"
    TAMPERED=1
  fi
done

if [ "$TAMPERED" -eq 1 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "Verifier error: test files have been tampered with. Reward set to 0."
  exit 1
fi

# ── Training mode support ─────────────────────────────────────────────
TRAINING_MODE_ARG=""
if [ -n "${TRAINING_MODE:-}" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "${PREV_PASSED:-}" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

CARGO_BIN=$(command -v cargo || true)
if [ -z "$CARGO_BIN" ] && [ -x /usr/local/cargo/bin/cargo ]; then
  CARGO_BIN=/usr/local/cargo/bin/cargo
fi
if [ -z "$CARGO_BIN" ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "Verifier error: cargo binary not found."
  exit 1
fi

set +e
TEST_OUTPUT=$("$CARGO_BIN" test 2>&1)
TEST_EXIT=$?
set -e

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL_PASSED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ passed' | awk '{sum+=$1} END {print sum+0}')
TOTAL_FAILED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ failed' | awk '{sum+=$1} END {print sum+0}')
TOTAL=$((TOTAL_PASSED + TOTAL_FAILED))

if [ "$TOTAL" -eq 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: cargo test failed before any test result could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi

# Use local scoring module with multi-solution bonus (8-threshold, Hyper-Principal)
REWARD=$(python3 /app/environment/scoring.py --passed "$TOTAL_PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$TOTAL_PASSED" --total "$TOTAL" --tier "hyper-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $TOTAL_PASSED passed, $TOTAL_FAILED failed (total: $TOTAL)"

# Show incremental info if available
if [ -n "${PREV_PASSED:-}" ]; then
  DELTA=$((TOTAL_PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
