#!/bin/bash
# verify_all_fixes.sh — Apply all 29 bug fixes, run cargo test, verify 90/90 pass, then revert.
#
# Usage:
#   bash tests/verify_all_fixes.sh          # from repo root
#   bash tests/verify_all_fixes.sh --keep   # apply fixes without reverting (for debugging)
#
# Exit codes:
#   0 = All 90 tests pass after fixes
#   1 = Some tests failed or build error
#   2 = solve.sh not found or not executable

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOLVE_SH="$REPO_ROOT/solution/solve.sh"
KEEP_FIXES=false

if [[ "${1:-}" == "--keep" ]]; then
    KEEP_FIXES=true
fi

# ---------- pre-flight ----------
if [[ ! -x "$SOLVE_SH" ]]; then
    echo "ERROR: $SOLVE_SH not found or not executable."
    exit 2
fi

# Ensure we are in repo root
cd "$REPO_ROOT"

# Check for uncommitted changes to src/ — warn but proceed
if ! git diff --quiet -- src/; then
    echo "WARNING: Uncommitted changes in src/. They will be reverted after verification."
fi

# ---------- apply fixes ----------
echo "=== Applying all 29 bug fixes via solution/solve.sh ==="
bash "$SOLVE_SH"
echo ""

# ---------- run tests ----------
echo "=== Running cargo test ==="
set +e
TEST_OUTPUT=$(cargo test 2>&1)
TEST_EXIT=$?
set -e

echo "$TEST_OUTPUT"
echo ""

# ---------- parse results ----------
TOTAL_PASSED=0
TOTAL_FAILED=0

while IFS= read -r line; do
    P=$(echo "$line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
    F=$(echo "$line" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)
    TOTAL_PASSED=$((TOTAL_PASSED + P))
    TOTAL_FAILED=$((TOTAL_FAILED + F))
done < <(echo "$TEST_OUTPUT" | grep 'test result:')

TOTAL=$((TOTAL_PASSED + TOTAL_FAILED))

echo "=== Results: $TOTAL_PASSED passed, $TOTAL_FAILED failed (total: $TOTAL) ==="

# ---------- revert ----------
if [[ "$KEEP_FIXES" == "false" ]]; then
    echo ""
    echo "=== Reverting all source changes ==="
    git checkout -- src/
    echo "Reverted src/ to original (buggy) state."
fi

# ---------- verdict ----------
EXPECTED=90
if [[ "$TOTAL_PASSED" -eq "$EXPECTED" && "$TOTAL_FAILED" -eq 0 ]]; then
    echo ""
    echo "PASS: All $EXPECTED tests pass after applying fixes."
    exit 0
else
    echo ""
    echo "FAIL: Expected $EXPECTED/0, got $TOTAL_PASSED passed / $TOTAL_FAILED failed."
    exit 1
fi
