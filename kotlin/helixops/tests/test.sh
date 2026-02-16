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

# Clear stale XML so failed runs cannot reuse old test counts.
find . -type d \( -path '*/build/test-results/test' -o -path '*/build/reports/tests/test' \) -prune -exec rm -rf {} + 2>/dev/null || true

# Provision JDK 21 when the container defaults to Java 17.
if command -v java >/dev/null 2>&1; then
  JAVA_MAJOR=$(java -version 2>&1 | sed -n 's/.*version \"\([0-9][0-9]*\).*/\1/p' | head -1)
  if [ -n "$JAVA_MAJOR" ] && [ "$JAVA_MAJOR" -lt 21 ]; then
    if command -v apt-get >/dev/null 2>&1; then
      export DEBIAN_FRONTEND=noninteractive
      apt-get update >/tmp/helixops_apt_update.log 2>&1 || true
      apt-get install -y --no-install-recommends openjdk-21-jdk >/tmp/helixops_apt_jdk21.log 2>&1 || true
      if command -v javac >/dev/null 2>&1; then
        export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")"
        export PATH="$JAVA_HOME/bin:$PATH"
      fi
    fi
  fi
fi

# ============================================================================
# Anti-tampering: verify test files have not been modified
# ============================================================================
TAMPER_DETECTED=0
declare -A EXPECTED_LINES
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/HyperMatrixTests.kt"]=1094
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/CacheTests.kt"]=249
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/ConfigTests.kt"]=515
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/DelegationTests.kt"]=235
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/EventBusTests.kt"]=291
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/KotlinUtilTests.kt"]=200
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/ObservabilityTests.kt"]=327
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/SecurityTests.kt"]=262
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/SerializationTests.kt"]=170
EXPECTED_LINES["shared/src/test/kotlin/com/mindvault/shared/SharedModelsTests.kt"]=441
EXPECTED_LINES["analytics/src/test/kotlin/com/mindvault/analytics/AnalyticsTests.kt"]=553
EXPECTED_LINES["auth/src/test/kotlin/com/mindvault/auth/AuthTests.kt"]=441
EXPECTED_LINES["billing/src/test/kotlin/com/mindvault/billing/BillingTests.kt"]=709
EXPECTED_LINES["collab/src/test/kotlin/com/mindvault/collab/CollabTests.kt"]=604
EXPECTED_LINES["documents/src/test/kotlin/com/mindvault/documents/DocumentTests.kt"]=872
EXPECTED_LINES["embeddings/src/test/kotlin/com/mindvault/embeddings/EmbeddingTests.kt"]=480
EXPECTED_LINES["gateway/src/test/kotlin/com/mindvault/gateway/GatewayTests.kt"]=669
EXPECTED_LINES["graph/src/test/kotlin/com/mindvault/graph/GraphTests.kt"]=788
EXPECTED_LINES["notifications/src/test/kotlin/com/mindvault/notifications/NotificationTests.kt"]=543
EXPECTED_LINES["search/src/test/kotlin/com/mindvault/search/SearchTests.kt"]=710

for TEST_FILE in "${!EXPECTED_LINES[@]}"; do
  if [ -f "$TEST_FILE" ]; then
    ACTUAL_LINES=$(wc -l < "$TEST_FILE" | tr -d ' ')
    EXPECTED=${EXPECTED_LINES[$TEST_FILE]}
    # Allow ±2 lines tolerance for line ending differences
    DIFF=$(( ACTUAL_LINES - EXPECTED ))
    if [ "$DIFF" -lt -2 ] || [ "$DIFF" -gt 2 ]; then
      echo "TAMPER DETECTED: $TEST_FILE has $ACTUAL_LINES lines (expected $EXPECTED)"
      TAMPER_DETECTED=1
    fi
  fi
done

if [ "$TAMPER_DETECTED" -eq 1 ]; then
  echo "Test file tampering detected. Agents must fix production source code, not tests."
  echo "0.0" > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "error": "test_tampering_detected"}' > /logs/verifier/results.json
  exit 1
fi

if [ -x "./gradlew" ]; then
  set +e
TEST_OUTPUT=$(./gradlew test --continue --no-daemon 2>&1)
TEST_EXIT=$?
set -e
else
  set +e
TEST_OUTPUT=$(gradle test --continue --no-daemon 2>&1)
TEST_EXIT=$?
set -e
fi
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse JUnit XML from all modules
TOTAL_TESTS=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

for xml in $(find . -path '*/test-results/test/TEST-*.xml' 2>/dev/null); do
    T=$(grep -oE 'tests="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    F=$(grep -oE 'failures="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    E=$(grep -oE 'errors="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    S=$(grep -oE 'skipped="[0-9]+"' "$xml" | head -1 | grep -oE '[0-9]+' || echo 0)
    TOTAL_TESTS=$((TOTAL_TESTS + T))
    TOTAL_FAILURES=$((TOTAL_FAILURES + F))
    TOTAL_ERRORS=$((TOTAL_ERRORS + E))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + S))
done

PASSED=$((TOTAL_TESTS - TOTAL_FAILURES - TOTAL_ERRORS - TOTAL_SKIPPED))
TOTAL=$((TOTAL_TESTS - TOTAL_SKIPPED))

if [ "$TOTAL" -le 0 ]; then
    if echo "$TEST_OUTPUT" | grep -qE 'BUILD FAILED|Execution failed for task|Compilation error'; then
        TOTAL=1
        TOTAL_FAILURES=1
        TOTAL_ERRORS=0
        PASSED=0
    else
        echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
        echo "No tests found. Reward: 0.0"
        exit 1
    fi
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 10-threshold sparse reward (Apex-Principal)
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json
echo "Tests: $PASSED passed, $TOTAL_FAILURES failures, $TOTAL_ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"

# Show incremental info if available
if [ -n "$PREV_PASSED" ]; then
  DELTA=$((PASSED - PREV_PASSED))
  if [ "$DELTA" -gt 0 ]; then
    echo "Progress: +$DELTA newly passing tests"
  elif [ "$DELTA" -lt 0 ]; then
    echo "Regression: $DELTA tests now failing"
  fi
fi
