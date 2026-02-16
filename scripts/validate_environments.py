#!/usr/bin/env python3
"""
Comprehensive validation of all 50 Terminal Bench environments.

Tests:
- scoring.py syntax and execution
- tests/test.sh bash syntax
- reward.py/go/js/rb imports and syntax
- setup.py syntax
- Tier & variable validation (Rec 1)
- Reward threshold matching (Rec 2)
- Ruby template consistency (Rec 3)

Usage:
    python scripts/validate_environments.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Canonical tier tables from scoring.py REWARD_TABLES
# ---------------------------------------------------------------------------
EXPECTED_TIER_TABLES: Dict[str, Dict[str, List[float]]] = {
    "senior": {
        "thresholds": [0.50, 0.75, 0.90, 1.0],
        "rewards": [0.15, 0.35, 0.65, 1.0],
    },
    "principal": {
        "thresholds": [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0],
        "rewards": [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0],
    },
    "distinguished": {
        "thresholds": [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0],
        "rewards": [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0],
    },
    "ultra-principal": {
        "thresholds": [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0],
        "rewards": [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0],
    },
    "hyper-principal": {
        "thresholds": [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0],
        "rewards": [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0],
    },
    "apex-principal": {
        "thresholds": [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0],
        "rewards": [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(cmd, cwd=None, timeout=10):
    """Run command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stderr or result.stdout
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)

def test_python_syntax(filepath):
    """Test Python file for syntax errors."""
    ok, out = run_cmd(f'python3 -m py_compile "{filepath}"')
    return ok, out if not ok else None

def test_python_import(env_path, module):
    """Test Python module import."""
    ok, out = run_cmd(f'python3 -c "import {module}"', cwd=env_path)
    return ok, out if not ok else None

def test_bash_syntax(filepath):
    """Test bash script for syntax errors."""
    ok, out = run_cmd(f'bash -n "{filepath}"')
    return ok, out if not ok else None

def test_go_syntax(filepath):
    """Test Go file syntax (basic brace matching)."""
    try:
        with open(filepath) as f:
            content = f.read()
        stack = []
        pairs = {'{': '}', '(': ')', '[': ']'}
        in_string = False
        in_comment = False
        prev_char = ''
        for i, c in enumerate(content):
            if in_comment:
                if c == '\n' and prev_char != '\\':
                    in_comment = False
            elif in_string:
                if c == '"' and prev_char != '\\':
                    in_string = False
            elif c == '/' and prev_char == '/':
                in_comment = True
            elif c == '"':
                in_string = True
            elif c in pairs:
                stack.append(pairs[c])
            elif c in pairs.values():
                if not stack or stack.pop() != c:
                    return False, f"Mismatched bracket at char {i}"
            prev_char = c
        if stack:
            return False, f"Unclosed brackets: {stack}"
        return True, None
    except Exception as e:
        return False, str(e)

def test_js_syntax(filepath):
    """Test JavaScript syntax."""
    ok, out = run_cmd(f'node --check "{filepath}"')
    if not ok and "command not found" in out:
        return True, None
    return ok, out if not ok else None

def test_ruby_syntax(filepath):
    """Test Ruby syntax."""
    ok, out = run_cmd(f'ruby -c "{filepath}"')
    if not ok and "command not found" in out:
        return True, None
    return ok, out if not ok else None

# ---------------------------------------------------------------------------
# Rec 1: Tier & Variable Validation
# ---------------------------------------------------------------------------

def extract_tier_from_test_sh(content: str) -> Optional[str]:
    """Extract --tier "VALUE" from test.sh content."""
    m = re.search(r'--tier\s+"([^"]+)"', content)
    if m:
        return m.group(1)
    m = re.search(r"--tier\s+'([^']+)'", content)
    if m:
        return m.group(1)
    m = re.search(r'--tier\s+(\S+)', content)
    if m:
        return m.group(1)
    return None


def has_set_u(content: str) -> bool:
    """Check if script uses set -u (via set -euo pipefail, set -u, etc.)."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('#'):
            continue
        if re.match(r'set\s+.*-[a-z]*u', line):
            return True
    return False


def _find_guarded_vars(content: str) -> set:
    """Find vars that are guarded by if [ -n "${VAR:-}" ] blocks.

    Inside such blocks, bare $VAR is safe because the if condition
    ensures the variable is set before the block executes.
    """
    guarded = set()
    lines = content.splitlines()
    guard_var = None
    depth = 0
    for line in lines:
        stripped = line.strip()
        # Detect guard pattern: if [ -n "${VAR:-}" ]; then
        m = re.search(r'if\s+\[\s+-n\s+"\$\{(\w+):-[^}]*\}"\s+\]', stripped)
        if m:
            guard_var = m.group(1)
            depth = 1
            continue
        if guard_var:
            if re.match(r'(if|for|while)\b', stripped):
                depth += 1
            if stripped == 'fi':
                depth -= 1
                if depth <= 0:
                    guard_var = None
                    depth = 0
                continue
            if depth > 0:
                guarded.add(guard_var)
    return guarded


def validate_set_u_safety(content: str) -> List[str]:
    """Check that env vars under set -u use ${VAR:-} form."""
    errors = []
    if not has_set_u(content):
        return errors

    # Find all variable assignments in the script
    defined_vars = set()
    for m in re.finditer(r'^(\w+)=', content, re.MULTILINE):
        defined_vars.add(m.group(1))

    # Find vars guarded by if [ -n "${VAR:-}" ] blocks
    guarded_vars = _find_guarded_vars(content)

    # Environment variables commonly referenced but not defined in script
    env_vars_to_check = ['TRAINING_MODE', 'PREV_PASSED', 'TEST_FILE', 'TEST_FAST', 'PARSE_ERRORS']

    for var in env_vars_to_check:
        if var in defined_vars:
            continue
        # Look for bare $VAR references (not ${VAR:-...} form)
        bare_pat = re.compile(r'\$' + var + r'(?!\w|\{)')
        safe_pat = re.compile(r'\$\{' + var + r':-[^}]*\}')

        # Track whether we're inside this var's guard block
        in_guard = False
        guard_depth = 0
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            # Check for guard entry
            if re.search(r'if\s+\[\s+-n\s+"\$\{' + var + r':-[^}]*\}"\s+\]', stripped):
                in_guard = True
                guard_depth = 1
                # The guard line itself should use safe form (check it)
                if bare_pat.search(stripped) and not safe_pat.search(stripped):
                    errors.append(f"set -u safety: bare ${var} on line {i} (use ${{{var}:-}})")
                continue
            if in_guard:
                if re.match(r'(if|for|while)\b', stripped):
                    guard_depth += 1
                if stripped == 'fi':
                    guard_depth -= 1
                    if guard_depth <= 0:
                        in_guard = False
                        guard_depth = 0
                    continue
                # Inside guard: bare $VAR is safe, skip
                continue
            # Outside guard: flag bare $VAR
            if bare_pat.search(stripped) and not safe_pat.search(stripped):
                errors.append(f"set -u safety: bare ${var} on line {i} (use ${{{var}:-}})")
    return errors


def validate_scoring_call_variables(content: str) -> List[str]:
    """Verify variables used in scoring.py call line are defined."""
    errors = []
    # Find the scoring.py call line(s)
    for i, line in enumerate(content.splitlines(), 1):
        if 'scoring.py' not in line:
            continue
        if line.strip().startswith('#'):
            continue
        # Extract all $VAR references (not $(...) subshells)
        var_refs = re.findall(r'\$(\w+)', line)
        # Filter out subshell captures like $(python3 ...)
        var_refs = [v for v in var_refs if v not in ('python3',)]
        # Check each is defined somewhere before this line
        preceding = '\n'.join(content.splitlines()[:i])
        for var in var_refs:
            # Check if defined via VAR= or for VAR in ...
            if not re.search(rf'^{var}=', preceding, re.MULTILINE) and \
               not re.search(rf'\bfor\s+{var}\b', preceding, re.MULTILINE):
                # Some built-in vars are fine
                if var in ('HOME', 'PATH', 'PWD', 'USER', 'SHELL'):
                    continue
                # Vars from command substitution on same line are fine
                if re.search(rf'{var}=\$\(', preceding, re.MULTILINE):
                    continue
                # Check if it's a parameter expansion with default
                if re.search(rf'\$\{{{var}:-', line):
                    continue
                errors.append(f"scoring.py call on line {i}: ${var} may be undefined")
    return errors

# ---------------------------------------------------------------------------
# Rec 2: Reward Threshold Validation
# ---------------------------------------------------------------------------

def _extract_floats_from_bracket(content: str, start_pos: int) -> Optional[List[float]]:
    """Extract float array from [...] or {...} starting at start_pos."""
    bracket_stack = 0
    open_char = None
    close_char = None
    arr_start = None
    for i in range(start_pos, min(start_pos + 500, len(content))):
        c = content[i]
        if c in '[{' and open_char is None:
            open_char = c
            close_char = ']' if c == '[' else '}'
            arr_start = i
            bracket_stack = 1
        elif open_char and c == open_char:
            bracket_stack += 1
        elif open_char and c == close_char:
            bracket_stack -= 1
            if bracket_stack == 0:
                arr_text = content[arr_start:i + 1]
                floats = re.findall(r'\d+\.\d+', arr_text)
                return [float(f) for f in floats]
    return None


def parse_reward_thresholds_python(content: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Parse thresholds and rewards from Python reward file."""
    thresholds = None
    rewards = None

    # Pattern 1: module-level THRESHOLDS = [...] and REWARDS = [...]
    m = re.search(r'^THRESHOLDS\s*=\s*', content, re.MULTILINE)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'^REWARDS\s*=\s*', content, re.MULTILINE)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    if thresholds and rewards:
        return thresholds, rewards

    # Pattern 2: self.pass_thresholds = [...] and self.threshold_rewards = [...]
    m = re.search(r'self\.pass_thresholds\s*=\s*', content)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'self\.threshold_rewards\s*=\s*', content)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    if thresholds and rewards:
        return thresholds, rewards

    # Pattern 3: dataclass field(default_factory=lambda: [...])
    m = re.search(r'pass_thresholds.*?default_factory\s*=\s*lambda\s*:\s*', content, re.DOTALL)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'threshold_rewards.*?default_factory\s*=\s*lambda\s*:\s*', content, re.DOTALL)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    if thresholds and rewards:
        return thresholds, rewards

    # Pattern 4: PASS_THRESHOLDS = [...] (alternate name)
    m = re.search(r'PASS_THRESHOLDS\s*=\s*', content)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'THRESHOLD_REWARDS\s*=\s*', content)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    if thresholds and rewards:
        return thresholds, rewards

    # Pattern 5: REWARD_THRESHOLDS = [...]
    m = re.search(r'REWARD_THRESHOLDS\s*=\s*', content)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    if thresholds and rewards:
        return thresholds, rewards

    return thresholds, rewards


def parse_reward_thresholds_js(content: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Parse thresholds and rewards from JavaScript reward file."""
    thresholds = None
    rewards = None

    m = re.search(r'(?:const|let|var)\s+PASS_THRESHOLDS\s*=\s*', content)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'(?:const|let|var)\s+THRESHOLD_REWARDS\s*=\s*', content)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    return thresholds, rewards


def parse_reward_thresholds_go(content: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Parse thresholds and rewards from Go reward file."""
    thresholds = None
    rewards = None

    # var passThresholds = []float64{...}
    m = re.search(r'passThresholds\s*(?:=\s*\[\]float64|:\s*\[\]float64)', content)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'thresholdRewards\s*(?:=\s*\[\]float64|:\s*\[\]float64)', content)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    return thresholds, rewards


def parse_reward_thresholds_ruby(content: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Parse thresholds and rewards from Ruby reward file."""
    thresholds = None
    rewards = None

    m = re.search(r'PASS_THRESHOLDS\s*=\s*', content)
    if m:
        thresholds = _extract_floats_from_bracket(content, m.end() - 1)
    m = re.search(r'THRESHOLD_REWARDS\s*=\s*', content)
    if m:
        rewards = _extract_floats_from_bracket(content, m.end() - 1)
    return thresholds, rewards


def parse_reward_thresholds(env_path: Path, lang: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """Parse reward thresholds from reward file, dispatching by language."""
    # Determine which reward file to read
    if lang in ("python", "rust", "cpp", "java", "kotlin", "csharp"):
        reward_file = env_path / "environment" / "reward.py"
        parser = parse_reward_thresholds_python
    elif lang == "js":
        reward_file = env_path / "environment" / "reward.js"
        parser = parse_reward_thresholds_js
    elif lang == "go":
        reward_file = env_path / "environment" / "reward.go"
        parser = parse_reward_thresholds_go
    elif lang == "ruby":
        reward_file = env_path / "environment" / "reward.rb"
        parser = parse_reward_thresholds_ruby
    else:
        return None, None

    if not reward_file.exists():
        return None, None

    try:
        content = reward_file.read_text()
    except Exception:
        return None, None

    return parser(content)


def _normalize_ascending(arr: List[float]) -> List[float]:
    """Normalize array to ascending order (handles descending like aetherops)."""
    if len(arr) >= 2 and arr[0] > arr[-1]:
        return list(reversed(arr))
    return arr


def _floats_match(a: List[float], b: List[float], tol: float = 0.001) -> bool:
    """Check if two float lists match within tolerance."""
    if len(a) != len(b):
        return False
    return all(abs(x - y) < tol for x, y in zip(a, b))


def validate_reward_thresholds(env_path: Path, lang: str, tier: Optional[str]) -> List[str]:
    """Validate reward file thresholds match expected tier table."""
    errors = []
    if tier is None:
        return errors
    if tier not in EXPECTED_TIER_TABLES:
        errors.append(f"reward thresholds: unknown tier '{tier}'")
        return errors

    thresholds, rewards = parse_reward_thresholds(env_path, lang)
    if thresholds is None or rewards is None:
        # Can't parse - not necessarily an error (some envs may use different patterns)
        return errors

    expected = EXPECTED_TIER_TABLES[tier]
    norm_thresholds = _normalize_ascending(thresholds)
    norm_rewards = _normalize_ascending(rewards)

    if not _floats_match(norm_thresholds, expected["thresholds"]):
        errors.append(
            f"reward thresholds mismatch for tier '{tier}': "
            f"got {norm_thresholds}, expected {expected['thresholds']}"
        )
    if not _floats_match(norm_rewards, expected["rewards"]):
        errors.append(
            f"reward rewards mismatch for tier '{tier}': "
            f"got {norm_rewards}, expected {expected['rewards']}"
        )
    return errors

# ---------------------------------------------------------------------------
# Rec 3: Ruby Template Validation
# ---------------------------------------------------------------------------

def validate_ruby_test_sh(content: str) -> List[str]:
    """Validate Ruby test.sh for RSpec vs Minitest parser consistency."""
    errors = []

    uses_rspec = 'rspec' in content.lower() or 'bundle exec rspec' in content
    uses_minitest = 'run_all.rb' in content or 'ruby -I' in content

    # Check parser matches test runner
    parses_examples = bool(re.search(r"'examples?'|examples?", content) and
                          re.search(r"grep.*examples?", content))
    parses_runs = bool(re.search(r"'runs?'|runs?", content) and
                       re.search(r"grep.*runs?", content))

    if uses_rspec and parses_runs and not parses_examples:
        errors.append("ruby test.sh: uses RSpec but parses Minitest output (runs/assertions)")
    if uses_minitest and parses_examples and not parses_runs:
        errors.append("ruby test.sh: uses Minitest but parses RSpec output (examples/failures)")

    return errors

# ---------------------------------------------------------------------------
# Rec 4: REWARD Initialization Validation
# ---------------------------------------------------------------------------

def validate_reward_init(content: str) -> List[str]:
    """Check that $REWARD is initialized before conditional use."""
    errors = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        # Look for `if [ -z "$REWARD" ]` pattern
        if re.search(r'if\s+\[\s+-z\s+"\$REWARD"\s+\]', line):
            # Check if REWARD="" is defined before this line
            preceding = '\n'.join(lines[:i])
            if 'REWARD=""' not in preceding and "REWARD=''" not in preceding:
                errors.append(f"Rec 4: $REWARD used in test on line {i+1} without prior initialization")
    return errors

# ---------------------------------------------------------------------------
# Rec 5: Crash Detection Validation
# ---------------------------------------------------------------------------

def validate_crash_detection(content: str) -> List[str]:
    """Check that test.sh uses proper crash detection (TEST_EXIT)."""
    errors = []
    if 'TEST_EXIT' not in content:
        # Check if there's a test runner invocation with || true
        if re.search(r'TEST_OUTPUT=\$\(.*\|\|\s*true\)', content, re.DOTALL):
            errors.append("Rec 5: test runner uses || true without crash detection (missing TEST_EXIT)")
    return errors

# ---------------------------------------------------------------------------
# Rec 6: Exit Code Validation
# ---------------------------------------------------------------------------

def validate_exit_on_zero_tests(content: str) -> List[str]:
    """Check that test.sh exits with 1 (not 0) when no tests found."""
    errors = []
    lines = content.splitlines()
    in_zero_block = False
    for i, line in enumerate(lines):
        if '0.0' in line and 'reward.txt' in line:
            in_zero_block = True
        if in_zero_block and re.match(r'\s*exit\s+0\s*$', line):
            errors.append(f"Rec 6: exit 0 on line {i+1} in zero-tests block (should be exit 1)")
            in_zero_block = False
        if in_zero_block and (re.match(r'\s*fi\s*$', line) or 'exit 1' in line):
            in_zero_block = False
    return errors

# ---------------------------------------------------------------------------
# Rec 8: Reward File Existence
# ---------------------------------------------------------------------------

def validate_reward_file_exists(env_path: Path, lang: str) -> List[str]:
    """Check that the reward file exists."""
    errors = []
    if lang in ("python", "rust", "cpp", "java", "kotlin", "csharp"):
        reward_file = env_path / "environment" / "reward.py"
    elif lang == "js":
        reward_file = env_path / "environment" / "reward.js"
    elif lang == "go":
        reward_file = env_path / "environment" / "reward.go"
    elif lang == "ruby":
        reward_file = env_path / "environment" / "reward.rb"
    else:
        return errors
    if not reward_file.exists():
        errors.append(f"Rec 8: missing reward file {reward_file.name}")
    return errors

# ---------------------------------------------------------------------------
# Rec 9: Kotlin/Java XML Path Validation
# ---------------------------------------------------------------------------

def validate_xml_report_paths(content: str, lang: str) -> List[str]:
    """Check Kotlin/Java scripts use portable find-based XML path."""
    errors = []
    if lang not in ("kotlin",):
        return errors
    # Flag hardcoded glob paths (not using find)
    if re.search(r'for\s+\w+\s+in\s+build/', content) and 'find' not in content:
        errors.append("Rec 9: hardcoded XML report path (use 'find . -path' for portability)")
    return errors

# ---------------------------------------------------------------------------
# Rec 10: PREV_PASSED and JSON Output
# ---------------------------------------------------------------------------

def validate_training_features(content: str) -> List[str]:
    """Check that test.sh has PREV_PASSED support and JSON output."""
    errors = []
    if 'PREV_PASSED_ARG' not in content:
        errors.append("Rec 10: missing PREV_PASSED support")
    if 'results.json' not in content:
        errors.append("Rec 10: missing JSON results output")
    return errors

# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def validate_environment(lang, env_name, env_path):
    """Validate a single environment."""
    errors = []

    # 1. Test scoring.py
    scoring_py = env_path / "environment" / "scoring.py"
    if scoring_py.exists():
        ok, err = test_python_syntax(scoring_py)
        if not ok:
            errors.append(f"scoring.py syntax: {err[:100]}")
        else:
            ok, err = run_cmd(f'python3 environment/scoring.py --help', cwd=env_path)
            if not ok:
                errors.append(f"scoring.py run: {err[:100]}")

    # 2. Test tests/test.sh (also check harbor/test.sh for legacy)
    test_sh = env_path / "tests" / "test.sh"
    if not test_sh.exists():
        test_sh = env_path / "harbor" / "test.sh"
    test_sh_content = None
    tier = None
    if test_sh.exists():
        ok, err = test_bash_syntax(test_sh)
        if not ok:
            errors.append(f"test.sh syntax: {err[:100]}")
        try:
            test_sh_content = test_sh.read_text()
        except Exception:
            pass

    # Rec 1: Tier & variable validation
    if test_sh_content:
        tier = extract_tier_from_test_sh(test_sh_content)
        if tier is None:
            errors.append("test.sh: no --tier argument found in scoring.py call")
        elif tier not in EXPECTED_TIER_TABLES:
            errors.append(f"test.sh: unknown --tier value '{tier}'")

        errors.extend(validate_set_u_safety(test_sh_content))
        errors.extend(validate_scoring_call_variables(test_sh_content))

    # Rec 2: Reward threshold validation
    errors.extend(validate_reward_thresholds(env_path, lang, tier))

    # Rec 3: Ruby template validation
    if lang == "ruby" and test_sh_content:
        errors.extend(validate_ruby_test_sh(test_sh_content))

    # Rec 4: REWARD initialization
    if test_sh_content:
        errors.extend(validate_reward_init(test_sh_content))

    # Rec 5: Crash detection
    if test_sh_content:
        errors.extend(validate_crash_detection(test_sh_content))

    # Rec 6: Exit code on zero tests
    if test_sh_content:
        errors.extend(validate_exit_on_zero_tests(test_sh_content))

    # Rec 8: Reward file existence
    errors.extend(validate_reward_file_exists(env_path, lang))

    # Rec 9: XML report path portability
    if test_sh_content:
        errors.extend(validate_xml_report_paths(test_sh_content, lang))

    # Rec 10: Training features
    if test_sh_content:
        errors.extend(validate_training_features(test_sh_content))

    # 3. Language-specific tests
    if lang == "python":
        ok, err = test_python_import(env_path, "environment.reward")
        if not ok:
            errors.append(f"reward.py import: {err[:150]}")
        setup_py = env_path / "environment" / "setup.py"
        if setup_py.exists():
            ok, err = test_python_syntax(setup_py)
            if not ok:
                errors.append(f"setup.py syntax: {err[:100]}")

    elif lang == "go":
        reward_go = env_path / "environment" / "reward.go"
        if reward_go.exists():
            ok, err = test_go_syntax(reward_go)
            if not ok:
                errors.append(f"reward.go syntax: {err[:100]}")

    elif lang == "js":
        reward_js = env_path / "environment" / "reward.js"
        if reward_js.exists():
            ok, err = test_js_syntax(reward_js)
            if not ok:
                errors.append(f"reward.js syntax: {err[:100]}")

    elif lang == "ruby":
        reward_rb = env_path / "environment" / "reward.rb"
        if reward_rb.exists():
            ok, err = test_ruby_syntax(reward_rb)
            if not ok:
                errors.append(f"reward.rb syntax: {err[:100]}")

    elif lang in ["java", "kotlin", "csharp", "cpp", "rust"]:
        reward_py = env_path / "environment" / "reward.py"
        if reward_py.exists():
            ok, err = test_python_import(env_path, "environment.reward")
            if not ok:
                errors.append(f"reward.py import: {err[:150]}")
        setup_py = env_path / "environment" / "setup.py"
        if setup_py.exists():
            ok, err = test_python_syntax(setup_py)
            if not ok:
                errors.append(f"setup.py syntax: {err[:100]}")

    return errors

def main():
    """Run validation on all environments."""
    results = {"passed": [], "failed": []}

    langs = ["python", "js", "go", "ruby", "java", "kotlin", "csharp", "rust", "cpp"]

    for lang in langs:
        lang_path = ROOT / lang
        if not lang_path.is_dir():
            continue

        for env_name in sorted(os.listdir(lang_path)):
            env_path = lang_path / env_name
            if not env_path.is_dir():
                continue
            if not (env_path / "environment").is_dir():
                continue

            errors = validate_environment(lang, env_name, env_path)

            if errors:
                results["failed"].append((f"{lang}/{env_name}", errors))
                print(f"FAIL: {lang}/{env_name}")
                for err in errors:
                    print(f"      {err}")
            else:
                results["passed"].append(f"{lang}/{env_name}")
                print(f"OK:   {lang}/{env_name}")

    print(f"\n{'='*60}")
    print(f"PASSED: {len(results['passed'])}")
    print(f"FAILED: {len(results['failed'])}")

    if results["failed"]:
        print(f"\nFailed environments:")
        for env, _ in results["failed"]:
            print(f"  - {env}")
        return 1

    print("\nAll environments validated successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
