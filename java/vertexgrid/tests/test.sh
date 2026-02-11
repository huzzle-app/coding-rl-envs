#!/bin/bash
set -o pipefail
mkdir -p /logs/verifier

# Training mode support: set TRAINING_MODE env var to enable dense rewards
# Options: linear, sublinear, smooth (default: unset = sparse evaluation rewards)
TRAINING_MODE_ARG=""
if [ -n "$TRAINING_MODE" ]; then
  TRAINING_MODE_ARG="--training-mode $TRAINING_MODE"
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

# Run Maven tests and capture output
TEST_OUTPUT=$(mvn test -B 2>&1 || true)
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Initialize counters
TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

# Parse each line containing "Tests run:"
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
if echo "$TEST_OUTPUT" | grep -qE 'BUILD FAILURE|COMPILATION ERROR|command not found'; then
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
    echo "No tests found. Reward: 0.0"
    exit 0
fi

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Apply 10-threshold reward function (Apex-Principal environment)
# Use local scoring module with multi-solution bonus (with bash fallback)
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "apex-principal" --cwd /app $TRAINING_MODE_ARG 2>/dev/null)
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

# Output summary
echo "Tests: $PASSED passed, $TOTAL_FAILURES failures, $TOTAL_ERRORS errors (total: $TOTAL)"
echo "Pass ratio: $RATIO | Reward: $REWARD"
