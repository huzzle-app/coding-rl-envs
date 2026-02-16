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

# ── Anti-tampering: verify test files have not been modified ──
TEST_DIRS="shared/src/test gateway/src/test auth/src/test vehicles/src/test routes/src/test dispatch/src/test tracking/src/test billing/src/test analytics/src/test notifications/src/test compliance/src/test"
TAMPERED=false
for dir in $TEST_DIRS; do
  if [ -d "/app/$dir" ]; then
    if git -C /app diff --name-only HEAD -- "$dir" 2>/dev/null | grep -q .; then
      TAMPERED=true
      echo "TAMPERING DETECTED: test files modified in $dir"
    fi
  fi
done

if [ "$TAMPERED" = true ]; then
  echo "0.0" > /logs/verifier/reward.txt
  echo "Reward: 0.0 (test file tampering detected)" > /logs/verifier/test_output.txt
  echo "REJECTED: Test files were modified. Only source files may be changed."
  exit 0
fi

# Run Maven tests with failure-ignore so ALL modules compile and test
set +e
TEST_OUTPUT=$(mvn test -B -Dmaven.test.failure.ignore=true --fail-at-end 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Initialize counters
TOTAL_RUN=0
TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

# Parse Surefire summary lines: "Tests run: X, Failures: Y, Errors: Z, Skipped: W"
# Only count per-class summary lines (which appear inline with test class results),
# NOT the final reactor summary line. Per-class lines contain "<<< FAILURE!" or
# end with "-- in <classname>", while the final summary does not.
while IFS= read -r line; do
    # Skip the final reactor summary line (it has no class context)
    if echo "$line" | grep -qE '^\[INFO\] Tests run:.*Time elapsed.*$' && ! echo "$line" | grep -q ' -- in '; then
      continue
    fi
    if echo "$line" | grep -qE '^\[ERROR\] Tests run:.*Time elapsed.*$' && ! echo "$line" | grep -q ' -- in '; then
      continue
    fi

    RUN=$(echo "$line" | grep -oP 'Tests run: \K[0-9]+' || echo 0)
    FAIL=$(echo "$line" | grep -oP 'Failures: \K[0-9]+' || echo 0)
    ERR=$(echo "$line" | grep -oP 'Errors: \K[0-9]+' || echo 0)
    SKIP=$(echo "$line" | grep -oP 'Skipped: \K[0-9]+' || echo 0)

    TOTAL_RUN=$((TOTAL_RUN + RUN))
    TOTAL_FAILURES=$((TOTAL_FAILURES + FAIL))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERR))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIP))
done < <(echo "$TEST_OUTPUT" | grep 'Tests run:')

# Calculate passed tests
PASSED=$((TOTAL_RUN - TOTAL_FAILURES - TOTAL_ERRORS - TOTAL_SKIPPED))
TOTAL=$((TOTAL_RUN - TOTAL_SKIPPED))

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

# Apply 8-threshold reward function (Principal environment)
# Use local scoring module with multi-solution bonus (with bash fallback)
REWARD=""
if command -v python3 &>/dev/null; then
  REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null)
fi
if [ -z "$REWARD" ]; then
  # Bash fallback for containers without Python
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

# Write reward to file
echo "$REWARD" > /logs/verifier/reward.txt

# JSON results output
if command -v python3 &>/dev/null; then
  RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')
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
