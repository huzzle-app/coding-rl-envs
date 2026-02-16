"""
NexusTrade Reward Function
Terminal Bench v2 - Extremely Sparse Reward System

This reward function is designed to be 10x harder than TalentFlow:
- Very sparse rewards with 8 thresholds
- Regression penalties
- Service isolation bonuses
- Chaos test bonuses
"""
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

# Test categories and their weights
TEST_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'contract': 2.0,
    'chaos': 3.0,
    'security': 2.5,
    'performance': 2.0,
    'system': 3.0,
}

# Service isolation - bonus for fully passing services
SERVICE_TEST_GROUPS = {
    'gateway': ['test_gateway_*'],
    'auth': ['test_auth_*'],
    'users': ['test_users_*'],
    'orders': ['test_orders_*'],
    'matching': ['test_matching_*'],
    'risk': ['test_risk_*'],
    'settlement': ['test_settlement_*'],
    'market_data': ['test_market_data_*'],
    'notifications': ['test_notifications_*'],
    'audit': ['test_audit_*'],
}

@dataclass
class RewardCalculator:
    """
    Extremely sparse reward calculator for NexusTrade.

    Features:
    - 8 threshold levels (vs 5 in TalentFlow)
    - Regression penalty: -0.15 per previously passing test that fails
    - Service isolation bonus: +0.02 per fully passing service
    - Chaos test bonus: +0.10 for passing chaos tests
    """

    # Extremely sparse thresholds
    pass_thresholds: List[float] = field(default_factory=lambda: [
        0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0
    ])
    threshold_rewards: List[float] = field(default_factory=lambda: [
        0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0
    ])

    # Penalty and bonus weights
    regression_penalty: float = -0.15
    service_isolation_bonus: float = 0.02
    chaos_test_bonus: float = 0.10
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

        Args:
            test_results: Current test results
            previous_results: Previous step's test results
            step_count: Current step number
            max_steps: Maximum steps allowed

        Returns:
            Reward value between -1.0 and 1.0
        """
        pass_rate = test_results.get('pass_rate', 0.0)

        # Component 1: Sparse threshold reward (70%)
        base_reward = self._calculate_sparse_reward(pass_rate) * 0.70

        # Component 2: Regression penalty
        regression = self._calculate_regression_penalty(test_results, previous_results)

        # Component 3: Service isolation bonus (15%)
        service_bonus = self._calculate_service_bonus(test_results) * 0.15

        # Component 4: Chaos test bonus (10%)
        chaos_bonus = self._calculate_chaos_bonus(test_results) * 0.10

        # Component 5: Efficiency bonus (5%) - only if all tests pass
        efficiency = 0.0
        if pass_rate >= 1.0:
            efficiency = max(0, 1 - step_count / max_steps) * self.efficiency_bonus_weight

        total = base_reward + regression + service_bonus + chaos_bonus + efficiency

        # Clamp to valid range
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

        # Simple regression check based on pass count
        current_passed = current.get('passed', 0)
        previous_passed = previous.get('passed', 0)

        if current_passed < previous_passed:
            regressions = previous_passed - current_passed
            return self.regression_penalty * (regressions / max(previous_passed, 1))

        return 0.0

    def _calculate_service_bonus(self, test_results: Dict[str, Any]) -> float:
        """Calculate bonus for services with all tests passing."""
        test_detail = test_results.get('test_detail', {})
        if not test_detail:
            return 0.0

        passing_services = 0
        for service, patterns in SERVICE_TEST_GROUPS.items():
            # Find tests matching this service's patterns (test_<service>_*)
            prefix = patterns[0].replace('*', '')  # e.g. "test_gateway_"
            service_tests = [name for name in test_detail if name.startswith(prefix)]
            if service_tests and all(test_detail[name] for name in service_tests):
                passing_services += 1

        return self.service_isolation_bonus * passing_services

    def _calculate_chaos_bonus(self, test_results: Dict[str, Any]) -> float:
        """Calculate bonus for passing chaos tests."""
        test_detail = test_results.get('test_detail', {})
        if not test_detail:
            return 0.0

        # Count chaos-related tests (those with chaos-like prefixes)
        chaos_tests_total = 0
        chaos_tests_passed = 0
        chaos_prefixes = ['test_partition_', 'test_leader_', 'test_failover_',
                          'test_lock_', 'test_majority_', 'test_concurrent_',
                          'test_eventual_', 'test_stale_', 'test_transaction_',
                          'test_event_', 'test_idempotency_', 'test_replay_']
        for test_name, passed in test_detail.items():
            for prefix in chaos_prefixes:
                if test_name.startswith(prefix):
                    chaos_tests_total += 1
                    if passed:
                        chaos_tests_passed += 1
                    break

        if chaos_tests_total == 0:
            return 0.0
        chaos_pass_rate = chaos_tests_passed / chaos_tests_total
        if chaos_pass_rate >= 0.90:
            return self.chaos_test_bonus
        elif chaos_pass_rate >= 0.50:
            return self.chaos_test_bonus * 0.5
        return 0.0

    def get_bug_status(self, test_results: Dict[str, Any]) -> Dict[str, bool]:
        """
        Determine which bugs are fixed based on test results.

        Returns:
            Empty dictionary as bug tracking has been removed.
        """
        return {}

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
