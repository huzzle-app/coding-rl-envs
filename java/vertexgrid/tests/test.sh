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

# Provision Maven when running on base JDK images without mvn.
if ! command -v mvn >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update >/tmp/vertexgrid_apt_update.log 2>&1 || true
        apt-get install -y --no-install-recommends maven openjdk-21-jdk >/tmp/vertexgrid_apt_install.log 2>&1 || true
    fi
fi

# Ensure Java 21 is available for virtual-thread APIs used by tests.
if command -v java >/dev/null 2>&1; then
    JAVA_MAJOR=$(java -version 2>&1 | sed -n 's/.*version \"\([0-9][0-9]*\).*/\1/p' | head -1)
    if [ -n "$JAVA_MAJOR" ] && [ "$JAVA_MAJOR" -lt 21 ]; then
        if command -v apt-get >/dev/null 2>&1; then
            export DEBIAN_FRONTEND=noninteractive
            apt-get update >/tmp/vertexgrid_apt_update.log 2>&1 || true
            apt-get install -y --no-install-recommends openjdk-21-jdk >/tmp/vertexgrid_apt_jdk21.log 2>&1 || true
            if command -v javac >/dev/null 2>&1; then
                export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")"
                export PATH="$JAVA_HOME/bin:$PATH"
            fi
        fi
    fi
fi

# ==============================================================================
# Anti-reward-hacking: verify test file integrity
# ==============================================================================
TAMPER_DETECTED=0

# Check that test files exist and haven't been deleted
EXPECTED_TEST_FILES=(
  "shared/src/test/java/com/vertexgrid/shared/HyperMatrixTest.java"
  "shared/src/test/java/com/vertexgrid/shared/CollectionUtilsTest.java"
  "shared/src/test/java/com/vertexgrid/shared/ConcurrencyTest.java"
  "shared/src/test/java/com/vertexgrid/shared/ConfigTest.java"
  "shared/src/test/java/com/vertexgrid/shared/EventBusTest.java"
  "shared/src/test/java/com/vertexgrid/shared/EventStoreTest.java"
  "shared/src/test/java/com/vertexgrid/shared/ObservabilityTest.java"
  "shared/src/test/java/com/vertexgrid/shared/SecurityTest.java"
  "gateway/src/test/java/com/vertexgrid/gateway/RequestServiceTest.java"
  "gateway/src/test/java/com/vertexgrid/gateway/GatewaySecurityTest.java"
  "auth/src/test/java/com/vertexgrid/auth/AuthServiceTest.java"
  "auth/src/test/java/com/vertexgrid/auth/TokenValidatorTest.java"
  "vehicles/src/test/java/com/vertexgrid/vehicles/VehicleServiceTest.java"
  "vehicles/src/test/java/com/vertexgrid/vehicles/VehicleModelTest.java"
  "routes/src/test/java/com/vertexgrid/routes/RouteServiceTest.java"
  "dispatch/src/test/java/com/vertexgrid/dispatch/DispatchServiceTest.java"
  "tracking/src/test/java/com/vertexgrid/tracking/TrackingServiceTest.java"
  "tracking/src/test/java/com/vertexgrid/tracking/TrackingEventTest.java"
  "billing/src/test/java/com/vertexgrid/billing/BillingServiceTest.java"
  "analytics/src/test/java/com/vertexgrid/analytics/AnalyticsServiceTest.java"
  "notifications/src/test/java/com/vertexgrid/notifications/NotificationServiceTest.java"
  "compliance/src/test/java/com/vertexgrid/compliance/ComplianceServiceTest.java"
  "billing/src/test/java/com/vertexgrid/billing/HyperMatrixTest.java"
  "analytics/src/test/java/com/vertexgrid/analytics/HyperMatrixTest.java"
  "compliance/src/test/java/com/vertexgrid/compliance/HyperMatrixTest.java"
  "routes/src/test/java/com/vertexgrid/routes/HyperMatrixTest.java"
  "tracking/src/test/java/com/vertexgrid/tracking/HyperMatrixTest.java"
)

for tf in "${EXPECTED_TEST_FILES[@]}"; do
  if [ ! -f "$tf" ]; then
    echo "TAMPER DETECTED: Test file missing: $tf"
    TAMPER_DETECTED=1
  fi
done

# Check that test files haven't been modified (assert count check)
# Each test file must contain a minimum number of @Test annotations
check_min_tests() {
  local file="$1"
  local min_count="$2"
  if [ -f "$file" ]; then
    local actual
    actual=$(grep -c '@Test' "$file" 2>/dev/null || echo 0)
    if [ "$actual" -lt "$min_count" ]; then
      echo "TAMPER DETECTED: $file has only $actual @Test (expected >= $min_count)"
      TAMPER_DETECTED=1
    fi
  fi
}

check_min_tests "shared/src/test/java/com/vertexgrid/shared/HyperMatrixTest.java" 1
check_min_tests "shared/src/test/java/com/vertexgrid/shared/SecurityTest.java" 10
check_min_tests "shared/src/test/java/com/vertexgrid/shared/CollectionUtilsTest.java" 8
check_min_tests "billing/src/test/java/com/vertexgrid/billing/BillingServiceTest.java" 50
check_min_tests "analytics/src/test/java/com/vertexgrid/analytics/AnalyticsServiceTest.java" 40
check_min_tests "compliance/src/test/java/com/vertexgrid/compliance/ComplianceServiceTest.java" 40
check_min_tests "dispatch/src/test/java/com/vertexgrid/dispatch/DispatchServiceTest.java" 15
check_min_tests "routes/src/test/java/com/vertexgrid/routes/RouteServiceTest.java" 15

# Check shared HyperMatrixTest still generates 12000+ tests with 8 modes
if [ -f "shared/src/test/java/com/vertexgrid/shared/HyperMatrixTest.java" ]; then
  if ! grep -q 'final int total = 12000' "shared/src/test/java/com/vertexgrid/shared/HyperMatrixTest.java"; then
    echo "TAMPER DETECTED: HyperMatrixTest test count modified"
    TAMPER_DETECTED=1
  fi
  if ! grep -q 'idx % 8' "shared/src/test/java/com/vertexgrid/shared/HyperMatrixTest.java"; then
    echo "TAMPER DETECTED: HyperMatrixTest mode count reduced"
    TAMPER_DETECTED=1
  fi
fi

# Check downstream HyperMatrixTests exist and have correct test counts
check_hyper_matrix() {
  local file="$1"
  local expected_total="$2"
  if [ -f "$file" ]; then
    if ! grep -q "final int total = $expected_total" "$file"; then
      echo "TAMPER DETECTED: $file test count modified (expected $expected_total)"
      TAMPER_DETECTED=1
    fi
  fi
}

check_hyper_matrix "billing/src/test/java/com/vertexgrid/billing/HyperMatrixTest.java" 500
check_hyper_matrix "analytics/src/test/java/com/vertexgrid/analytics/HyperMatrixTest.java" 500
check_hyper_matrix "compliance/src/test/java/com/vertexgrid/compliance/HyperMatrixTest.java" 500
check_hyper_matrix "routes/src/test/java/com/vertexgrid/routes/HyperMatrixTest.java" 500
check_hyper_matrix "tracking/src/test/java/com/vertexgrid/tracking/HyperMatrixTest.java" 500

# If tampering detected, assign zero reward
if [ "$TAMPER_DETECTED" -eq 1 ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "Test tampering detected. Reward: 0.0"
  echo "Agents must fix bugs in source files only, not modify test files."
  exit 0
fi

# ==============================================================================
# Build all modules first (compile only, skip tests) so downstream modules
# can compile even if upstream tests fail.
# ==============================================================================
set +e
mvn install -DskipTests -B -q 2>/dev/null
INSTALL_EXIT=$?
set -e

if [ "$INSTALL_EXIT" -ne 0 ]; then
  # If compilation fails, try to still run whatever tests we can
  echo "Warning: compilation had errors, some modules may not run tests"
fi

# ==============================================================================
# Run Maven tests with -fn (fail-never) to ensure ALL modules run tests,
# even when upstream modules have test failures.
# ==============================================================================
set +e
TEST_OUTPUT=$(mvn test -B -fn 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Initialize counters
TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

# Parse each line containing "Tests run:" from Maven surefire output
while IFS= read -r line; do
    RUN=$(echo "$line" | grep -oE 'Tests run: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    FAIL=$(echo "$line" | grep -oE 'Failures: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    ERR=$(echo "$line" | grep -oE 'Errors: [0-9]+' | grep -oE '[0-9]+' || echo 0)
    SKIP=$(echo "$line" | grep -oE 'Skipped: [0-9]+' | grep -oE '[0-9]+' || echo 0)

    TOTAL_RUN=$((TOTAL_RUN + RUN))
    TOTAL_FAILURES=$((TOTAL_FAILURES + FAIL))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERR))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIP))
done < <(echo "$TEST_OUTPUT" | grep 'Tests run:')

# Calculate passed tests
PASSED=$((TOTAL_RUN - TOTAL_FAILURES - TOTAL_ERRORS - TOTAL_SKIPPED))
TOTAL=$((TOTAL_RUN - TOTAL_SKIPPED))

# If build failed before test discovery, force a failing summary.
if echo "$TEST_OUTPUT" | grep -qE 'COMPILATION ERROR|command not found'; then
    if [ "$TOTAL" -le 0 ]; then
        TOTAL=1
        TOTAL_FAILURES=1
        TOTAL_ERRORS=0
        PASSED=0
    fi
fi

# Handle case where no tests are found
if [ "$TOTAL" -le 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Apply 10-threshold reward function (Apex-Principal environment)
# Use local scoring module with multi-solution bonus (with bash fallback)
REWARD=""
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null)
fi
if [ -z "$REWARD" ]; then
  # Bash fallback for containers without Python
  RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")
  REWARD=$(awk -v r="$RATIO" 'BEGIN {
    if (r >= 1.0) print 1.0
    else if (r >= 0.99) print 0.85
    else if (r >= 0.96) print 0.66
    else if (r >= 0.90) print 0.47
    else if (r >= 0.80) print 0.31
    else if (r >= 0.67) print 0.19
    else if (r >= 0.52) print 0.11
    else if (r >= 0.36) print 0.05
    else if (r >= 0.22) print 0.015
    else print 0.0
  }')
fi

# Write reward to file
echo "$REWARD" > /logs/verifier/reward.txt

# JSON results output
if command -v python3 &>/dev/null; then
  RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')
  echo "$RESULTS_JSON" > /logs/verifier/results.json
fi

# Output summary
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
