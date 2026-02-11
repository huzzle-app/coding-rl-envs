#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
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

if [ -x "./gradlew" ]; then
  TEST_OUTPUT=$(./gradlew test --continue --no-daemon 2>&1 || true)
else
  TEST_OUTPUT=$(gradle test --continue --no-daemon 2>&1 || true)
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
        echo "No tests found. Reward: 0.0"
        exit 0
    fi
fi

RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# 10-threshold sparse reward (Apex-Principal)
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null || echo "0.0")

echo "$REWARD" > /logs/verifier/reward.txt
echo "Tests: $PASSED passed, $TOTAL_FAILURES failures, $TOTAL_ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
