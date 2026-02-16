#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

# ============================================================
# Anti-tampering: verify test infrastructure integrity
# ============================================================
TAMPER_DETECTED=false

# 1. Verify all expected test files exist and are unmodified
declare -A EXPECTED_HASHES=(
  ["src/test/java/com/terminalbench/transitcore/AuditTrailTest.java"]="5dbd7dcdc875bf0d243802e7dcf7c2fb716a02da4f92c887b86d734b79c5d6da"
  ["src/test/java/com/terminalbench/transitcore/CapacityBalancerTest.java"]="73b9c776798598a3741e35d518acf1c41eea6501f71f245b8624627b28c11aba"
  ["src/test/java/com/terminalbench/transitcore/ComplianceLedgerTest.java"]="7e707bf0d1e8fccaf0195ab21cf307a79fabbd642a99cd4937349f1fe663174a"
  ["src/test/java/com/terminalbench/transitcore/DispatchPlannerTest.java"]="9d0ce5451b3a9b28c1894276febc15befaa0a4fcfef8c9a8cc182ff9bc213f64"
  ["src/test/java/com/terminalbench/transitcore/FaultInjectionFlowTest.java"]="36d9ab65a4008a39f1b81ca686c3557f92e232f4cb8b8a3e4c850ff445e06fe6"
  ["src/test/java/com/terminalbench/transitcore/IntegrationFlowTest.java"]="3d7867917ed65effccbd5fb9e34d39866be2da637794a9a6ccd7718a36c9be7e"
  ["src/test/java/com/terminalbench/transitcore/BoundaryStressTest.java"]="6fbf796c70470bde7fafb068b78661044e950786c0874afe5a4a99a18ee910d2"
  ["src/test/java/com/terminalbench/transitcore/MigrationsTest.java"]="8d2a48ed6532d8a870c6ff8e486e58187f8ab6f15c5620ef0491a47e0f16e78c"
  ["src/test/java/com/terminalbench/transitcore/PolicyEngineTest.java"]="de52b19a3038819eda0c82e1de34c829a901d3bc9a2683fc890737c1a4470db3"
  ["src/test/java/com/terminalbench/transitcore/QueueGovernorTest.java"]="12bced954a1352a5664381a9a44673a1eeb2c0a0742ef204cb487f840ddb19f2"
  ["src/test/java/com/terminalbench/transitcore/ResilienceReplayTest.java"]="95b82c251846487ff0c1d75ac6818d2953da77c83e05ff2c3e1d9df3daab6f8f"
  ["src/test/java/com/terminalbench/transitcore/RetryBudgetTest.java"]="d5a33e31547dc32a768aa17107672117c5e2585d56bd7e3e556a2a9b7221c7cf"
  ["src/test/java/com/terminalbench/transitcore/RoutingHeuristicsTest.java"]="dbe10eef8591042047a2742b4bbd3d50939d206590d523d78a317ea389f9554a"
  ["src/test/java/com/terminalbench/transitcore/SecurityPolicyTest.java"]="3fcda10ad3b3c9cc19413b88ff2a1103704afbcf3a876c8cc3cb99328e3e0d91"
  ["src/test/java/com/terminalbench/transitcore/ServicesContractsTest.java"]="aa1ca2df62d01c943beca4880ce4f970da61235000ff6bfa2f51e58ed106add1"
  ["src/test/java/com/terminalbench/transitcore/SlaModelTest.java"]="da4e563f030e7a21ffa7c3494827139509a1f0f99dc686181aefa974eb8d5d83"
  ["src/test/java/com/terminalbench/transitcore/StatisticsReducerTest.java"]="f381114b13c7264d9038a0f211652a71d3816781ed6f2f8d3c58480f5ad016ee"
  ["src/test/java/com/terminalbench/transitcore/StressTest.java"]="f37502d7e8bc02315017c01e9bb87f653b45160953f51087adaf04e3c962ea3c"
  ["src/test/java/com/terminalbench/transitcore/WatermarkWindowTest.java"]="39c26975cdb5050478aaa330e7263ae45d4300c32b71d7ab871ae51127e8041c"
  ["src/test/java/com/terminalbench/transitcore/WorkflowOrchestratorTest.java"]="8aa95062dd0036be526aa43753dea3b526fa294a34f04aac3cd3ee268f9c84df"
)

for filepath in "${!EXPECTED_HASHES[@]}"; do
  expected_hash="${EXPECTED_HASHES[$filepath]}"
  if [ ! -f "$filepath" ]; then
    echo "INTEGRITY ERROR: Missing test file $filepath"
    TAMPER_DETECTED=true
    continue
  fi
  actual_hash=$(sha256sum "$filepath" | cut -d' ' -f1)
  if [ "$actual_hash" != "$expected_hash" ]; then
    echo "INTEGRITY ERROR: Test file modified: $filepath"
    TAMPER_DETECTED=true
  fi
done

# 2. Verify pom.xml hasn't been modified to exclude tests
POM_HASH=$(sha256sum pom.xml | cut -d' ' -f1)
if [ "$POM_HASH" != "b95ed950b2a98041787738a1bc57de06e1feec067afcb8c7679fc0ced24c3c89" ]; then
  echo "INTEGRITY ERROR: pom.xml has been modified"
  TAMPER_DETECTED=true
fi

# 3. Verify scoring/reward infrastructure hasn't been modified
for infra_file in "environment/scoring.py:466c35822b10b440f94ee726c5acbb384b2266bc1a8cf5759edd02d9211f5ccd" \
                  "environment/reward.py:36064f8036d3fa7a1b2087ae4a215b815fcd7bc67caf12f857e415e9b133a924"; do
  IFS=':' read -r infra_path infra_expected <<< "$infra_file"
  if [ -f "$infra_path" ]; then
    infra_actual=$(sha256sum "$infra_path" | cut -d' ' -f1)
    if [ "$infra_actual" != "$infra_expected" ]; then
      echo "INTEGRITY ERROR: $infra_path has been modified"
      TAMPER_DETECTED=true
    fi
  fi
done

if [ "$TAMPER_DETECTED" = true ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "Test infrastructure tampering detected"}' > /logs/verifier/results.json
  echo "Reward: 0.0 (test infrastructure tampering detected)"
  exit 0
fi

# ============================================================
# Training mode support
# ============================================================
TRAINING_MODE_ARG=""
if [ -n "${TRAINING_MODE:-}" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
fi

# Incremental reward support
PREV_PASSED_ARG=""
if [ -n "${PREV_PASSED:-}" ]; then
  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"
fi

# Prevent stale surefire reports from previous runs contaminating counts.
if [ -d target/surefire-reports ]; then
  find target/surefire-reports -type f -name 'TEST-*.xml' -delete
fi

set +e
TEST_OUTPUT=$(mvn test -B 2>&1)
TEST_EXIT=$?
set -e

echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

for report in target/surefire-reports/TEST-*.xml; do
  if [ ! -f "$report" ]; then
    continue
  fi

  LINE=$(grep -m1 '<testsuite ' "$report" || true)
  RUN=$(echo "$LINE" | sed -n 's/.*tests="\([0-9]\+\)".*/\1/p')
  FAIL=$(echo "$LINE" | sed -n 's/.*failures="\([0-9]\+\)".*/\1/p')
  ERR=$(echo "$LINE" | sed -n 's/.*errors="\([0-9]\+\)".*/\1/p')
  SKIP=$(echo "$LINE" | sed -n 's/.*skipped="\([0-9]\+\)".*/\1/p')

  RUN=${RUN:-0}
  FAIL=${FAIL:-0}
  ERR=${ERR:-0}
  SKIP=${SKIP:-0}

  TOTAL_RUN=$((TOTAL_RUN + RUN))
  TOTAL_FAILURES=$((TOTAL_FAILURES + FAIL))
  TOTAL_ERRORS=$((TOTAL_ERRORS + ERR))
  TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIP))
done

TOTAL=$((TOTAL_RUN - TOTAL_SKIPPED))

# 3. Verify minimum expected test count (anti-tampering)
MIN_EXPECTED_TESTS=1640
if [ "$TOTAL" -lt "$MIN_EXPECTED_TESTS" ]; then
  echo "INTEGRITY ERROR: Expected at least $MIN_EXPECTED_TESTS tests but found $TOTAL"
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "Test count below minimum threshold"}' > /logs/verifier/results.json
  exit 0
fi

if [ "$TOTAL" -le 0 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  if [ "$TEST_EXIT" -ne 0 ]; then
    echo "Verifier error: mvn test failed before any test summary could be parsed."
    exit 1
  fi
  echo "Verifier error: no tests were discovered."
  exit 1
fi

PASSED=$((TOTAL - TOTAL_FAILURES - TOTAL_ERRORS))
if [ "$PASSED" -lt 0 ]; then
  PASSED=0
fi


# 8-tier thresholds for ultra-principal difficulty
# Use local scoring module with multi-solution bonus (with bash fallback)
REWARD=""
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null)
fi
if [ -z "$REWARD" ]; then
  # Bash fallback for containers without Python
  RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")
  REWARD=$(awk -v r="$RATIO" 'BEGIN {
    if (r >= 1.0) print 1.0
    else if (r >= 0.95) print 0.78
    else if (r >= 0.85) print 0.55
    else if (r >= 0.70) print 0.38
    else if (r >= 0.55) print 0.22
    else if (r >= 0.40) print 0.12
    else if (r >= 0.25) print 0.05
    else print 0.0
  }')
fi

echo "$REWARD" > /logs/verifier/reward.txt

# JSON results output
if command -v python3 &>/dev/null; then
  RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "ultra-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')
  echo "$RESULTS_JSON" > /logs/verifier/results.json
else
  RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")
  echo "{\"reward\": $REWARD, \"pass_rate\": $RATIO, \"passed\": $PASSED, \"total\": $TOTAL, \"tier\": \"ultra-principal\"}" > /logs/verifier/results.json
fi
echo "Tests: $PASSED passed, $((TOTAL_FAILURES + TOTAL_ERRORS)) failed (total: $TOTAL)"

# Show incremental info if available
if [ -n "${PREV_PASSED:-}" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
