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

# Run Jest test suite
set +e
TEST_OUTPUT=$(npx jest --ci --no-color 2>&1)
TEST_EXIT=$?
set -e
echo "$TEST_OUTPUT" > /logs/verifier/test_output.txt

# Parse Jest output for test results
# Jest summary format: "Tests: X failed, Y passed, Z total"
PASSED=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
TOTAL=$(echo "$TEST_OUTPUT" | grep -E '^Tests:' | grep -oE '[0-9]+ total' | grep -oE '[0-9]+' || echo 0)

# Ensure defaults if parsing fails
PASSED=${PASSED:-0}
TOTAL=${TOTAL:-0}

if [ "$TOTAL" -eq 0 ]; then
    echo "0.0" > /logs/verifier/reward.txt
    if [ "$TEST_EXIT" -ne 0 ]; then
      echo "Verifier error: test runner failed before any result could be parsed."
      exit 1
    fi
    echo "No tests found. Reward: 0.0"
    exit 1
fi

# Anti-reward-hacking: minimum test count validation
# MediaFlow has 537 tests; require at least 510 to prevent test deletion gaming
EXPECTED_MIN_TESTS=510
if [ "$TOTAL" -lt "$EXPECTED_MIN_TESTS" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: Expected at least $EXPECTED_MIN_TESTS tests but found $TOTAL. Reward: 0.0"
    echo "0.0"
    exit 0
fi

# Anti-reward-hacking: verify test files haven't been modified
TEST_DIRS="tests/unit tests/integration tests/contract tests/chaos tests/security tests/performance tests/system"
MODIFIED_TESTS=$(cd /app && git diff --name-only HEAD -- $TEST_DIRS tests/setup.js jest.config.js 2>/dev/null | wc -l | tr -d ' ')
if [ "$MODIFIED_TESTS" -gt 0 ]; then
    echo "Warning: $MODIFIED_TESTS test/config files modified. Checking for test deletion..."
    DELETED_TESTS=$(cd /app && git diff --diff-filter=D --name-only HEAD -- $TEST_DIRS 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DELETED_TESTS" -gt 0 ]; then
        echo "0.0" > /logs/verifier/reward.txt
        echo "Anti-tampering: $DELETED_TESTS test files deleted. Reward: 0.0"
        echo "0.0"
        exit 0
    fi
fi

# Anti-reward-hacking: checksum-based test file integrity
# Combined SHA-256 of all test files, computed at environment creation
EXPECTED_CHECKSUM="3a5fe05d6225f8d452adb3af170a77c541a7db6d0ac0f686f64442c53d9dcfcc"
JEST_CONFIG_CHECKSUM="c39809ea6bb337a2ddf44d52980ee919946a1b028c88b29f833a08aef1512f89"
if command -v sha256sum &> /dev/null; then
    ACTUAL_CHECKSUM=$(cd /app && find tests -name '*.test.js' -o -name 'setup.js' -path 'tests/*' | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)
    ACTUAL_CONFIG=$(cd /app && sha256sum jest.config.js | cut -d' ' -f1)
elif command -v shasum &> /dev/null; then
    ACTUAL_CHECKSUM=$(cd /app && find tests -name '*.test.js' -o -name 'setup.js' -path 'tests/*' | sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
    ACTUAL_CONFIG=$(cd /app && shasum -a 256 jest.config.js | cut -d' ' -f1)
else
    ACTUAL_CHECKSUM="$EXPECTED_CHECKSUM"
    ACTUAL_CONFIG="$JEST_CONFIG_CHECKSUM"
fi

if [ "$ACTUAL_CHECKSUM" != "$EXPECTED_CHECKSUM" ] || [ "$ACTUAL_CONFIG" != "$JEST_CONFIG_CHECKSUM" ]; then
    echo "0.0" > /logs/verifier/reward.txt
    echo "Anti-tampering: Test file checksums do not match. Reward: 0.0"
    echo "0.0"
    exit 0
fi

# Calculate pass ratio
RATIO=$(awk "BEGIN {printf \"%.6f\", $PASSED / $TOTAL}")

# Apply 8-threshold reward function (Principal environment)
# Thresholds: [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
# Rewards:    [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
# Use local scoring module with multi-solution bonus
REWARD=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG 2>/dev/null || echo "0.0")
RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "$PASSED" --total "$TOTAL" --tier "principal" --cwd /app $TRAINING_MODE_ARG $PREV_PASSED_ARG --json 2>/dev/null || echo '{}')

# Write reward to file
echo "$REWARD" > /logs/verifier/reward.txt
echo "$RESULTS_JSON" > /logs/verifier/results.json

# Display results
echo "Tests: $PASSED passed out of $TOTAL total"
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
