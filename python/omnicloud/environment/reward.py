"""
OmniCloud Reward Function
Terminal Bench v2 - Ultra Sparse Reward System

This reward function is designed to be harder than NexusTrade:
- Very sparse rewards with 8 thresholds
- Regression penalties
- Service isolation bonuses (15 services)
- Chaos test bonuses
- Infrastructure state bonuses
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
    'tenants': ['test_tenants_*', 'test_tenant_*'],
    'compute': ['test_compute_*'],
    'network': ['test_network_*', 'test_cidr_*', 'test_firewall_*', 'test_vpn_*', 'test_dns_*', 'test_subnet_*', 'test_nat_*', 'test_peering_*', 'test_route_*'],
    'storage': ['test_storage_*'],
    'dns': ['test_dns_zone_*'],
    'loadbalancer': ['test_lb_*', 'test_health_check_*'],
    'secrets': ['test_secret_*', 'test_vault_*'],
    'config': ['test_config_*', 'test_template_*'],
    'deploy': ['test_rolling_*', 'test_blue_green_*', 'test_canary_*', 'test_rollback_*', 'test_deployment_*', 'test_hook_*'],
    'monitor': ['test_metric_*', 'test_alert_*', 'test_trace_*'],
    'billing': ['test_usage_*', 'test_proration_*', 'test_invoice_*', 'test_cost_*', 'test_discount_*', 'test_credit_*', 'test_overage_*', 'test_billing_*'],
    'audit': ['test_audit_*', 'test_correlation_*'],
    'compliance': ['test_compliance_*', 'test_policy_*'],
}

@dataclass
class RewardCalculator:
    """
    Ultra sparse reward calculator for OmniCloud.

    Features:
    - 8 threshold levels (same as NexusTrade)
    - Regression penalty: -0.20 per previously passing test that fails
    - Service isolation bonus: +0.015 per fully passing service (15 services)
    - Chaos test bonus: +0.10 for passing chaos tests
    - Infrastructure state bonus: +0.05 for passing state management tests
    """

    # Very sparse thresholds
    pass_thresholds: List[float] = field(default_factory=lambda: [
        0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0
    ])
    threshold_rewards: List[float] = field(default_factory=lambda: [
        0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0
    ])

    # Penalty and bonus weights
    regression_penalty: float = -0.20
    service_isolation_bonus: float = 0.015
    chaos_test_bonus: float = 0.10
    infra_state_bonus: float = 0.05
    efficiency_bonus_weight: float = 0.02

    def calculate_reward(
        self,
        test_results: Dict[str, Any],
        previous_results: Optional[Dict[str, Any]] = None,
        step_count: int = 0,
        max_steps: int = 300,
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

        # Component 1: Sparse threshold reward (60%)
        base_reward = self._calculate_sparse_reward(pass_rate) * 0.60

        # Component 2: Regression penalty
        regression = self._calculate_regression_penalty(test_results, previous_results)

        # Component 3: Service isolation bonus (15%)
        service_bonus = self._calculate_service_bonus(test_results) * 0.15

        # Component 4: Chaos test bonus (10%)
        chaos_bonus = self._calculate_chaos_bonus(test_results) * 0.10

        # Component 5: Infrastructure state bonus (10%)
        infra_bonus = self._calculate_infra_state_bonus(test_results) * 0.10

        # Component 6: Efficiency bonus (5%) - only if all tests pass
        efficiency = 0.0
        if pass_rate >= 1.0:
            efficiency = max(0, 1 - step_count / max_steps) * self.efficiency_bonus_weight

        total = base_reward + regression + service_bonus + chaos_bonus + infra_bonus + efficiency

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
            service_tests = []
            for pattern in patterns:
                prefix = pattern.replace('*', '')
                service_tests.extend([name for name in test_detail if name.startswith(prefix)])
            if service_tests and all(test_detail[name] for name in service_tests):
                passing_services += 1

        return self.service_isolation_bonus * passing_services

    def _calculate_chaos_bonus(self, test_results: Dict[str, Any]) -> float:
        """Calculate bonus for passing chaos tests."""
        test_detail = test_results.get('test_detail', {})
        if not test_detail:
            return 0.0

        # Chaos-related test prefixes (distributed consensus, multi-tenancy)
        chaos_prefixes = ['test_leader_', 'test_split_brain_', 'test_distributed_lock_',
                          'test_quorum_', 'test_version_vector_', 'test_gossip_',
                          'test_etcd_watch_', 'test_raft_', 'test_membership_',
                          'test_snapshot_', 'test_resource_isolation_', 'test_quota_',
                          'test_tenant_scope_', 'test_cache_tenant_', 'test_tenant_deletion_',
                          'test_soft_hard_', 'test_tenant_migration_', 'test_billing_isolation_']
        chaos_tests_total = 0
        chaos_tests_passed = 0
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

    def _calculate_infra_state_bonus(self, test_results: Dict[str, Any]) -> float:
        """Calculate bonus for passing infrastructure state management tests."""
        test_detail = test_results.get('test_detail', {})
        if not test_detail:
            return 0.0

        # Infrastructure state test prefixes
        infra_prefixes = ['test_state_transition_', 'test_eventual_consistency_',
                          'test_reconciliation_', 'test_desired_actual_',
                          'test_resource_dependency_', 'test_state_lock_',
                          'test_partial_apply_', 'test_state_serialization_',
                          'test_concurrent_modification_', 'test_orphaned_resource_',
                          'test_state_snapshot_', 'test_cross_region_sync_']
        infra_tests_total = 0
        infra_tests_passed = 0
        for test_name, passed in test_detail.items():
            for prefix in infra_prefixes:
                if test_name.startswith(prefix):
                    infra_tests_total += 1
                    if passed:
                        infra_tests_passed += 1
                    break

        if infra_tests_total == 0:
            return 0.0
        infra_pass_rate = infra_tests_passed / infra_tests_total
        if infra_pass_rate >= 0.90:
            return self.infra_state_bonus
        elif infra_pass_rate >= 0.50:
            return self.infra_state_bonus * 0.5
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
