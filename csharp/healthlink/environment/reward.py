"""
HealthLink Reward Function
Terminal Bench v2 - Sparse Reward System for C#/.NET Healthcare Management

Sparse rewards with 5 thresholds based on pass rate.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

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
    Calculate reward for the HealthLink debugging environment.

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
        """
        Calculate total reward from test results.

        Args:
            test_results: List of test results from dotnet test/TRX run
            step_count: Current step/action count
            previous_results: Previous test results for delta calculation

        Returns:
            RewardBreakdown with detailed scoring
        """
        test_pass_score = self._calculate_sparse_pass_rate(test_results)

        total = max(0.0, min(test_pass_score, 1.0))

        return RewardBreakdown(
            test_pass_score=test_pass_score,
            total=total,
            details=self._get_details(test_results, step_count),
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

    def _get_details(
        self,
        results: List[TestResult],
        step_count: int,
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
            'category_breakdown': category_breakdown,
        }

def parse_trx_reports(report_dir: Path) -> List[TestResult]:
    """
    Parse TRX (Visual Studio Test Results) XML reports to extract test results.

    TRX files use the Microsoft Visual Studio Test Results XML schema.
    Each <UnitTestResult> element has an 'outcome' attribute ("Passed" or "Failed")
    and a 'testName' attribute giving the test name.

    Args:
        report_dir: Path to tests/HealthLink.Tests/TestResults/ directory

    Returns:
        List of TestResult objects
    """
    results = []
    seen = set()

    if not report_dir.exists():
        return results

    # TRX namespace
    ns = {'vs': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}

    def categorize(test_name: str) -> str:
        """Categorize a test based on its fully qualified name or test name."""
        name_lower = test_name.lower()
        if 'concurrency' in name_lower or 'async' in name_lower or 'deadlock' in name_lower or 'valuetask' in name_lower:
            return 'concurrency'
        elif 'security' in name_lower or 'injection' in name_lower or 'traversal' in name_lower or 'jwt' in name_lower or 'authorization' in name_lower or 'anonymous' in name_lower:
            return 'security'
        elif 'integration' in name_lower or 'startup' in name_lower or 'efcore' in name_lower:
            return 'integration'
        return 'unit'

    for trx_file in report_dir.glob('*.trx'):
        try:
            tree = ET.parse(trx_file)
            root = tree.getroot()

            # Try with namespace first
            test_results_elem = root.findall('.//vs:UnitTestResult', ns)
            if not test_results_elem:
                # Try without namespace (some TRX files may not use it)
                test_results_elem = root.findall('.//{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}UnitTestResult')
            if not test_results_elem:
                # Try bare element names (no namespace)
                test_results_elem = root.findall('.//UnitTestResult')

            for unit_result in test_results_elem:
                test_name = unit_result.get('testName', '')
                outcome = unit_result.get('outcome', 'Failed')
                duration_str = unit_result.get('duration', '00:00:00')

                # Skip already-seen tests
                if test_name in seen:
                    continue

                # Skip NotExecuted / Inconclusive tests
                if outcome in ('NotExecuted', 'Inconclusive', 'Pending'):
                    continue

                seen.add(test_name)

                # Parse duration (HH:MM:SS.fff format)
                time_val = 0.0
                try:
                    parts = duration_str.split(':')
                    if len(parts) == 3:
                        time_val = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                    else:
                        time_val = float(duration_str)
                except (ValueError, IndexError):
                    time_val = 0.0

                passed = outcome == 'Passed'
                category = categorize(test_name)

                results.append(TestResult(
                    name=test_name,
                    passed=passed,
                    duration=time_val,
                    category=category,
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
        )
        for r in test_results
    ]

    calculator = RewardCalculator(max_steps=max_steps)
    breakdown = calculator.calculate(results, step_count)

    return breakdown.total

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
