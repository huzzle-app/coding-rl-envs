"""
DocuVault Reward Function
Terminal Bench v2 - Sparse Reward System for Java/Spring Boot Document Management

25 bugs across 7 categories with dependency chains.
- Sparse rewards with 5 thresholds
- Regression penalties
- Category completion bonuses
- Concurrency and security fix bonuses
"""
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from pathlib import Path
import re
import xml.etree.ElementTree as ET

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float
    category: str  # unit, integration, concurrency, security
    bug_markers: List[str]

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
    completion_bonus: float
    bug_bonus: float
    efficiency_bonus: float
    total: float
    details: Dict

# ==============================================================================
# Test category weights
# ==============================================================================
CATEGORY_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'concurrency': 2.5,
    'security': 2.0,
}

class RewardCalculator:
    """
    Calculate reward for the DocuVault debugging environment.

    Reward components:
    1. Sparse test pass rate with thresholds (40%)
    2. Category completion bonus (25%)
    3. Bug detection bonus with dependencies (25%)
    4. Efficiency bonus (5%)
    5. Regression penalty (up to -15%)
    6. Concurrency/security fix bonuses (+5%)
    """

    def __init__(self, max_steps: int = 100):
        self.max_steps = max_steps
        # 5-threshold sparse reward for Senior tier (step function, matches scoring.py)
        self.pass_thresholds = [0.50, 0.75, 0.90, 1.0]
        self.threshold_rewards = [0.15, 0.35, 0.65, 1.0]

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None
    ) -> RewardBreakdown:
        """
        Calculate total reward from test results.

        Args:
            test_results: List of test results from Maven/Surefire run
            step_count: Current step/action count
            previous_results: Previous test results for delta calculation

        Returns:
            RewardBreakdown with detailed scoring
        """
        test_pass_score = self._calculate_sparse_pass_rate(test_results)
        completion_bonus = self._calculate_strict_completion_bonus(test_results)
        bug_bonus = 0.0
        efficiency_bonus = self._calculate_efficiency_bonus(test_results, step_count)

        regression_penalty = 0.0
        if previous_results:
            regression_penalty = self._calculate_regression_penalty(
                test_results, previous_results
            )

        # Concurrency bonus
        concurrency_bonus = 0.0
        failing = {r.name for r in test_results if not r.passed}
        concurrency_keywords = ['thread_safe', 'concurrent', 'synchronized', 'threadlocal', 'partial_construction']
        if not any(any(kw in t.lower() for kw in concurrency_keywords) for t in failing):
            concurrency_bonus = 0.03

        # Security bonus
        security_bonus = 0.0
        security_keywords = ['injection', 'traversal', 'deserialization', 'jwt_none']
        if not any(any(kw in t.lower() for kw in security_keywords) for t in failing):
            security_bonus = 0.02

        total = (
            test_pass_score * 0.40 +
            completion_bonus * 0.25 +
            bug_bonus * 0.25 +
            efficiency_bonus * 0.05 +
            concurrency_bonus +
            security_bonus -
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
        Calculate sparse pass rate with thresholds (step function).

        No reward until 50% pass rate, then step increases.
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

        # Step function: find highest threshold that pass_rate meets
        for threshold, reward in reversed(list(zip(self.pass_thresholds, self.threshold_rewards))):
            if pass_rate >= threshold:
                return reward
        return 0.0

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

    def get_dependency_stats(self) -> Dict[str, Any]:
        """Get statistics about bug dependency graph."""
        return {
            'bugs_with_dependencies': 0,
            'dependency_percentage': 0,
            'max_chain_depth': 0,
            'diamond_patterns': 0,
            'cross_category_links': 0,
        }

def parse_surefire_reports(report_dir: Path) -> List[TestResult]:
    """
    Parse Maven Surefire XML reports to extract test results.

    Args:
        report_dir: Path to target/surefire-reports directory

    Returns:
        List of TestResult objects
    """
    results = []
    seen = set()

    if not report_dir.exists():
        return results

    def categorize(classname: str) -> str:
        if '.concurrency.' in classname:
            return 'concurrency'
        elif '.security.' in classname:
            return 'security'
        elif '.integration.' in classname:
            return 'integration'
        return 'unit'

    for xml_file in report_dir.glob('TEST-*.xml'):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for testcase in root.findall('testcase'):
                classname = testcase.get('classname', '')
                name = testcase.get('name', '')
                time_val = float(testcase.get('time', '0'))

                # Skip already-seen tests
                if name in seen:
                    continue

                # Skip skipped tests
                skipped = testcase.find('skipped')
                if skipped is not None:
                    continue

                seen.add(name)

                failure = testcase.find('failure')
                error = testcase.find('error')
                passed = failure is None and error is None

                category = categorize(classname)

                results.append(TestResult(
                    name=name,
                    passed=passed,
                    duration=time_val,
                    category=category,
                    bug_markers=[],
                ))
        except ET.ParseError:
            continue

    return results

def calculate_reward(test_results, step_count, max_steps=100):
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

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
