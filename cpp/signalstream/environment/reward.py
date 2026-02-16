"""
SignalStream Reward Function
Terminal Bench v2 - Very Sparse Reward System for C++ Streaming Platform

Very sparse rewards with 10 thresholds (Apex-Principal difficulty).
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# ==============================================================================
# Test category weights
# ==============================================================================
TEST_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'concurrency': 2.5,
    'security': 2.0,
    'performance': 2.0,
    'chaos': 3.0,
    'system': 3.0,
}

@dataclass
class RewardCalculator:
    """
    Very sparse reward calculator for SignalStream (Apex-Principal difficulty).

    Features:
    - 10 threshold levels with very sparse payouts
    - Regression penalty
    - Service isolation bonus
    - Concurrency/security/template fix bonuses
    - Efficiency bonus at completion
    """

    pass_thresholds: List[float] = field(default_factory=lambda: [
        0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0
    ])
    threshold_rewards: List[float] = field(default_factory=lambda: [
        0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0
    ])

    regression_penalty_weight: float = -0.15
    service_isolation_bonus: float = 0.02
    concurrency_bonus_weight: float = 0.05
    security_bonus_weight: float = 0.05
    template_bonus_weight: float = 0.03
    efficiency_bonus_weight: float = 0.03

    def calculate_reward(
        self,
        test_results: Dict[str, Any],
        previous_results: Optional[Dict[str, Any]] = None,
        step_count: int = 0,
        max_steps: int = 200,
    ) -> float:
        pass_rate = test_results.get('pass_rate', 0.0)

        # Component 1: Sparse threshold reward (60%)
        base_reward = self._sparse_reward(pass_rate) * 0.60

        # Component 2: Regression penalty
        regression = self._regression_penalty(test_results, previous_results)

        # Component 3: Service isolation bonus (10%)
        service_bonus = self._service_bonus(test_results) * 0.10

        # Component 4: Concurrency test bonus (5%)
        conc_bonus = self._category_bonus(
            test_results, ['concurrent', 'deadlock', 'race', 'atomic', 'aba', 'condvar']
        ) * self.concurrency_bonus_weight

        # Component 5: Security test bonus (5%)
        sec_bonus = self._category_bonus(
            test_results, ['injection', 'traversal', 'overflow', 'timing', 'jwt', 'rng']
        ) * self.security_bonus_weight

        # Component 6: Template/Modern C++ bonus (3%)
        tmpl_bonus = self._category_bonus(
            test_results, ['sfinae', 'adl', 'constexpr', 'forwarding', 'variant', 'ctad', 'concept']
        ) * self.template_bonus_weight

        # Component 7: Efficiency bonus (2%)
        efficiency = 0.0
        if pass_rate >= 1.0:
            efficiency = max(0, 1 - step_count / max_steps) * self.efficiency_bonus_weight

        total = (base_reward + regression + service_bonus +
                 conc_bonus + sec_bonus + tmpl_bonus + efficiency)
        return max(-1.0, min(1.0, total))

    def _sparse_reward(self, pass_rate: float) -> float:
        reward = 0.0
        for threshold, reward_value in zip(self.pass_thresholds, self.threshold_rewards):
            if pass_rate >= threshold:
                reward = reward_value
            else:
                break
        return reward

    def _regression_penalty(self, current, previous):
        if previous is None:
            return 0.0
        curr_passed = current.get('passed', 0)
        prev_passed = previous.get('passed', 0)
        if curr_passed < prev_passed:
            regressions = prev_passed - curr_passed
            return self.regression_penalty_weight * (regressions / max(prev_passed, 1))
        return 0.0

    def _service_bonus(self, test_results):
        pass_rate = test_results.get('pass_rate', 0.0)
        if pass_rate >= 0.95:
            return self.service_isolation_bonus * 10
        elif pass_rate >= 0.80:
            return self.service_isolation_bonus * 6
        elif pass_rate >= 0.50:
            return self.service_isolation_bonus * 3
        return 0.0

    def _category_bonus(self, test_results, keywords):
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
