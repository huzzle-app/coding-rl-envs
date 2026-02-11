"""
CacheForge Reward Function
Terminal Bench v2 - Sparse Reward System for C++ Cache Server

Sparse rewards with 5 thresholds based on pass rate.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float
    category: str  # unit, integration, concurrency, security

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
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
    Calculate reward for the CacheForge debugging environment.

    Reward based on sparse test pass rate with thresholds.
    """

    def __init__(self, max_steps: int = 100):
        self.max_steps = max_steps
        self.pass_thresholds = [0.25, 0.50, 0.75, 0.90, 1.0]
        self.threshold_rewards = [0.0, 0.15, 0.35, 0.65, 1.0]

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None
    ) -> RewardBreakdown:
        test_pass_score = self._calculate_sparse_pass_rate(test_results)

        total = max(0.0, min(test_pass_score, 1.0))

        return RewardBreakdown(
            test_pass_score=test_pass_score,
            total=total,
            details=self._get_details(test_results, step_count),
        )

    def _calculate_sparse_pass_rate(self, results: List[TestResult]) -> float:
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

    def _get_details(self, results, step_count):
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

        return {
            'total_tests': len(results),
            'passed_tests': sum(1 for r in results if r.passed),
            'failed_tests': sum(1 for r in results if not r.passed),
            'pass_rate': sum(1 for r in results if r.passed) / len(results) if results else 0,
            'step_count': step_count,
            'max_steps': self.max_steps,
            'category_breakdown': category_breakdown,
        }

def parse_ctest_output(output: str) -> List[TestResult]:
    """Parse ctest output to extract test results."""
    results = []
    seen = set()

    def categorize(test_name):
        if 'concurrent' in test_name.lower() or 'deadlock' in test_name.lower():
            return 'concurrency'
        elif 'security' in test_name.lower() or 'overflow' in test_name.lower() or 'injection' in test_name.lower():
            return 'security'
        elif 'integration' in test_name.lower() or 'pipeline' in test_name.lower():
            return 'integration'
        return 'unit'

    # GTest output: [ OK ] TestSuite.TestName (N ms)
    # or: [ FAILED ] TestSuite.TestName (N ms)
    ok_pattern = r'\[\s+OK\s+\]\s+(\w+)\.(\w+)\s+\((\d+)\s+ms\)'
    fail_pattern = r'\[\s+FAILED\s+\]\s+(\w+)\.(\w+)'

    for match in re.finditer(ok_pattern, output):
        suite, name, duration = match.groups()
        if name not in seen:
            seen.add(name)
            results.append(TestResult(
                name=name, passed=True, duration=float(duration),
                category=categorize(name)
            ))

    for match in re.finditer(fail_pattern, output):
        suite, name = match.groups()
        if name not in seen:
            seen.add(name)
            results.append(TestResult(
                name=name, passed=False, duration=0.0,
                category=categorize(name)
            ))

    return results

def calculate_reward(test_results, step_count, max_steps=100):
    """Simplified reward calculation."""
    results = [
        TestResult(
            name=r['name'], passed=r['passed'],
            duration=r.get('duration', 0.0),
            category=r.get('category', 'unit'),
        )
        for r in test_results
    ]
    calc = RewardCalculator(max_steps=max_steps)
    return calc.calculate(results, step_count).total

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
