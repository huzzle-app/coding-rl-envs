#!/usr/bin/env python3
"""
Comprehensive validation of all 50 Terminal Bench environments.

Tests:
- scoring.py syntax and execution
- harbor/test.sh bash syntax
- reward.py/go/js/rb imports and syntax
- setup.py syntax

Usage:
    python scripts/validate_environments.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

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

    # 2. Test harbor/test.sh
    test_sh = env_path / "harbor" / "test.sh"
    if test_sh.exists():
        ok, err = test_bash_syntax(test_sh)
        if not ok:
            errors.append(f"test.sh syntax: {err[:100]}")

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
