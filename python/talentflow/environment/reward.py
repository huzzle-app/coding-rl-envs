"""
TalentFlow Reward Function

Calculates reward based on test results and bug detection.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import re

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float
    category: str  # unit, integration, system, security
    bug_markers: List[str]  # e.g., ['bug_a1', 'bug_c2']

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
    completion_bonus: float
    bug_bonus: float
    efficiency_bonus: float
    total: float
    details: Dict

# Test weights by category
CATEGORY_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'system': 2.5,
    'security': 2.0,
}

class RewardCalculator:
    """
    Calculate reward for the TalentFlow debugging environment.

    Reward components (harder version):
    1. Sparse test pass rate with thresholds (40%)
    2. Category completion bonus with all-or-nothing (25%)
    3. Bug detection bonus with dependencies (25%)
    4. Efficiency bonus (5%)
    5. Regression penalty (can reduce total)

    The reward is designed to be sparse - no meaningful reward
    until significant progress is made.
    """

    def __init__(self, max_steps: int = 150):
        self.max_steps = max_steps
        self.pass_thresholds = [0.25, 0.50, 0.75, 0.90, 1.0]
        self.threshold_rewards = [0.0, 0.15, 0.35, 0.65, 1.0]

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None
    ) -> RewardBreakdown:
        """
        Calculate total reward from test results.

        Args:
            test_results: List of test results from pytest run
            step_count: Current step/action count
            previous_results: Previous test results for delta calculation

        Returns:
            RewardBreakdown with detailed scoring
        """
        test_pass_score = self._calculate_sparse_pass_rate(test_results)

        completion_bonus = self._calculate_strict_completion_bonus(test_results)

        bug_bonus = self._calculate_bug_bonus_with_dependencies(test_results)

        efficiency_bonus = self._calculate_efficiency_bonus(
            test_results, step_count
        )

        regression_penalty = 0.0
        if previous_results:
            regression_penalty = self._calculate_regression_penalty(
                test_results, previous_results
            )

        total = (
            test_pass_score * 0.40 +
            completion_bonus * 0.25 +
            bug_bonus * 0.25 +
            efficiency_bonus * 0.05 -
            regression_penalty * 0.15
        )

        total = max(0.0, min(total, 1.0))

        return RewardBreakdown(
            test_pass_score=test_pass_score,
            completion_bonus=completion_bonus,
            bug_bonus=bug_bonus,
            efficiency_bonus=efficiency_bonus,
            total=total,
            details=self._get_details(test_results, step_count, regression_penalty),
        )

    def _calculate_sparse_pass_rate(self, results: List[TestResult]) -> float:
        """
        Calculate sparse pass rate with thresholds.

        No reward until 25% pass rate, then step increases.
        """
        if not results:
            return 0.0

        total_weight = 0.0
        weighted_passes = 0.0

        for result in results:
            weight = CATEGORY_WEIGHTS.get(result.category, 1.0)
            total_weight += weight
            if result.passed:
                weighted_passes += weight

        pass_rate = weighted_passes / total_weight if total_weight > 0 else 0.0

        for i, threshold in enumerate(self.pass_thresholds):
            if pass_rate < threshold:
                if i == 0:
                    return 0.0
                prev_threshold = self.pass_thresholds[i - 1]
                prev_reward = self.threshold_rewards[i - 1]
                curr_reward = self.threshold_rewards[i]

                progress = (pass_rate - prev_threshold) / (threshold - prev_threshold)
                return prev_reward + progress * (curr_reward - prev_reward)

        return 1.0

    def _calculate_strict_completion_bonus(self, results: List[TestResult]) -> float:
        """
        Calculate strict completion bonus.

        Only counts categories where ALL tests pass.
        Bonus requires at least 2 categories complete.
        """
        category_stats = {}

        for result in results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {'total': 0, 'passed': 0}
            category_stats[cat]['total'] += 1
            if result.passed:
                category_stats[cat]['passed'] += 1

        complete_categories = 0
        for cat, stats in category_stats.items():
            if stats['total'] > 0 and stats['passed'] == stats['total']:
                complete_categories += 1

        if complete_categories < 2:
            return 0.0

        return min((complete_categories - 1) * 0.25, 1.0)

    def _calculate_bug_bonus_with_dependencies(self, results: List[TestResult]) -> float:
        """
        Calculate bug bonus considering dependencies.

        Returns 0.0 as bug tracking has been removed.
        """
        return 0.0

    def _calculate_regression_penalty(
        self,
        current: List[TestResult],
        previous: List[TestResult]
    ) -> float:
        """
        Calculate penalty for regressions (tests that were passing now fail).
        """
        prev_status = {r.name: r.passed for r in previous}
        curr_status = {r.name: r.passed for r in current}

        regressions = 0
        for name, was_passing in prev_status.items():
            if was_passing and not curr_status.get(name, False):
                regressions += 1

        if not previous:
            return 0.0

        return min(regressions / len(previous), 1.0)

    def _calculate_efficiency_bonus(
        self,
        results: List[TestResult],
        step_count: int
    ) -> float:
        """
        Calculate progressive efficiency bonus.

        Rewards high pass rate achieved with remaining step budget.
        Formula: pass_rate * (1.0 - step_count / max_steps)
        """
        if not results:
            return 0.0

        pass_rate = sum(1 for r in results if r.passed) / len(results)
        remaining_budget = max(0.0, 1.0 - step_count / self.max_steps)
        return pass_rate * remaining_budget

    def _get_details(
        self,
        results: List[TestResult],
        step_count: int,
        regression_penalty: float = 0.0
    ) -> Dict:
        """Get detailed breakdown of results."""
        category_breakdown = {}
        for result in results:
            cat = result.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {'total': 0, 'passed': 0, 'failed': []}
            category_breakdown[cat]['total'] += 1
            if result.passed:
                category_breakdown[cat]['passed'] += 1
            else:
                category_breakdown[cat]['failed'].append(result.name)

        for cat in category_breakdown:
            stats = category_breakdown[cat]
            stats['pass_rate'] = stats['passed'] / stats['total'] if stats['total'] > 0 else 0

        return {
            'total_tests': len(results),
            'passed_tests': sum(1 for r in results if r.passed),
            'failed_tests': sum(1 for r in results if not r.passed),
            'pass_rate': sum(1 for r in results if r.passed) / len(results) if results else 0,
            'step_count': step_count,
            'max_steps': self.max_steps,
            'regression_penalty': regression_penalty,
            'category_breakdown': category_breakdown,
        }

def calculate_reward(
    test_results: List[Dict],
    step_count: int,
    max_steps: int = 100
) -> float:
    """
    Simplified reward calculation function.

    Args:
        test_results: List of dicts with 'name', 'passed', 'category' keys
        step_count: Current step count
        max_steps: Maximum steps allowed

    Returns:
        Float reward between 0.0 and 1.0
    """
    results = [
        TestResult(
            name=r['name'],
            passed=r['passed'],
            duration=r.get('duration', 0.0),
            category=r.get('category', 'unit'),
            bug_markers=r.get('markers', []),
        )
        for r in test_results
    ]

    calculator = RewardCalculator(max_steps=max_steps)
    breakdown = calculator.calculate(results, step_count)

    return breakdown.total

def parse_pytest_output(output: str) -> List[TestResult]:
    """
    Parse pytest output to extract test results.

    Args:
        output: Raw pytest output string

    Returns:
        List of TestResult objects
    """
    results = []
    seen_tests = set()

    def _categorize(file_path: str) -> str:
        if 'unit/' in file_path:
            return 'unit'
        elif 'integration/' in file_path:
            return 'integration'
        elif 'system/' in file_path:
            return 'system'
        elif 'security/' in file_path:
            return 'security'
        return 'unit'

    def _add_result(test_name: str, nodeid: str, file_path: str, status: str):
        if nodeid in seen_tests:
            return
        seen_tests.add(nodeid)

        category = _categorize(file_path)

        results.append(TestResult(
            name=test_name,
            passed=status == 'PASSED',
            duration=0.0,
            category=category,
            bug_markers=[],
        ))

    # Pattern for class-based tests: file::Class::test_name[params] STATUS
    class_pattern = r'(tests/\S+)::(\w+)::(test_\w+(?:\[[\S]*\])?)\s+(PASSED|FAILED|ERROR|SKIPPED)'
    for match in re.finditer(class_pattern, output):
        file_path, class_name, test_name, status = match.groups()
        nodeid = f'{file_path}::{class_name}::{test_name}'
        bare_name = re.sub(r'\[.*\]$', '', test_name)
        _add_result(bare_name, nodeid, file_path, status)

    # Pattern for function-level tests: file::test_name[params] STATUS
    func_pattern = r'(tests/\S+)::(test_\w+(?:\[[\S]*\])?)\s+(PASSED|FAILED|ERROR|SKIPPED)'
    for match in re.finditer(func_pattern, output):
        file_path, test_name, status = match.groups()
        nodeid = f'{file_path}::{test_name}'
        bare_name = re.sub(r'\[.*\]$', '', test_name)
        _add_result(bare_name, nodeid, file_path, status)

    return results

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
