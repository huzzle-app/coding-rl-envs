#!/usr/bin/env python3
"""
Transform all test.sh files to apply Recs 5, 6, and 10:
  Rec 5: Add crash detection (set +e / TEST_EXIT / set -e)
  Rec 6: Change exit 0 → exit 1 on zero tests
  Rec 10: Add PREV_PASSED support and JSON output

This script makes targeted, pattern-based edits. It does NOT rewrite files
from scratch — it preserves existing structure and only adds/modifies
specific blocks.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

def transform_test_sh(path: Path) -> list:
    """Apply transformations to a single test.sh file. Returns list of changes made."""
    content = path.read_text()
    original = content
    changes = []

    has_set_euo = bool(re.search(r'^set\s+-euo\s+pipefail', content, re.MULTILINE))

    # =========================================================================
    # Rec 10a: Add PREV_PASSED block after TRAINING_MODE block
    # =========================================================================
    if 'PREV_PASSED_ARG' not in content:
        # Find end of TRAINING_MODE block (the "fi" after TRAINING_MODE_ARG)
        m = re.search(
            r'(TRAINING_MODE_ARG="--training-mode \$(?:TRAINING_MODE|\{TRAINING_MODE:-\})"\nfi\n)',
            content,
        )
        if m:
            safe_form = '${PREV_PASSED:-}' if has_set_euo else '$PREV_PASSED'
            insert = (
                f'\n# Incremental reward support\n'
                f'PREV_PASSED_ARG=""\n'
                f'if [ -n "{safe_form}" ]; then\n'
                f'  PREV_PASSED_ARG="--prev-passed $PREV_PASSED"\n'
                f'fi\n'
            )
            content = content[:m.end()] + insert + content[m.end():]
            changes.append("added PREV_PASSED block")

    # =========================================================================
    # Rec 5: Add crash detection — replace `|| true)` with set +e pattern
    # =========================================================================
    # Match patterns like: TEST_OUTPUT=$(cmd 2>&1 || true)
    # But NOT if set +e is already nearby (within 3 lines before)
    def replace_or_true(m):
        full = m.group(0)
        cmd_part = m.group(1)  # everything inside $(...)
        # Remove the || true from the command
        cmd_clean = re.sub(r'\s*\|\|\s*true\s*$', '', cmd_part).strip()
        return (
            f'set +e\n'
            f'TEST_OUTPUT=$({cmd_clean})\n'
            f'TEST_EXIT=$?\n'
            f'set -e'
        )

    if 'TEST_EXIT' not in content:
        # Find: TEST_OUTPUT=$(... || true)  possibly multiline
        pat = re.compile(
            r'TEST_OUTPUT=\$\((.*?\|\|\s*true)\)',
            re.DOTALL,
        )
        new_content = pat.sub(replace_or_true, content)
        if new_content != content:
            content = new_content
            changes.append("added crash detection (set +e/TEST_EXIT)")

    # =========================================================================
    # Rec 6: Change exit 0 → exit 1 on zero tests, add crash check
    # =========================================================================
    # Pattern: after "0.0" > reward.txt in zero-tests block, look for exit 0
    # Replace with crash detection + exit 1

    # First, add crash check before "no tests" message if TEST_EXIT exists
    if 'TEST_EXIT' in content and 'Verifier error' not in content:
        # Find the zero-tests block — typically:
        #   echo "0.0" > /logs/verifier/reward.txt
        #   echo "No tests found..."
        #   exit 0
        # We want to insert crash check between reward.txt write and the message

        # Pattern for zero-tests block (various forms)
        zero_block_pat = re.compile(
            r'(echo\s+"0\.0"\s*>\s*/logs/verifier/reward\.txt\n)'
            r'(\s*echo\s+"(?:No tests|Verifier error)[^"]*"[^\n]*\n'
            r'\s*exit\s+0)',
            re.MULTILINE,
        )
        def add_crash_check(m):
            reward_line = m.group(1)
            rest = m.group(2)
            # Change exit 0 to exit 1
            rest_fixed = rest.replace('exit 0', 'exit 1')
            indent = '  ' if reward_line.startswith('  ') else '    '
            crash_block = (
                f'{indent}if [ "$TEST_EXIT" -ne 0 ]; then\n'
                f'{indent}  echo "Verifier error: test runner failed before any result could be parsed."\n'
                f'{indent}  exit 1\n'
                f'{indent}fi\n'
            )
            return reward_line + crash_block + rest_fixed

        new_content = zero_block_pat.sub(add_crash_check, content)
        if new_content != content:
            content = new_content
            changes.append("added crash check in zero-tests block")
        else:
            # Try alternate pattern with JSON line in between
            zero_block_pat2 = re.compile(
                r'(echo\s+"0\.0"\s*>\s*/logs/verifier/reward\.txt\n)'
                r"(\s*echo\s+'[^']*'\s*>\s*/logs/verifier/results\.json\n)?"
                r'(\s*echo\s+"(?:No tests|Verifier error)[^"]*"[^\n]*\n'
                r'\s*exit\s+0)',
                re.MULTILINE,
            )
            def add_crash_check2(m):
                reward_line = m.group(1)
                json_line = m.group(2) or ''
                rest = m.group(3)
                rest_fixed = rest.replace('exit 0', 'exit 1')
                indent = '  ' if reward_line.startswith('  ') else '    '
                crash_block = (
                    f'{indent}if [ "$TEST_EXIT" -ne 0 ]; then\n'
                    f'{indent}  echo "Verifier error: test runner failed before any result could be parsed."\n'
                    f'{indent}  exit 1\n'
                    f'{indent}fi\n'
                )
                return reward_line + json_line + crash_block + rest_fixed
            new_content = zero_block_pat2.sub(add_crash_check2, content)
            if new_content != content:
                content = new_content
                changes.append("added crash check in zero-tests block (alt)")

    # Even without crash detection, still change exit 0 → exit 1 in zero-tests blocks
    # Look for exit 0 that appears right after "No tests" / "0.0" reward patterns
    if 'TEST_EXIT' not in content:
        # Only change exit 0 in the zero-tests block, not elsewhere
        zero_exit_pat = re.compile(
            r'(echo\s+"0\.0"\s*>\s*/logs/verifier/reward\.txt\n'
            r'(?:.*\n)*?'
            r'\s*)exit\s+0',
        )
        # Simpler: just change exit 0 to exit 1 if it follows reward.txt 0.0
        lines = content.split('\n')
        new_lines = []
        in_zero_block = False
        for line in lines:
            if '0.0' in line and 'reward.txt' in line:
                in_zero_block = True
            if in_zero_block and re.match(r'\s*exit\s+0\s*$', line):
                line = line.replace('exit 0', 'exit 1')
                in_zero_block = False
                if "exit 0 → exit 1" not in changes:
                    changes.append("exit 0 → exit 1 in zero-tests block")
            if in_zero_block and re.match(r'\s*fi\s*$', line):
                in_zero_block = False
            new_lines.append(line)
        content = '\n'.join(new_lines)

    # Also catch remaining exit 0 after "Verifier error" or "No tests"
    lines = content.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        if re.match(r'\s*exit\s+0\s*$', line):
            # Check if previous lines mention "No tests" or "Verifier error" or "0.0"
            context = '\n'.join(lines[max(0, i-3):i])
            if 'No tests' in context or 'Verifier error' in context or '0.0' in context:
                line = line.replace('exit 0', 'exit 1')
                if "exit 0 → exit 1" not in changes:
                    changes.append("exit 0 → exit 1 in zero-tests block")
        new_lines.append(line)
    content = '\n'.join(new_lines)

    # =========================================================================
    # Rec 10b: Add $PREV_PASSED_ARG to scoring.py calls and add JSON output
    # =========================================================================
    if 'PREV_PASSED_ARG' in content:
        # Add $PREV_PASSED_ARG to scoring.py REWARD line if not already there
        scoring_pat = re.compile(
            r'(REWARD=\$\(python3\s+/app/environment/scoring\.py\s+--passed\s+"\$\w+"\s+--total\s+"\$\w+"\s+--tier\s+"[^"]+"\s+--cwd\s+/app\s+\$TRAINING_MODE_ARG)'
            r'(?!\s+\$PREV_PASSED_ARG)'
            r'(\s+2>/dev/null)',
        )
        new_content = scoring_pat.sub(r'\1 $PREV_PASSED_ARG\2', content)
        if new_content != content:
            content = new_content
            changes.append("added $PREV_PASSED_ARG to scoring.py call")

    # Add JSON output line after REWARD line (if not already present)
    if 'results.json' not in content and 'RESULTS_JSON' not in content:
        # Find the REWARD scoring.py line and duplicate with --json
        reward_line_pat = re.compile(
            r'^(REWARD=\$\(python3\s+/app/environment/scoring\.py\s+--passed\s+"\$(\w+)"\s+--total\s+"\$(\w+)"\s+--tier\s+"([^"]+)"\s+--cwd\s+/app\s+\$TRAINING_MODE_ARG(?:\s+\$PREV_PASSED_ARG)?\s+2>/dev/null\s*\|\|\s*echo\s+"0\.0"\))',
            re.MULTILINE,
        )
        m = reward_line_pat.search(content)
        if m:
            passed_var = m.group(2)
            total_var = m.group(3)
            tier = m.group(4)
            prev_arg = ' $PREV_PASSED_ARG' if 'PREV_PASSED_ARG' in content else ''
            json_line = f'RESULTS_JSON=$(python3 /app/environment/scoring.py --passed "${passed_var}" --total "${total_var}" --tier "{tier}" --cwd /app $TRAINING_MODE_ARG{prev_arg} --json 2>/dev/null || echo \'{{}}\')'
            content = content[:m.end()] + '\n' + json_line + content[m.end():]
            changes.append("added JSON scoring.py call")

    # Add results.json write after reward.txt write
    if 'RESULTS_JSON' in content and 'results.json' not in content:
        content = content.replace(
            'echo "$REWARD" > /logs/verifier/reward.txt',
            'echo "$REWARD" > /logs/verifier/reward.txt\necho "$RESULTS_JSON" > /logs/verifier/results.json',
        )
        changes.append("added results.json write")

    # =========================================================================
    # Rec 10c: Add incremental info block at end (if PREV_PASSED_ARG exists)
    # =========================================================================
    if 'PREV_PASSED_ARG' in content and 'Progress:' not in content and 'Regression:' not in content:
        # Find the last echo line (summary line) and add after it
        safe_form = '${PREV_PASSED:-}' if has_set_euo else '$PREV_PASSED'
        incremental_block = (
            f'\n# Show incremental info if available\n'
            f'if [ -n "{safe_form}" ]; then\n'
            f'  DELTA=$((PASSED - PREV_PASSED))\n'
            f'  if [ "$DELTA" -gt 0 ]; then\n'
            f'    echo "Progress: +$DELTA newly passing tests"\n'
            f'  elif [ "$DELTA" -lt 0 ]; then\n'
            f'    echo "Regression: $DELTA tests now failing"\n'
            f'  fi\n'
            f'fi\n'
        )
        # Append at end (before final newline)
        content = content.rstrip('\n') + '\n' + incremental_block
        changes.append("added incremental info block")

    # Write back if changed
    if content != original:
        path.write_text(content)

    return changes


def main():
    langs = ["python", "js", "go", "ruby", "java", "kotlin", "csharp", "rust", "cpp"]
    total_changed = 0
    total_envs = 0

    for lang in langs:
        lang_path = ROOT / lang
        if not lang_path.is_dir():
            continue
        for env_name in sorted(os.listdir(lang_path)):
            test_sh = lang_path / env_name / "tests" / "test.sh"
            if not test_sh.exists():
                continue
            total_envs += 1
            changes = transform_test_sh(test_sh)
            if changes:
                total_changed += 1
                print(f"OK:   {lang}/{env_name}")
                for c in changes:
                    print(f"      - {c}")
            else:
                print(f"SKIP: {lang}/{env_name} (no changes needed)")

    print(f"\n{'='*60}")
    print(f"Modified: {total_changed}/{total_envs} test.sh files")


if __name__ == "__main__":
    main()
