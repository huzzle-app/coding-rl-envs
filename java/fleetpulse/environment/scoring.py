#!/usr/bin/env python3
"""
Multi-Solution Scoring Module

Rewards surgical, minimal fixes over large changes.
Works standalone - no dependencies on environment-specific code.

Usage:
    python scoring.py --passed 9000 --total 10000 --cwd /app --tier apex-principal
    python scoring.py --passed 9000 --total 10000 --training-mode linear  # Dense rewards
    python scoring.py --passed 9000 --total 10000 --prev-passed 8500  # Incremental rewards
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Training mode options
TRAINING_MODES = {
    "linear": lambda x: x,                    # Direct 1:1 mapping
    "sublinear": lambda x: x ** 0.7,          # Rewards early progress more
    "smooth": lambda x: 3 * x**2 - 2 * x**3,  # Smooth S-curve (Hermite)
}
DEFAULT_TRAINING_MODE = "linear"

# Incremental reward settings
NEWLY_PASSING_BONUS = 0.01   # Bonus per newly passing test (normalized)
REGRESSION_PENALTY = 0.02    # Penalty per regressed test (normalized)

# Reward tables by tier (used in evaluation mode)
REWARD_TABLES = {
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

# Diff size scoring (smaller = better)
DIFF_SIZE_THRESHOLDS = [
    (10, 0.05),   # <= 10 lines: max bonus
    (25, 0.04),   # <= 25 lines: high bonus
    (50, 0.03),   # <= 50 lines: medium bonus
    (100, 0.02),  # <= 100 lines: low bonus
    (200, 0.01),  # <= 200 lines: minimal bonus
]

# Surgical precision (avg lines per hunk)
PRECISION_THRESHOLDS = [
    (3, 0.03),   # <= 3 lines/hunk: very surgical
    (5, 0.02),   # <= 5 lines/hunk: surgical
    (10, 0.01),  # <= 10 lines/hunk: moderate
]

# Patterns indicating lower quality fixes
DEBUG_PATTERNS = [
    r'\bprint\s*\(', r'\bconsole\.log\s*\(', r'\bSystem\.out\.print',
    r'\bfmt\.Print', r'\bputs\s+', r'\bdebug!', r'\bdbg!',
]
TODO_PATTERNS = [r'#\s*TODO', r'//\s*TODO', r'#\s*FIXME', r'//\s*FIXME']
TEST_FILE_PATTERNS = [r'test[s]?/', r'_test\.', r'\.test\.', r'Test\.java$', r'_spec\.']

# Error parsing patterns by language
ERROR_PATTERNS = {
    "python": {
        "test_name": r'FAILED\s+([\w./]+::[\w_]+)',
        "assertion": r'AssertionError:\s*(.+?)(?:\n|$)',
        "expected": r'assert\s+.+?==\s*(.+?)(?:\n|$)|Expected:\s*(.+?)(?:\n|$)',
        "actual": r'assert\s+(.+?)\s*==|Actual:\s*(.+?)(?:\n|$)',
        "file_line": r'File\s+"([^"]+)",\s*line\s+(\d+)',
    },
    "javascript": {
        "test_name": r'✖\s+(.+?)(?:\n|$)|not ok\s+\d+\s+-\s+(.+?)(?:\n|$)',
        "assertion": r'AssertionError.*?:\s*(.+?)(?:\n|$)',
        "expected": r'expected:\s*(.+?)(?:\n|$)',
        "actual": r'actual:\s*(.+?)(?:\n|$)',
        "file_line": r'at\s+.+?\(([^:]+):(\d+):\d+\)',
    },
    "go": {
        "test_name": r'---\s+FAIL:\s+([\w/]+)',
        "assertion": r'Error:\s*(.+?)(?:\n|$)',
        "expected": r'expected:\s*(.+?)(?:\n|$)|want:\s*(.+?)(?:\n|$)',
        "actual": r'got:\s*(.+?)(?:\n|$)|actual:\s*(.+?)(?:\n|$)',
        "file_line": r'(\w+\.go):(\d+):',
    },
    "ruby": {
        "test_name": r'rspec\s+(.+?)(?:\n|$)|Failure.*?:\s+(.+?)(?:\n|$)',
        "assertion": r'expected:\s*(.+?)(?:\n|$)',
        "expected": r'expected:\s*(.+?)(?:\n|$)',
        "actual": r'got:\s*(.+?)(?:\n|$)',
        "file_line": r'#\s+([^:]+):(\d+)',
    },
    "rust": {
        "test_name": r'test\s+([\w:]+)\s+\.\.\.\s+FAILED',
        "assertion": r"assertion.*?failed:\s*(.+?)(?:\n|$)|panicked at '([^']+)'",
        "expected": r'left:\s*`([^`]+)`',
        "actual": r'right:\s*`([^`]+)`',
        "file_line": r'(\w+\.rs):(\d+):(\d+)',
    },
}


@dataclass
class TestFailure:
    """Structured representation of a test failure."""
    test_name: str
    error_type: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "test": self.test_name,
            "error": self.error_type,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "file": self.file,
            "line": self.line,
        }


def parse_test_failures(output: str, language: str = "python") -> List[TestFailure]:
    """
    Parse test output into structured failure objects.

    Args:
        output: Raw test output string
        language: Language to use for parsing (python, javascript, go, ruby, rust)

    Returns:
        List of TestFailure objects
    """
    patterns = ERROR_PATTERNS.get(language, ERROR_PATTERNS["python"])
    failures = []

    # Find all test names that failed
    test_matches = re.findall(patterns["test_name"], output, re.MULTILINE)
    test_names = [m if isinstance(m, str) else next(x for x in m if x) for m in test_matches]

    for test_name in test_names:
        # Try to extract context around this failure
        # Look for the failure block
        failure = TestFailure(
            test_name=test_name,
            error_type="AssertionError",
            message="Test failed",
        )

        # Try to find assertion message
        assertion_match = re.search(patterns["assertion"], output)
        if assertion_match:
            msg = assertion_match.group(1) or (assertion_match.group(2) if assertion_match.lastindex > 1 else None)
            if msg:
                failure.message = msg.strip()[:200]  # Truncate long messages

        # Try to find expected value
        expected_match = re.search(patterns["expected"], output)
        if expected_match:
            exp = expected_match.group(1) or (expected_match.group(2) if expected_match.lastindex > 1 else None)
            if exp:
                failure.expected = exp.strip()[:100]

        # Try to find actual value
        actual_match = re.search(patterns["actual"], output)
        if actual_match:
            act = actual_match.group(1) or (actual_match.group(2) if actual_match.lastindex > 1 else None)
            if act:
                failure.actual = act.strip()[:100]

        # Try to find file and line
        file_match = re.search(patterns["file_line"], output)
        if file_match:
            failure.file = file_match.group(1)
            try:
                failure.line = int(file_match.group(2))
            except (ValueError, IndexError):
                pass

        failures.append(failure)

    return failures


def format_failures_json(failures: List[TestFailure]) -> str:
    """Format test failures as JSON string."""
    return json.dumps([f.to_dict() for f in failures], indent=2)


@dataclass
class SolutionMetrics:
    """Metrics for evaluating solution quality."""
    total_lines_changed: int
    files_modified: int
    hunks_count: int
    avg_hunk_size: float
    modifies_test_files: bool
    adds_debug_code: bool
    adds_todo_comments: bool
    diff_size_score: float
    surgical_precision_score: float
    quality_score: float

    @property
    def total_bonus(self) -> float:
        return self.diff_size_score + self.surgical_precision_score + self.quality_score


def sparse_reward(pass_rate: float, tier: str = "principal") -> float:
    """Calculate base reward from pass rate using tier thresholds."""
    table = REWARD_TABLES.get(tier, REWARD_TABLES["principal"])
    thresholds = table["thresholds"]
    rewards = table["rewards"]
    for threshold, reward in reversed(list(zip(thresholds, rewards))):
        if pass_rate >= threshold:
            return reward
    return 0.0


def training_reward(pass_rate: float, mode: str = DEFAULT_TRAINING_MODE) -> float:
    """
    Calculate dense reward for training.

    Unlike sparse_reward which uses step functions with dead zones,
    training_reward provides continuous gradient signal from any pass rate.

    Modes:
        - linear: Direct 1:1 mapping (pass_rate = reward)
        - sublinear: pass_rate^0.7 - rewards early progress more
        - smooth: Hermite curve - S-shaped, smooth at endpoints
    """
    fn = TRAINING_MODES.get(mode, TRAINING_MODES[DEFAULT_TRAINING_MODE])
    return fn(min(1.0, max(0.0, pass_rate)))


def incremental_reward(
    passed: int,
    total: int,
    prev_passed: int,
    prev_total: Optional[int] = None,
) -> Dict:
    """
    Calculate incremental reward based on test deltas.

    Rewards newly passing tests and penalizes regressions.
    This provides more granular feedback than just total pass rate.

    Args:
        passed: Current number of passing tests
        total: Current total tests
        prev_passed: Previous number of passing tests
        prev_total: Previous total tests (defaults to current total)

    Returns:
        Dict with newly_passing, regressions, and incremental_bonus
    """
    if prev_total is None:
        prev_total = total

    # Calculate deltas
    newly_passing = max(0, passed - prev_passed)
    regressions = max(0, prev_passed - passed)

    # Normalize by total tests
    if total > 0:
        bonus = (newly_passing * NEWLY_PASSING_BONUS) / total
        penalty = (regressions * REGRESSION_PENALTY) / total
    else:
        bonus = 0.0
        penalty = 0.0

    incremental_bonus = bonus - penalty

    return {
        "newly_passing": newly_passing,
        "regressions": regressions,
        "incremental_bonus": round(incremental_bonus, 6),
        "prev_passed": prev_passed,
        "prev_total": prev_total,
    }


def _count_diff_lines(original: str, modified: str) -> Tuple[int, int, int]:
    """Count lines changed. Returns (added, removed, hunks)."""
    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
    ))
    added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
    removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    hunks = sum(1 for line in diff if line.startswith('@@'))
    return added, removed, hunks


def _check_patterns(content: str, patterns: List[str]) -> bool:
    return any(re.search(p, content, re.IGNORECASE) for p in patterns)


def _is_test_file(filepath: str) -> bool:
    return any(re.search(p, filepath, re.IGNORECASE) for p in TEST_FILE_PATTERNS)


def get_git_diff_files(cwd: Optional[str] = None) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Get original and modified file contents from git."""
    import os
    original_files: Dict[str, str] = {}
    modified_files: Dict[str, str] = {}

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=cwd, capture_output=True, text=True,
        )
        changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception:
        return {}, {}

    for filepath in changed:
        if _is_test_file(filepath):
            continue
        full_path = os.path.join(cwd, filepath) if cwd else filepath
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                modified_files[filepath] = f.read()
        except Exception:
            continue
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{filepath}"],
                cwd=cwd, capture_output=True, text=True,
            )
            original_files[filepath] = result.stdout if result.returncode == 0 else ""
        except Exception:
            original_files[filepath] = ""

    return original_files, modified_files


def analyze_solution(
    original_files: Dict[str, str],
    modified_files: Dict[str, str],
) -> SolutionMetrics:
    """Analyze solution and compute quality metrics."""
    total_changed = 0
    total_hunks = 0
    files_modified = 0
    modifies_test_files = False
    adds_debug_code = False
    adds_todo_comments = False

    for filepath, modified in modified_files.items():
        original = original_files.get(filepath, "")
        if modified == original:
            continue

        files_modified += 1
        added, removed, hunks = _count_diff_lines(original, modified)
        total_changed += added + removed
        total_hunks += hunks

        if _is_test_file(filepath):
            modifies_test_files = True
        if _check_patterns(modified, DEBUG_PATTERNS) and not _check_patterns(original, DEBUG_PATTERNS):
            adds_debug_code = True
        if _check_patterns(modified, TODO_PATTERNS) and not _check_patterns(original, TODO_PATTERNS):
            adds_todo_comments = True

    avg_hunk_size = total_changed / total_hunks if total_hunks > 0 else 0.0

    diff_size_score = next((b for t, b in DIFF_SIZE_THRESHOLDS if total_changed <= t), 0.0)
    precision_score = next((b for t, b in PRECISION_THRESHOLDS if avg_hunk_size <= t), 0.0) if avg_hunk_size > 0 else 0.0
    quality_score = max(0.0, 0.02 - (0.02 if modifies_test_files else 0) - (0.01 if adds_debug_code else 0) - (0.005 if adds_todo_comments else 0))

    return SolutionMetrics(
        total_lines_changed=total_changed,
        files_modified=files_modified,
        hunks_count=total_hunks,
        avg_hunk_size=round(avg_hunk_size, 2),
        modifies_test_files=modifies_test_files,
        adds_debug_code=adds_debug_code,
        adds_todo_comments=adds_todo_comments,
        diff_size_score=diff_size_score,
        surgical_precision_score=precision_score,
        quality_score=quality_score,
    )


def calculate_solution_bonus(
    passed: int,
    total: int,
    cwd: Optional[str] = None,
    min_pass_rate: float = 0.5,
) -> float:
    """Calculate solution quality bonus based on diff analysis."""
    if total <= 0:
        return 0.0
    pass_rate = passed / total
    if pass_rate < min_pass_rate:
        return 0.0

    original_files, modified_files = get_git_diff_files(cwd)
    if not modified_files:
        return 0.0

    metrics = analyze_solution(original_files, modified_files)
    scale_factor = (pass_rate - min_pass_rate) / (1.0 - min_pass_rate)
    return round(metrics.total_bonus * scale_factor, 4)


def calculate_reward(
    passed: int,
    total: int,
    tier: str = "principal",
    cwd: Optional[str] = None,
    enable_solution_bonus: bool = True,
    training_mode: Optional[str] = None,
    prev_passed: Optional[int] = None,
    prev_total: Optional[int] = None,
) -> Dict:
    """
    Calculate final reward with optional solution quality bonus.

    Args:
        passed: Number of tests passed
        total: Total number of tests
        tier: Difficulty tier for sparse reward thresholds
        cwd: Working directory for git diff analysis
        enable_solution_bonus: Whether to add surgical fix bonuses
        training_mode: If set, use dense rewards instead of sparse.
                       Options: "linear", "sublinear", "smooth"
        prev_passed: Previous passed count for incremental rewards
        prev_total: Previous total count for incremental rewards
    """
    if total <= 0:
        return {
            "reward": 0.0,
            "base_reward": 0.0,
            "solution_bonus": 0.0,
            "incremental_bonus": 0.0,
            "passed": 0,
            "total": 0,
            "training_mode": training_mode,
        }

    pass_rate = passed / total

    # Use training reward (dense) or sparse reward based on mode
    if training_mode:
        base_reward = training_reward(pass_rate, training_mode)
    else:
        base_reward = sparse_reward(pass_rate, tier)

    solution_bonus = 0.0
    if enable_solution_bonus and not training_mode:
        # Solution bonus only applies in evaluation mode
        solution_bonus = calculate_solution_bonus(passed, total, cwd)

    # Calculate incremental bonus if previous results provided
    incr_data = {}
    incremental_bonus = 0.0
    if prev_passed is not None:
        incr_data = incremental_reward(passed, total, prev_passed, prev_total)
        incremental_bonus = incr_data.get("incremental_bonus", 0.0)

    final_reward = min(1.0, max(0.0, base_reward + solution_bonus + incremental_bonus))

    result = {
        "reward": round(final_reward, 4),
        "pass_rate": round(pass_rate, 6),
        "base_reward": round(base_reward, 4),
        "solution_bonus": round(solution_bonus, 4),
        "incremental_bonus": round(incremental_bonus, 6),
        "passed": passed,
        "total": total,
        "tier": tier,
        "training_mode": training_mode,
    }

    # Add incremental details if available
    if incr_data:
        result["newly_passing"] = incr_data.get("newly_passing", 0)
        result["regressions"] = incr_data.get("regressions", 0)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Solution Scoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Training Mode:
  Use --training-mode for foundation model training. This provides dense,
  continuous reward signals instead of sparse step-function rewards.

  Modes:
    linear    - Direct 1:1 mapping (reward = pass_rate)
    sublinear - Rewards early progress more (reward = pass_rate^0.7)
    smooth    - S-curve with smooth endpoints (Hermite interpolation)

Incremental Rewards:
  Use --prev-passed to track progress between steps. This adds bonuses for
  newly passing tests and penalties for regressions.

Examples:
  # Evaluation mode (sparse rewards with thresholds)
  python scoring.py --passed 9000 --total 10000 --tier apex-principal

  # Training mode (dense linear rewards)
  python scoring.py --passed 9000 --total 10000 --training-mode linear

  # Incremental rewards (track progress between steps)
  python scoring.py --passed 9000 --total 10000 --prev-passed 8500 --json
        """,
    )
    parser.add_argument("--passed", type=int, default=0)
    parser.add_argument("--total", type=int, default=0)
    parser.add_argument("--tier", type=str, default="principal", choices=list(REWARD_TABLES.keys()))
    parser.add_argument("--cwd", type=str, default=None)
    parser.add_argument("--no-bonus", action="store_true", help="Disable solution quality bonus")
    parser.add_argument("--json", action="store_true", help="Output full JSON results")
    parser.add_argument(
        "--training-mode",
        type=str,
        choices=list(TRAINING_MODES.keys()),
        default=None,
        metavar="MODE",
        help="Enable training mode with dense rewards. Modes: linear, sublinear, smooth",
    )
    parser.add_argument(
        "--prev-passed",
        type=int,
        default=None,
        metavar="N",
        help="Previous passed count for incremental reward tracking",
    )
    parser.add_argument(
        "--prev-total",
        type=int,
        default=None,
        metavar="N",
        help="Previous total count (defaults to current total)",
    )
    parser.add_argument(
        "--parse-errors",
        type=str,
        default=None,
        metavar="FILE",
        help="Parse test output file into structured errors",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        choices=["python", "javascript", "go", "ruby", "rust"],
        help="Language for error parsing (default: python)",
    )
    args = parser.parse_args()

    # Handle error parsing mode
    if args.parse_errors:
        try:
            with open(args.parse_errors, "r", encoding="utf-8", errors="ignore") as f:
                output = f.read()
            failures = parse_test_failures(output, args.language)
            print(format_failures_json(failures))
            return
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            return

    result = calculate_reward(
        passed=args.passed,
        total=args.total,
        tier=args.tier,
        cwd=args.cwd,
        enable_solution_bonus=not args.no_bonus,
        training_mode=args.training_mode,
        prev_passed=args.prev_passed,
        prev_total=args.prev_total,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["reward"])


if __name__ == "__main__":
    main()
