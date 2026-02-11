"""
QuantumCore Reward Function
Terminal Bench v2 - Extremely Sparse Reward System for Rust HFT Platform

Very sparse rewards with 8 thresholds.
"""
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

# ==============================================================================
# Test categories and their weights
# ==============================================================================
TEST_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'concurrency': 2.5,
    'financial': 2.0,
    'security': 2.5,
    'performance': 2.0,
    'chaos': 3.0,
    'system': 3.0,
}

@dataclass
class RewardCalculator:
    """
    Extremely sparse reward calculator for QuantumCore.

    Features:
    - 8 threshold levels with very sparse payouts
    - Regression penalty: -0.15 per previously passing test that fails
    - Service isolation bonus: +0.02 per fully passing service
    - Concurrency test bonus: +0.05 for passing concurrency tests
    - Financial test bonus: +0.05 for passing financial tests
    - Efficiency bonus at completion
    """

    # Extremely sparse thresholds
    pass_thresholds: List[float] = field(default_factory=lambda: [
        0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0
    ])
    threshold_rewards: List[float] = field(default_factory=lambda: [
        0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0
    ])

    # Penalty and bonus weights
    regression_penalty: float = -0.15
    service_isolation_bonus: float = 0.02
    concurrency_test_bonus: float = 0.05
    financial_test_bonus: float = 0.05
    efficiency_bonus_weight: float = 0.03

    def calculate_reward(
        self,
        test_results: Dict[str, Any],
        previous_results: Optional[Dict[str, Any]] = None,
        step_count: int = 0,
        max_steps: int = 200,
    ) -> float:
        """
        Calculate reward based on test results.

        Returns reward value between -1.0 and 1.0
        """
        pass_rate = test_results.get('pass_rate', 0.0)

        # Component 1: Sparse threshold reward (70%)
        base_reward = self._calculate_sparse_reward(pass_rate) * 0.70

        # Component 2: Regression penalty
        regression = self._calculate_regression_penalty(test_results, previous_results)

        # Component 3: Service isolation bonus (10%)
        service_bonus = self._calculate_service_bonus(test_results) * 0.10

        # Component 4: Concurrency test bonus (5%)
        concurrency_bonus = self._calculate_category_bonus(
            test_results, ['concurrency', 'race', 'deadlock', 'atomic']
        ) * self.concurrency_test_bonus

        # Component 5: Financial test bonus (5%)
        financial_bonus = self._calculate_category_bonus(
            test_results, ['precision', 'decimal', 'overflow', 'rounding', 'pnl']
        ) * self.financial_test_bonus

        # Component 6: Efficiency bonus (5%) - only if all tests pass
        efficiency = 0.0
        if pass_rate >= 1.0:
            efficiency = max(0, 1 - step_count / max_steps) * self.efficiency_bonus_weight

        total = base_reward + regression + service_bonus + concurrency_bonus + financial_bonus + efficiency
        return max(-1.0, min(1.0, total))

    def _calculate_sparse_reward(self, pass_rate: float) -> float:
        """Calculate sparse reward based on thresholds."""
        reward = 0.0
        for threshold, reward_value in zip(self.pass_thresholds, self.threshold_rewards):
            if pass_rate >= threshold:
                reward = reward_value
            else:
                break
        return reward

    def _calculate_regression_penalty(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> float:
        """Calculate penalty for tests that regressed."""
        if previous is None:
            return 0.0

        current_passed = current.get('passed', 0)
        previous_passed = previous.get('passed', 0)

        if current_passed < previous_passed:
            regressions = previous_passed - current_passed
            return self.regression_penalty * (regressions / max(previous_passed, 1))

        return 0.0

    def _calculate_service_bonus(self, test_results: Dict[str, Any]) -> float:
        """Calculate bonus for services with all tests passing."""
        pass_rate = test_results.get('pass_rate', 0.0)
        if pass_rate >= 0.95:
            return self.service_isolation_bonus * 10
        elif pass_rate >= 0.80:
            return self.service_isolation_bonus * 6
        elif pass_rate >= 0.50:
            return self.service_isolation_bonus * 3
        return 0.0

    def _calculate_category_bonus(
        self, test_results: Dict[str, Any], keywords: List[str]
    ) -> float:
        """Calculate bonus for category-specific tests passing."""
        failed_tests = test_results.get('failed_tests', [])
        if not failed_tests:
            return 1.0
        category_failing = any(
            any(kw in t.lower() for kw in keywords)
            for t in failed_tests
        )
        return 0.0 if category_failing else 1.0

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
