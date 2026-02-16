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
        0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0
    ])
    threshold_rewards: List[float] = field(default_factory=lambda: [
        0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0
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

# Bug-to-test mapping for per-bug reward tracking
BUG_TEST_MAPPING = {
    # L1-L15: Setup Hell / Infrastructure
    "L1": [
        "tests/unit/test_infrastructure_state.py::TestSetupImports::test_import_success",
        "tests/unit/test_infrastructure_state.py::TestSetupImports::test_circular_import_resolved",
        "tests/unit/test_infrastructure_state.py::TestSetupImports::test_shared_clients_importable",
        "tests/unit/test_infrastructure_state.py::TestSetupImports::test_shared_events_importable",
        "tests/unit/test_infrastructure_state.py::TestSetupImports::test_shared_infra_importable",
    ],
    "L2": [
        "tests/unit/test_infrastructure_state.py::TestTenantMigrations::test_tenant_migration_exists",
        "tests/unit/test_infrastructure_state.py::TestTenantMigrations::test_migration_files_present",
    ],
    "L3": [
        "tests/unit/test_infrastructure_state.py::TestKafkaTopics::test_kafka_topic_exists",
        "tests/unit/test_infrastructure_state.py::TestKafkaTopics::test_topic_creation_enabled",
    ],
    "L4": [
        "tests/unit/test_infrastructure_state.py::TestMigrationOrder::test_migration_order_correct",
        "tests/unit/test_infrastructure_state.py::TestMigrationOrder::test_dependency_chain_valid",
    ],
    "L5": [
        "tests/unit/test_infrastructure_state.py::TestServiceStartup::test_service_startup_order",
        "tests/unit/test_infrastructure_state.py::TestServiceStartup::test_dependency_wait_configured",
    ],
    "L6": [
        "tests/unit/test_infrastructure_state.py::TestConsulACL::test_consul_acl_bootstrap",
        "tests/unit/test_infrastructure_state.py::TestConsulACL::test_consul_token_valid",
    ],
    "L7": [
        "tests/unit/test_infrastructure_state.py::TestEtcdConnection::test_etcd_connection_scheme",
        "tests/unit/test_infrastructure_state.py::TestEtcdConnection::test_etcd_client_connects",
    ],
    "L8": [
        "tests/unit/test_infrastructure_state.py::TestVaultUnseal::test_vault_unseal_configured",
        "tests/unit/test_infrastructure_state.py::TestVaultUnseal::test_vault_health_check",
    ],
    "L9": [
        "tests/unit/test_infrastructure_state.py::TestMinioBuckets::test_minio_bucket_creation",
        "tests/unit/test_infrastructure_state.py::TestMinioBuckets::test_minio_bucket_exists",
    ],
    "L10": [
        "tests/unit/test_infrastructure_state.py::TestCeleryBroker::test_celery_broker_url",
        "tests/unit/test_infrastructure_state.py::TestCeleryBroker::test_celery_worker_connects",
    ],
    "L11": [
        "tests/unit/test_infrastructure_state.py::TestCORS::test_cors_configuration",
        "tests/unit/test_infrastructure_state.py::TestCORS::test_inter_service_calls_allowed",
    ],
    "L12": [
        "tests/unit/test_infrastructure_state.py::TestSchemaValidation::test_schema_validation_version",
        "tests/unit/test_infrastructure_state.py::TestSchemaValidation::test_pydantic_compat",
    ],
    "L13": [
        "tests/unit/test_infrastructure_state.py::TestConsulHealthCheck::test_consul_health_check_url",
        "tests/unit/test_infrastructure_state.py::TestConsulHealthCheck::test_service_registration_complete",
    ],
    "L14": [
        "tests/unit/test_infrastructure_state.py::TestWorkerSerializer::test_worker_serializer",
        "tests/unit/test_infrastructure_state.py::TestWorkerSerializer::test_task_serialization_roundtrip",
    ],
    "L15": [
        "tests/unit/test_infrastructure_state.py::TestEnvVarParsing::test_env_var_bool_parsing",
        "tests/unit/test_infrastructure_state.py::TestEnvVarParsing::test_string_false_is_falsy",
    ],

    # A1-A12: Infrastructure State Management
    "A1": [
        "tests/unit/test_infrastructure_state.py::TestStateTransitions::test_state_transition_lock",
        "tests/unit/test_infrastructure_state.py::TestStateTransitions::test_concurrent_state_transitions_safe",
        "tests/unit/test_infrastructure_state.py::TestStateTransitions::test_invalid_transition_rejected",
        "tests/unit/test_infrastructure_state.py::TestStateTransitions::test_valid_transition_accepted",
    ],
    "A2": [
        "tests/unit/test_infrastructure_state.py::TestEventualConsistency::test_eventual_consistency_converges",
        "tests/unit/test_infrastructure_state.py::TestEventualConsistency::test_state_sync_timeout",
    ],
    "A3": [
        "tests/unit/test_infrastructure_state.py::TestReconciliation::test_reconciliation_loop_terminates",
        "tests/unit/test_infrastructure_state.py::TestReconciliation::test_reconciliation_max_iterations",
        "tests/unit/test_cross_module_chains.py::TestReconcileWithRollback::test_reconcile_with_rollback",
    ],
    "A4": [
        "tests/unit/test_infrastructure_state.py::TestDriftDetection::test_desired_actual_state_diff",
        "tests/unit/test_infrastructure_state.py::TestDriftDetection::test_drift_detection_accurate",
        "tests/unit/test_infrastructure_state.py::TestDriftDetection::test_drift_detection_float_precision",
        "tests/unit/test_infrastructure_state.py::TestDriftDetection::test_drift_detection_none_vs_missing",
    ],
    "A5": [
        "tests/unit/test_infrastructure_state.py::TestDependencyGraph::test_resource_dependency_cycle_detection",
        "tests/unit/test_infrastructure_state.py::TestDependencyGraph::test_dag_validation",
    ],
    "A6": [
        "tests/unit/test_infrastructure_state.py::TestStateLock::test_state_lock_no_deadlock",
        "tests/unit/test_infrastructure_state.py::TestStateLock::test_lock_ordering_consistent",
    ],
    "A7": [
        "tests/unit/test_infrastructure_state.py::TestPartialRollback::test_partial_apply_rollback",
        "tests/unit/test_infrastructure_state.py::TestPartialRollback::test_rollback_completeness",
        "tests/unit/test_cross_module_chains.py::TestReconcileWithRollback::test_reconcile_with_rollback",
    ],
    "A8": [
        "tests/unit/test_infrastructure_state.py::TestStateSerialization::test_state_serialization_version",
        "tests/unit/test_infrastructure_state.py::TestStateSerialization::test_backward_compat_deserialization",
    ],
    "A9": [
        "tests/unit/test_infrastructure_state.py::TestConcurrentModification::test_concurrent_modification_detection",
        "tests/unit/test_infrastructure_state.py::TestConcurrentModification::test_lost_update_prevented",
    ],
    "A10": [
        "tests/unit/test_infrastructure_state.py::TestOrphanCleanup::test_orphaned_resource_cleanup",
        "tests/unit/test_infrastructure_state.py::TestOrphanCleanup::test_orphan_detection_complete",
    ],
    "A11": [
        "tests/unit/test_infrastructure_state.py::TestStateSnapshot::test_state_snapshot_integrity",
        "tests/unit/test_infrastructure_state.py::TestStateSnapshot::test_snapshot_restore_consistent",
    ],
    "A12": [
        "tests/unit/test_infrastructure_state.py::TestCrossRegionSync::test_cross_region_sync_eventual",
        "tests/unit/test_infrastructure_state.py::TestCrossRegionSync::test_sync_lag_bounded",
    ],

    # B1-B10: Distributed Consensus
    "B1": [
        "tests/chaos/test_distributed_consensus.py::TestLeaderElection::test_leader_election_single_winner",
        "tests/chaos/test_distributed_consensus.py::TestLeaderElection::test_election_race_safe",
        "tests/chaos/test_distributed_consensus.py::TestLeaderElection::test_leader_has_fencing_token",
        "tests/chaos/test_distributed_consensus.py::TestLeaderElection::test_resignation_clears_leader",
        "tests/chaos/test_distributed_consensus.py::TestLeaderElection::test_re_election_after_resign",
        "tests/chaos/test_distributed_consensus.py::TestLeaderElection::test_get_leader_returns_id",
    ],
    "B2": [
        "tests/chaos/test_distributed_consensus.py::TestSplitBrain::test_split_brain_detection",
        "tests/chaos/test_distributed_consensus.py::TestSplitBrain::test_partition_handling_consistent",
        "tests/chaos/test_distributed_consensus.py::TestSplitBrain::test_partition_minority_no_writes",
        "tests/chaos/test_distributed_consensus.py::TestSplitBrain::test_partition_majority_continues",
    ],
    "B3": [
        "tests/chaos/test_distributed_consensus.py::TestDistributedLockTTL::test_distributed_lock_not_stolen",
        "tests/chaos/test_distributed_consensus.py::TestDistributedLockTTL::test_lock_extension_works",
        "tests/chaos/test_distributed_consensus.py::TestDistributedLockTTL::test_lock_context_manager",
        "tests/chaos/test_distributed_consensus.py::TestDistributedLockTTL::test_lock_release",
        "tests/chaos/test_distributed_consensus.py::TestDistributedLockTTL::test_lock_blocking_acquisition",
        "tests/chaos/test_distributed_consensus.py::TestDistributedLockTTL::test_lock_non_blocking_acquisition",
        "tests/unit/test_cross_module_chains.py::TestDeploymentLockTTL::test_deployment_lock_ttl",
    ],
    "B4": [
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_quorum_majority_required",
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_minority_write_rejected",
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_majority_accepted",
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_all_nodes_quorum",
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_minimum_for_quorum_correct",
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_single_node_quorum",
        "tests/chaos/test_distributed_consensus.py::TestQuorum::test_zero_nodes_no_quorum",
    ],
    "B5": [
        "tests/chaos/test_distributed_consensus.py::TestVersionVectors::test_version_vector_merge_correct",
        "tests/chaos/test_distributed_consensus.py::TestVersionVectors::test_concurrent_version_resolution",
        "tests/chaos/test_distributed_consensus.py::TestVersionVectors::test_version_vector_increment",
        "tests/chaos/test_distributed_consensus.py::TestVersionVectors::test_version_vector_dominates",
        "tests/chaos/test_distributed_consensus.py::TestVersionVectors::test_merge_with_new_node",
        "tests/chaos/test_distributed_consensus.py::TestVersionVectors::test_merge_empty_vectors",
    ],
    "B6": [
        "tests/chaos/test_distributed_consensus.py::TestGossipOrdering::test_gossip_message_ordering",
        "tests/chaos/test_distributed_consensus.py::TestGossipOrdering::test_gossip_eventual_delivery",
        "tests/chaos/test_distributed_consensus.py::TestGossipOrdering::test_gossip_deduplication",
        "tests/chaos/test_distributed_consensus.py::TestGossipOrdering::test_gossip_anti_entropy",
    ],
    "B7": [
        "tests/chaos/test_distributed_consensus.py::TestEtcdWatch::test_etcd_watch_no_revision_gap",
        "tests/chaos/test_distributed_consensus.py::TestEtcdWatch::test_watch_continuity",
        "tests/chaos/test_distributed_consensus.py::TestEtcdWatch::test_watch_compaction_handling",
        "tests/chaos/test_distributed_consensus.py::TestEtcdWatch::test_watch_event_ordering",
    ],
    "B8": [
        "tests/chaos/test_distributed_consensus.py::TestRaftLogCompaction::test_raft_log_compaction_safe",
        "tests/chaos/test_distributed_consensus.py::TestRaftLogCompaction::test_compaction_no_data_loss",
        "tests/chaos/test_distributed_consensus.py::TestRaftLogCompaction::test_compaction_snapshot_complete",
        "tests/chaos/test_distributed_consensus.py::TestRaftLogCompaction::test_compaction_idempotent",
    ],
    "B9": [
        "tests/chaos/test_distributed_consensus.py::TestMembershipChange::test_membership_change_during_election",
        "tests/chaos/test_distributed_consensus.py::TestMembershipChange::test_config_change_safe",
        "tests/chaos/test_distributed_consensus.py::TestMembershipChange::test_node_removal_safe",
        "tests/chaos/test_distributed_consensus.py::TestMembershipChange::test_node_addition_safe",
    ],
    "B10": [
        "tests/chaos/test_distributed_consensus.py::TestSnapshotTransfer::test_snapshot_transfer_integrity",
        "tests/chaos/test_distributed_consensus.py::TestSnapshotTransfer::test_snapshot_checksum_valid",
        "tests/chaos/test_distributed_consensus.py::TestSnapshotTransfer::test_snapshot_partial_transfer_detected",
        "tests/chaos/test_distributed_consensus.py::TestSnapshotTransfer::test_snapshot_retry_on_failure",
    ],

    # C1-C8: Multi-Tenancy
    "C1": [
        "tests/chaos/test_multi_tenancy.py::TestResourceIsolation::test_resource_isolation_enforced",
        "tests/chaos/test_multi_tenancy.py::TestResourceIsolation::test_cross_tenant_resource_blocked",
        "tests/chaos/test_multi_tenancy.py::TestResourceIsolation::test_empty_tenant_id_rejected",
        "tests/chaos/test_multi_tenancy.py::TestResourceIsolation::test_none_tenant_id_rejected",
        "tests/chaos/test_multi_tenancy.py::TestResourceIsolation::test_resource_type_filtering",
        "tests/chaos/test_multi_tenancy.py::TestResourceIsolation::test_cross_tenant_listing_prevented",
        "tests/unit/test_cross_module_chains.py::TestBillingTenantIsolation::test_billing_tenant_isolation",
    ],
    "C2": [
        "tests/chaos/test_multi_tenancy.py::TestQuotaEnforcement::test_quota_enforcement_atomic",
        "tests/chaos/test_multi_tenancy.py::TestQuotaEnforcement::test_quota_race_prevented",
        "tests/chaos/test_multi_tenancy.py::TestQuotaEnforcement::test_quota_types_independent",
        "tests/chaos/test_multi_tenancy.py::TestQuotaEnforcement::test_quota_bulk_request",
        "tests/chaos/test_multi_tenancy.py::TestQuotaEnforcement::test_quota_zero_remaining",
        "tests/unit/test_cross_module_chains.py::TestQuotaWithPrecision::test_quota_with_precision",
    ],
    "C3": [
        "tests/chaos/test_multi_tenancy.py::TestTenantScoping::test_tenant_scope_in_queries",
        "tests/chaos/test_multi_tenancy.py::TestTenantScoping::test_query_filter_tenant_id",
        "tests/chaos/test_multi_tenancy.py::TestTenantScoping::test_join_queries_scoped",
        "tests/chaos/test_multi_tenancy.py::TestTenantScoping::test_aggregate_queries_scoped",
    ],
    "C4": [
        "tests/chaos/test_multi_tenancy.py::TestCacheTenantIsolation::test_cache_tenant_isolation",
        "tests/chaos/test_multi_tenancy.py::TestCacheTenantIsolation::test_cross_tenant_cache_miss",
        "tests/chaos/test_multi_tenancy.py::TestCacheTenantIsolation::test_cache_key_without_prefix",
        "tests/chaos/test_multi_tenancy.py::TestCacheTenantIsolation::test_cache_invalidation_per_tenant",
    ],
    "C5": [
        "tests/chaos/test_multi_tenancy.py::TestTenantDeletion::test_tenant_deletion_cleanup",
        "tests/chaos/test_multi_tenancy.py::TestTenantDeletion::test_orphan_resources_removed",
        "tests/chaos/test_multi_tenancy.py::TestTenantDeletion::test_deletion_does_not_affect_others",
        "tests/chaos/test_multi_tenancy.py::TestTenantDeletion::test_deletion_nonexistent_tenant",
        "tests/chaos/test_multi_tenancy.py::TestTenantDeletion::test_deletion_idempotent",
    ],
    "C6": [
        "tests/chaos/test_multi_tenancy.py::TestSoftHardLimits::test_soft_hard_limit_distinction",
        "tests/chaos/test_multi_tenancy.py::TestSoftHardLimits::test_hard_limit_enforced",
        "tests/chaos/test_multi_tenancy.py::TestSoftHardLimits::test_under_soft_limit_allowed",
        "tests/chaos/test_multi_tenancy.py::TestSoftHardLimits::test_soft_limit_with_overage",
    ],
    "C7": [
        "tests/chaos/test_multi_tenancy.py::TestTenantMigration::test_tenant_migration_data_integrity",
        "tests/chaos/test_multi_tenancy.py::TestTenantMigration::test_migration_no_data_loss",
        "tests/chaos/test_multi_tenancy.py::TestTenantMigration::test_migration_other_tenants_unaffected",
        "tests/chaos/test_multi_tenancy.py::TestTenantMigration::test_migration_empty_tenant",
    ],
    "C8": [
        "tests/chaos/test_multi_tenancy.py::TestBillingIsolation::test_billing_isolation_correct",
        "tests/chaos/test_multi_tenancy.py::TestBillingIsolation::test_cross_tenant_billing_prevented",
        "tests/chaos/test_multi_tenancy.py::TestBillingIsolation::test_billing_zero_usage",
        "tests/chaos/test_multi_tenancy.py::TestBillingIsolation::test_billing_total_zero_handled",
        "tests/chaos/test_multi_tenancy.py::TestBillingIsolation::test_billing_precision_maintained",
        "tests/chaos/test_multi_tenancy.py::TestBillingIsolation::test_billing_all_tenants_sum_to_total",
    ],

    # D1-D10: Network Management
    "D1": [
        "tests/unit/test_network_management.py::TestCIDRAllocation::test_cidr_no_overlap",
        "tests/unit/test_network_management.py::TestCIDRAllocation::test_subnet_allocation_unique",
        "tests/unit/test_network_management.py::TestCIDRAllocation::test_cidr_allocation_returns_valid",
        "tests/unit/test_network_management.py::TestCIDRAllocation::test_cidr_within_parent",
    ],
    "D2": [
        "tests/unit/test_network_management.py::TestFirewallOrdering::test_firewall_rule_ordering",
        "tests/unit/test_network_management.py::TestFirewallOrdering::test_rule_priority_respected",
        "tests/unit/test_network_management.py::TestFirewallOrdering::test_same_priority_stable",
        "tests/unit/test_network_management.py::TestFirewallOrdering::test_empty_rules",
    ],
    "D3": [
        "tests/unit/test_network_management.py::TestVPNMTU::test_vpn_mtu_correct",
        "tests/unit/test_network_management.py::TestVPNMTU::test_mtu_negotiation",
        "tests/unit/test_network_management.py::TestVPNMTU::test_mtu_default_overhead",
    ],
    "D4": [
        "tests/unit/test_network_management.py::TestDNSResolution::test_dns_no_circular_cname",
        "tests/unit/test_network_management.py::TestDNSResolution::test_cname_chain_resolution",
        "tests/unit/test_network_management.py::TestDNSResolution::test_cname_depth_limit",
        "tests/unit/test_network_management.py::TestDNSResolution::test_cname_direct_resolution",
        "tests/unit/test_network_management.py::TestDNSResolution::test_cname_single_hop",
        "tests/unit/test_cross_module_chains.py::TestDnsWithSubnetExhaustion::test_dns_with_subnet_exhaustion",
    ],
    "D5": [
        "tests/unit/test_network_management.py::TestSubnetExhaustion::test_subnet_exhaustion_detected",
        "tests/unit/test_network_management.py::TestSubnetExhaustion::test_allocation_fails_when_full",
        "tests/unit/test_network_management.py::TestSubnetExhaustion::test_subnet_not_exhausted",
        "tests/unit/test_network_management.py::TestSubnetExhaustion::test_empty_subnet",
        "tests/unit/test_cross_module_chains.py::TestDnsWithSubnetExhaustion::test_dns_with_subnet_exhaustion",
    ],
    "D6": [
        "tests/unit/test_network_management.py::TestSecurityGroupDedup::test_security_group_dedup",
        "tests/unit/test_network_management.py::TestSecurityGroupDedup::test_duplicate_rule_rejected",
        "tests/unit/test_network_management.py::TestSecurityGroupDedup::test_different_protocols_kept",
        "tests/unit/test_network_management.py::TestSecurityGroupDedup::test_empty_rules",
    ],
    "D7": [
        "tests/unit/test_network_management.py::TestRouteTablePropagation::test_route_propagation_complete",
        "tests/unit/test_network_management.py::TestRouteTablePropagation::test_route_table_convergence",
    ],
    "D8": [
        "tests/unit/test_network_management.py::TestNATPortAllocation::test_nat_port_allocation_atomic",
        "tests/unit/test_network_management.py::TestNATPortAllocation::test_nat_port_no_conflict",
        "tests/unit/test_network_management.py::TestNATPortAllocation::test_nat_port_range",
        "tests/unit/test_network_management.py::TestNATPortAllocation::test_nat_port_exhaustion",
    ],
    "D9": [
        "tests/unit/test_network_management.py::TestHealthCheckFlap::test_lb_health_check_stability",
        "tests/unit/test_network_management.py::TestHealthCheckFlap::test_flap_detection",
        "tests/unit/test_network_management.py::TestHealthCheckFlap::test_consecutive_failures_marks_unhealthy",
        "tests/unit/test_network_management.py::TestHealthCheckFlap::test_consecutive_successes_marks_healthy",
        "tests/unit/test_network_management.py::TestHealthCheckFlap::test_health_check_defaults",
    ],
    "D10": [
        "tests/unit/test_network_management.py::TestPeeringRouting::test_peering_symmetric_routing",
        "tests/unit/test_network_management.py::TestPeeringRouting::test_bidirectional_peering",
    ],

    # E1-E8: Resource Scheduling
    "E1": [
        "tests/unit/test_resource_scheduling.py::TestBinPacking::test_bin_packing_no_overcommit",
        "tests/unit/test_resource_scheduling.py::TestBinPacking::test_capacity_respected",
        "tests/unit/test_resource_scheduling.py::TestBinPacking::test_bin_packing_best_fit",
        "tests/unit/test_resource_scheduling.py::TestBinPacking::test_float_precision_cpu",
        "tests/unit/test_resource_scheduling.py::TestBinPacking::test_no_nodes_returns_none",
        "tests/unit/test_resource_scheduling.py::TestBinPacking::test_insufficient_capacity_returns_none",
        "tests/unit/test_cross_module_chains.py::TestQuotaWithPrecision::test_quota_with_precision",
    ],
    "E2": [
        "tests/unit/test_resource_scheduling.py::TestAffinityRules::test_affinity_rule_evaluation_order",
        "tests/unit/test_resource_scheduling.py::TestAffinityRules::test_affinity_priority",
        "tests/unit/test_resource_scheduling.py::TestAffinityRules::test_affinity_no_match_fallback",
    ],
    "E3": [
        "tests/unit/test_resource_scheduling.py::TestAntiAffinity::test_anti_affinity_race_safe",
        "tests/unit/test_resource_scheduling.py::TestAntiAffinity::test_anti_affinity_concurrent",
    ],
    "E4": [
        "tests/unit/test_resource_scheduling.py::TestResourceLimitPrecision::test_resource_limit_precision",
        "tests/unit/test_resource_scheduling.py::TestResourceLimitPrecision::test_float_limit_handling",
    ],
    "E5": [
        "tests/unit/test_resource_scheduling.py::TestSpotPreemption::test_spot_preemption_graceful",
        "tests/unit/test_resource_scheduling.py::TestSpotPreemption::test_preemption_notification",
    ],
    "E6": [
        "tests/unit/test_resource_scheduling.py::TestPlacementGroup::test_placement_capacity_check",
        "tests/unit/test_resource_scheduling.py::TestPlacementGroup::test_placement_group_full",
        "tests/unit/test_resource_scheduling.py::TestPlacementGroup::test_placement_group_available",
        "tests/unit/test_resource_scheduling.py::TestPlacementGroup::test_placement_group_empty",
    ],
    "E7": [
        "tests/unit/test_resource_scheduling.py::TestNodeDrain::test_node_drain_race_safe",
        "tests/unit/test_resource_scheduling.py::TestNodeDrain::test_drain_concurrent_schedule",
    ],
    "E8": [
        "tests/unit/test_resource_scheduling.py::TestReservationExpiry::test_reservation_expiry_cleanup",
        "tests/unit/test_resource_scheduling.py::TestReservationExpiry::test_expired_reservation_released",
        "tests/unit/test_resource_scheduling.py::TestReservationExpiry::test_active_reservation_kept",
        "tests/unit/test_resource_scheduling.py::TestReservationExpiry::test_reservation_is_expired",
    ],

    # F1-F10: Deployment Pipeline
    "F1": [
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_batch_size_correct",
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_update_count",
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_single_batch",
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_batch_one",
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_covers_all_replicas",
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_no_duplicate_instances",
        "tests/integration/test_deployment_pipeline.py::TestRollingUpdate::test_rolling_zero_replicas",
    ],
    "F2": [
        "tests/integration/test_deployment_pipeline.py::TestBlueGreenSwitch::test_blue_green_switch_atomic",
        "tests/integration/test_deployment_pipeline.py::TestBlueGreenSwitch::test_blue_green_no_downtime",
        "tests/integration/test_deployment_pipeline.py::TestBlueGreenSwitch::test_blue_green_rollback",
        "tests/integration/test_deployment_pipeline.py::TestBlueGreenSwitch::test_blue_green_health_verified",
    ],
    "F3": [
        "tests/integration/test_deployment_pipeline.py::TestCanaryEvaluation::test_canary_metric_window_correct",
        "tests/integration/test_deployment_pipeline.py::TestCanaryEvaluation::test_canary_evaluation_period",
        "tests/integration/test_deployment_pipeline.py::TestCanaryEvaluation::test_canary_high_error_rate_rejected",
        "tests/integration/test_deployment_pipeline.py::TestCanaryEvaluation::test_canary_high_latency_rejected",
        "tests/integration/test_deployment_pipeline.py::TestCanaryEvaluation::test_canary_percentage_valid",
    ],
    "F4": [
        "tests/integration/test_deployment_pipeline.py::TestRollbackVersion::test_rollback_version_correct",
        "tests/integration/test_deployment_pipeline.py::TestRollbackVersion::test_rollback_to_previous",
        "tests/integration/test_deployment_pipeline.py::TestRollbackVersion::test_rollback_first_version",
        "tests/integration/test_deployment_pipeline.py::TestRollbackVersion::test_rollback_empty_history",
    ],
    "F5": [
        "tests/integration/test_deployment_pipeline.py::TestDeploymentLock::test_deployment_lock_not_stolen",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentLock::test_lock_during_long_deploy",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentLock::test_lock_prevents_concurrent_deploy",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentLock::test_lock_acquired_by_first_deployer",
        "tests/unit/test_cross_module_chains.py::TestDeploymentLockTTL::test_deployment_lock_ttl",
    ],
    "F6": [
        "tests/integration/test_deployment_pipeline.py::TestHealthCheckGrace::test_health_check_grace_period",
        "tests/integration/test_deployment_pipeline.py::TestHealthCheckGrace::test_grace_period_respected",
        "tests/integration/test_deployment_pipeline.py::TestHealthCheckGrace::test_grace_period_zero",
        "tests/integration/test_deployment_pipeline.py::TestHealthCheckGrace::test_grace_period_default",
    ],
    "F7": [
        "tests/integration/test_deployment_pipeline.py::TestDeploymentDependencyOrder::test_deployment_dependency_order",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentDependencyOrder::test_dependency_graph_sort",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentDependencyOrder::test_no_dependencies_first",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentDependencyOrder::test_empty_deployment_list",
    ],
    "F8": [
        "tests/integration/test_deployment_pipeline.py::TestParallelDeploy::test_parallel_deploy_no_conflict",
        "tests/integration/test_deployment_pipeline.py::TestParallelDeploy::test_resource_contention_handled",
        "tests/integration/test_deployment_pipeline.py::TestParallelDeploy::test_independent_deploys_parallel",
        "tests/integration/test_deployment_pipeline.py::TestParallelDeploy::test_dependent_deploys_serial",
    ],
    "F9": [
        "tests/integration/test_deployment_pipeline.py::TestDeploymentEventOrdering::test_deployment_event_ordering",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentEventOrdering::test_event_sequence_correct",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentEventOrdering::test_event_timestamps_monotonic",
        "tests/integration/test_deployment_pipeline.py::TestDeploymentEventOrdering::test_event_has_required_fields",
    ],
    "F10": [
        "tests/integration/test_deployment_pipeline.py::TestHookExecution::test_hook_execution_order",
        "tests/integration/test_deployment_pipeline.py::TestHookExecution::test_pre_post_hooks_correct",
        "tests/integration/test_deployment_pipeline.py::TestHookExecution::test_hook_failure_reported",
        "tests/integration/test_deployment_pipeline.py::TestHookExecution::test_empty_hooks",
        "tests/integration/test_deployment_pipeline.py::TestHookExecution::test_hooks_capture_results",
    ],

    # G1-G10: Database Transactions / Service Communication
    "G1": [
        "tests/integration/test_service_communication.py::TestCrossDBIsolation::test_cross_db_isolation",
        "tests/integration/test_service_communication.py::TestCrossDBIsolation::test_phantom_read_prevention",
        "tests/integration/test_service_communication.py::TestCrossDBIsolation::test_read_committed_isolation",
        "tests/integration/test_service_communication.py::TestCrossDBIsolation::test_snapshot_isolation",
    ],
    "G2": [
        "tests/integration/test_service_communication.py::TestConnectionPool::test_connection_pool_limits",
        "tests/integration/test_service_communication.py::TestConnectionPool::test_pool_exhaustion_handled",
        "tests/integration/test_service_communication.py::TestConnectionPool::test_connection_returned_on_error",
        "tests/integration/test_service_communication.py::TestConnectionPool::test_pool_health_monitoring",
    ],
    "G3": [
        "tests/integration/test_service_communication.py::TestSagaCompensation::test_saga_compensation_order",
        "tests/integration/test_service_communication.py::TestSagaCompensation::test_rollback_sequence",
        "tests/integration/test_service_communication.py::TestSagaCompensation::test_partial_saga_failure",
        "tests/integration/test_service_communication.py::TestSagaCompensation::test_compensation_idempotent",
    ],
    "G4": [
        "tests/integration/test_service_communication.py::TestOutboxPattern::test_outbox_delivery_guaranteed",
        "tests/integration/test_service_communication.py::TestOutboxPattern::test_event_publication_complete",
        "tests/integration/test_service_communication.py::TestOutboxPattern::test_outbox_ordering_preserved",
        "tests/integration/test_service_communication.py::TestOutboxPattern::test_outbox_duplicate_prevention",
    ],
    "G5": [
        "tests/integration/test_service_communication.py::TestReplicaLag::test_replica_lag_handling",
        "tests/integration/test_service_communication.py::TestReplicaLag::test_read_your_writes",
        "tests/integration/test_service_communication.py::TestReplicaLag::test_replica_staleness_detection",
        "tests/integration/test_service_communication.py::TestReplicaLag::test_failover_to_primary",
    ],
    "G6": [
        "tests/integration/test_service_communication.py::TestOptimisticLocking::test_optimistic_locking_retry",
        "tests/integration/test_service_communication.py::TestOptimisticLocking::test_concurrent_update_handled",
        "tests/integration/test_service_communication.py::TestOptimisticLocking::test_version_monotonic",
        "tests/integration/test_service_communication.py::TestOptimisticLocking::test_no_lost_update",
    ],
    "G7": [
        "tests/integration/test_service_communication.py::TestCrossDBReferential::test_cross_db_referential",
        "tests/integration/test_service_communication.py::TestCrossDBReferential::test_orphan_reference_prevented",
        "tests/integration/test_service_communication.py::TestCrossDBReferential::test_reference_validation",
        "tests/integration/test_service_communication.py::TestCrossDBReferential::test_cascade_across_databases",
    ],
    "G8": [
        "tests/integration/test_service_communication.py::TestBatchInsert::test_batch_insert_atomicity",
        "tests/integration/test_service_communication.py::TestBatchInsert::test_partial_failure_rollback",
        "tests/integration/test_service_communication.py::TestBatchInsert::test_batch_size_limits",
        "tests/integration/test_service_communication.py::TestBatchInsert::test_batch_idempotent",
    ],
    "G9": [
        "tests/integration/test_service_communication.py::TestIndexHint::test_index_hint_plan",
        "tests/integration/test_service_communication.py::TestIndexHint::test_query_performance_acceptable",
        "tests/integration/test_service_communication.py::TestIndexHint::test_missing_index_detected",
        "tests/integration/test_service_communication.py::TestIndexHint::test_composite_index_order",
    ],
    "G10": [
        "tests/integration/test_service_communication.py::TestLockOrdering::test_lock_ordering_consistent",
        "tests/integration/test_service_communication.py::TestLockOrdering::test_deadlock_prevention",
        "tests/integration/test_service_communication.py::TestLockOrdering::test_lock_manager_release_order",
        "tests/integration/test_service_communication.py::TestLockOrdering::test_lock_acquisition_timeout",
        "tests/unit/test_infrastructure_state.py::TestStateLock::test_lock_ordering_consistent",
        "tests/unit/test_cross_module_chains.py::TestStateTransitionWithLocking::test_state_transition_with_locking",
    ],

    # H1-H8: Billing & Metering
    "H1": [
        "tests/unit/test_billing_metering.py::TestUsageMetering::test_usage_metering_clock_aligned",
        "tests/unit/test_billing_metering.py::TestUsageMetering::test_clock_skew_handling",
    ],
    "H2": [
        "tests/unit/test_billing_metering.py::TestProration::test_proration_precision",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_decimal_correct",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_full_month",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_zero_days",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_zero_total",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_small_amounts",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_large_amounts",
        "tests/unit/test_billing_metering.py::TestProration::test_proration_odd_days",
    ],
    "H3": [
        "tests/unit/test_billing_metering.py::TestInvoiceGeneration::test_invoice_generation_atomic",
        "tests/unit/test_billing_metering.py::TestInvoiceGeneration::test_invoice_no_duplicate",
        "tests/unit/test_billing_metering.py::TestInvoiceGeneration::test_different_tenants_separate_invoices",
        "tests/unit/test_billing_metering.py::TestInvoiceGeneration::test_different_periods_separate_invoices",
    ],
    "H4": [
        "tests/unit/test_billing_metering.py::TestCostAllocation::test_cost_allocation_attribution",
        "tests/unit/test_billing_metering.py::TestCostAllocation::test_tenant_cost_correct",
        "tests/unit/test_billing_metering.py::TestCostAllocation::test_single_tenant_full_cost",
        "tests/unit/test_billing_metering.py::TestCostAllocation::test_zero_usage_zero_cost",
        "tests/unit/test_billing_metering.py::TestCostAllocation::test_uneven_split",
        "tests/unit/test_cross_module_chains.py::TestBillingTenantIsolation::test_billing_tenant_isolation",
    ],
    "H5": [
        "tests/unit/test_billing_metering.py::TestDiscountStacking::test_discount_stacking_order",
        "tests/unit/test_billing_metering.py::TestDiscountStacking::test_discount_precedence",
        "tests/unit/test_billing_metering.py::TestDiscountStacking::test_no_discounts",
        "tests/unit/test_billing_metering.py::TestDiscountStacking::test_discount_floor_zero",
    ],
    "H6": [
        "tests/unit/test_billing_metering.py::TestCreditApplication::test_credit_application_timing",
        "tests/unit/test_billing_metering.py::TestCreditApplication::test_credit_before_charge",
        "tests/unit/test_billing_metering.py::TestCreditApplication::test_credit_exceeds_total",
        "tests/unit/test_billing_metering.py::TestCreditApplication::test_zero_credit",
    ],
    "H7": [
        "tests/unit/test_billing_metering.py::TestOverageCharge::test_overage_charge_threshold",
        "tests/unit/test_billing_metering.py::TestOverageCharge::test_overage_boundary_correct",
        "tests/unit/test_billing_metering.py::TestOverageCharge::test_under_limit_no_overage",
        "tests/unit/test_billing_metering.py::TestOverageCharge::test_zero_usage_no_overage",
    ],
    "H8": [
        "tests/unit/test_billing_metering.py::TestBillingCycleBoundary::test_billing_cycle_boundary",
        "tests/unit/test_billing_metering.py::TestBillingCycleBoundary::test_midnight_utc_boundary",
        "tests/unit/test_billing_metering.py::TestBillingCycleBoundary::test_december_boundary",
        "tests/unit/test_billing_metering.py::TestBillingCycleBoundary::test_timezone_aware_boundaries",
    ],

    # I1-I10: Security & Compliance
    "I1": [
        "tests/security/test_vulnerabilities.py::TestSQLInjection::test_sql_injection_blocked",
        "tests/security/test_vulnerabilities.py::TestSQLInjection::test_parameterized_query_usage",
        "tests/security/test_vulnerabilities.py::TestSQLInjection::test_sql_injection_in_search",
        "tests/security/test_vulnerabilities.py::TestSQLInjection::test_sql_injection_in_filter",
        "tests/security/test_vulnerabilities.py::TestSQLInjection::test_numeric_injection_prevented",
    ],
    "I2": [
        "tests/security/test_vulnerabilities.py::TestSSRF::test_ssrf_url_blocked",
        "tests/security/test_vulnerabilities.py::TestSSRF::test_internal_url_validation",
        "tests/security/test_vulnerabilities.py::TestSSRF::test_ssrf_redirect_blocked",
        "tests/security/test_vulnerabilities.py::TestSSRF::test_dns_rebinding_protection",
    ],
    "I3": [
        "tests/security/test_vulnerabilities.py::TestPrivilegeEscalation::test_privilege_escalation_blocked",
        "tests/security/test_vulnerabilities.py::TestPrivilegeEscalation::test_role_inheritance_safe",
        "tests/security/test_vulnerabilities.py::TestPrivilegeEscalation::test_nonexistent_role",
        "tests/security/test_vulnerabilities.py::TestPrivilegeEscalation::test_role_without_inheritance",
        "tests/security/test_vulnerabilities.py::TestPrivilegeEscalation::test_deep_inheritance_chain",
    ],
    "I4": [
        "tests/security/test_vulnerabilities.py::TestRateLimitBypass::test_rate_limit_bypass_blocked",
        "tests/security/test_vulnerabilities.py::TestRateLimitBypass::test_rate_limit_uniform",
        "tests/security/test_vulnerabilities.py::TestRateLimitBypass::test_forwarded_for_with_proxy",
        "tests/security/test_vulnerabilities.py::TestRateLimitBypass::test_missing_client_fallback",
    ],
    "I5": [
        "tests/security/test_vulnerabilities.py::TestIDOR::test_idor_tenant_blocked",
        "tests/security/test_vulnerabilities.py::TestIDOR::test_authorization_check_required",
        "tests/security/test_vulnerabilities.py::TestIDOR::test_idor_enumeration_prevented",
        "tests/security/test_vulnerabilities.py::TestIDOR::test_idor_via_path_parameter",
    ],
    "I6": [
        "tests/security/test_vulnerabilities.py::TestPathTraversal::test_path_traversal_blocked",
        "tests/security/test_vulnerabilities.py::TestPathTraversal::test_artifact_path_validated",
        "tests/security/test_vulnerabilities.py::TestPathTraversal::test_null_byte_injection",
        "tests/security/test_vulnerabilities.py::TestPathTraversal::test_absolute_path_rejected",
    ],
    "I7": [
        "tests/security/test_vulnerabilities.py::TestMassAssignment::test_mass_assignment_blocked",
        "tests/security/test_vulnerabilities.py::TestMassAssignment::test_field_allowlist_enforced",
        "tests/security/test_vulnerabilities.py::TestMassAssignment::test_nested_mass_assignment",
        "tests/security/test_vulnerabilities.py::TestMassAssignment::test_update_preserves_readonly",
    ],
    "I8": [
        "tests/security/test_vulnerabilities.py::TestTimingAttack::test_timing_attack_prevented",
        "tests/security/test_vulnerabilities.py::TestTimingAttack::test_constant_time_comparison",
        "tests/security/test_vulnerabilities.py::TestTimingAttack::test_different_length_keys",
        "tests/security/test_vulnerabilities.py::TestTimingAttack::test_empty_key_rejected",
    ],
    "I9": [
        "tests/security/test_vulnerabilities.py::TestDefaultSecurityGroup::test_default_security_group_safe",
        "tests/security/test_vulnerabilities.py::TestDefaultSecurityGroup::test_no_open_ingress",
        "tests/security/test_vulnerabilities.py::TestDefaultSecurityGroup::test_egress_allowed_by_default",
        "tests/security/test_vulnerabilities.py::TestDefaultSecurityGroup::test_security_group_has_tenant",
    ],
    "I10": [
        "tests/security/test_vulnerabilities.py::TestComplianceEvaluation::test_compliance_rule_evaluation",
        "tests/security/test_vulnerabilities.py::TestComplianceEvaluation::test_policy_enforcement_order",
        "tests/security/test_vulnerabilities.py::TestComplianceEvaluation::test_no_matching_rules",
        "tests/security/test_vulnerabilities.py::TestComplianceEvaluation::test_wildcard_rule_matches_all",
        "tests/security/test_vulnerabilities.py::TestComplianceEvaluation::test_empty_rules",
        "tests/security/test_vulnerabilities.py::TestComplianceEvaluation::test_multiple_deny_rules",
    ],

    # J1-J7: Observability
    "J1": [
        "tests/integration/test_service_communication.py::TestTracePropagation::test_trace_propagation_kafka",
        "tests/integration/test_service_communication.py::TestTracePropagation::test_distributed_trace_complete",
        "tests/integration/test_service_communication.py::TestTracePropagation::test_trace_context_format",
        "tests/integration/test_service_communication.py::TestTracePropagation::test_trace_not_lost_on_async",
    ],
    "J2": [
        "tests/integration/test_service_communication.py::TestCorrelationID::test_correlation_id_consistent",
        "tests/integration/test_service_communication.py::TestCorrelationID::test_request_tracking_end_to_end",
        "tests/integration/test_service_communication.py::TestCorrelationID::test_new_correlation_id_when_missing",
        "tests/integration/test_service_communication.py::TestCorrelationID::test_correlation_id_in_response",
    ],
    "J3": [
        "tests/integration/test_service_communication.py::TestMetricCardinality::test_metric_cardinality_bounded",
        "tests/integration/test_service_communication.py::TestMetricCardinality::test_label_limits_enforced",
        "tests/integration/test_service_communication.py::TestMetricCardinality::test_safe_labels_allowed",
        "tests/integration/test_service_communication.py::TestMetricCardinality::test_label_sanitization",
    ],
    "J4": [
        "tests/integration/test_service_communication.py::TestHealthCheckAccuracy::test_health_check_accuracy",
        "tests/integration/test_service_communication.py::TestHealthCheckAccuracy::test_dependency_health_reflected",
        "tests/integration/test_service_communication.py::TestHealthCheckAccuracy::test_partial_dependency_failure",
        "tests/integration/test_service_communication.py::TestHealthCheckAccuracy::test_health_check_timeout",
    ],
    "J5": [
        "tests/integration/test_service_communication.py::TestErrorAggregation::test_error_aggregation_correct",
        "tests/integration/test_service_communication.py::TestErrorAggregation::test_error_grouping_logical",
        "tests/integration/test_service_communication.py::TestErrorAggregation::test_error_count_tracking",
        "tests/integration/test_service_communication.py::TestErrorAggregation::test_different_status_codes_separated",
    ],
    "J6": [
        "tests/integration/test_service_communication.py::TestAlertDedup::test_alert_dedup_window",
        "tests/integration/test_service_communication.py::TestAlertDedup::test_duplicate_alert_suppressed",
        "tests/integration/test_service_communication.py::TestAlertDedup::test_different_alerts_not_suppressed",
        "tests/integration/test_service_communication.py::TestAlertDedup::test_alert_fires_after_window",
    ],
    "J7": [
        "tests/integration/test_service_communication.py::TestTraceSpanCleanup::test_trace_span_cleanup",
        "tests/integration/test_service_communication.py::TestTraceSpanCleanup::test_span_not_leaked",
        "tests/integration/test_service_communication.py::TestTraceSpanCleanup::test_span_lifecycle_complete",
        "tests/integration/test_service_communication.py::TestTraceSpanCleanup::test_multiple_spans_tracked",
        "tests/integration/test_service_communication.py::TestTraceSpanCleanup::test_end_nonexistent_span",
    ],

    # K1-K12: Configuration Management
    "K1": [
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_template_variable_no_cycle",
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_interpolation_terminates",
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_simple_interpolation",
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_nested_interpolation",
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_missing_variable_preserved",
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_no_variables",
        "tests/system/test_end_to_end.py::TestTemplateVariableInterpolation::test_empty_template",
    ],
    "K2": [
        "tests/system/test_end_to_end.py::TestPlanApplyConsistency::test_plan_apply_consistency",
        "tests/system/test_end_to_end.py::TestPlanApplyConsistency::test_no_drift_after_apply",
        "tests/system/test_end_to_end.py::TestPlanApplyConsistency::test_plan_detects_changes",
        "tests/system/test_end_to_end.py::TestPlanApplyConsistency::test_plan_idempotent",
    ],
    "K3": [
        "tests/system/test_end_to_end.py::TestEnvVarPrecedence::test_env_var_precedence_correct",
        "tests/system/test_end_to_end.py::TestEnvVarPrecedence::test_override_order",
        "tests/system/test_end_to_end.py::TestEnvVarPrecedence::test_defaults_used_when_no_override",
        "tests/system/test_end_to_end.py::TestEnvVarPrecedence::test_config_overrides_default",
        "tests/system/test_end_to_end.py::TestEnvVarPrecedence::test_all_levels_combined",
    ],
    "K4": [
        "tests/system/test_end_to_end.py::TestConfigVersionPinning::test_config_version_pinning",
        "tests/system/test_end_to_end.py::TestConfigVersionPinning::test_version_race_prevented",
        "tests/system/test_end_to_end.py::TestConfigVersionPinning::test_version_increments_on_apply",
        "tests/system/test_end_to_end.py::TestConfigVersionPinning::test_version_unchanged_on_failure",
    ],
    "K5": [
        "tests/system/test_end_to_end.py::TestSecretResolution::test_secret_reference_resolution",
        "tests/system/test_end_to_end.py::TestSecretResolution::test_lazy_eager_correct",
        "tests/system/test_end_to_end.py::TestSecretResolution::test_lazy_resolution_stale",
        "tests/system/test_end_to_end.py::TestSecretResolution::test_missing_secret_returns_none_or_default",
    ],
    "K6": [
        "tests/system/test_end_to_end.py::TestDependencyTopologicalSort::test_dependency_topological_sort",
        "tests/system/test_end_to_end.py::TestDependencyTopologicalSort::test_sort_deterministic",
        "tests/system/test_end_to_end.py::TestDependencyTopologicalSort::test_single_node_sort",
        "tests/system/test_end_to_end.py::TestDependencyTopologicalSort::test_linear_chain_sort",
        "tests/system/test_end_to_end.py::TestDependencyTopologicalSort::test_empty_graph",
        "tests/system/test_end_to_end.py::TestDependencyTopologicalSort::test_diamond_dependency",
    ],
    "K7": [
        "tests/system/test_end_to_end.py::TestProviderPluginVersion::test_provider_plugin_version",
        "tests/system/test_end_to_end.py::TestProviderPluginVersion::test_version_conflict_detected",
        "tests/system/test_end_to_end.py::TestProviderPluginVersion::test_compatible_versions",
        "tests/system/test_end_to_end.py::TestProviderPluginVersion::test_missing_provider_detected",
    ],
    "K8": [
        "tests/system/test_end_to_end.py::TestResourceDefaultMerge::test_resource_default_merge",
        "tests/system/test_end_to_end.py::TestResourceDefaultMerge::test_deep_merge_correct",
        "tests/system/test_end_to_end.py::TestResourceDefaultMerge::test_non_dict_override",
        "tests/system/test_end_to_end.py::TestResourceDefaultMerge::test_empty_override",
        "tests/system/test_end_to_end.py::TestResourceDefaultMerge::test_empty_defaults",
    ],
    "K9": [
        "tests/system/test_end_to_end.py::TestOutputReference::test_output_reference_no_cycle",
        "tests/system/test_end_to_end.py::TestOutputReference::test_output_resolution",
        "tests/system/test_end_to_end.py::TestOutputReference::test_chained_output_resolution",
        "tests/system/test_end_to_end.py::TestOutputReference::test_missing_output_reference",
    ],
    "K10": [
        "tests/system/test_end_to_end.py::TestWorkspaceIsolation::test_workspace_variable_isolation",
        "tests/system/test_end_to_end.py::TestWorkspaceIsolation::test_no_variable_leak",
        "tests/system/test_end_to_end.py::TestWorkspaceIsolation::test_workspace_default_variables",
        "tests/system/test_end_to_end.py::TestWorkspaceIsolation::test_workspace_names_unique",
    ],
    "K11": [
        "tests/system/test_end_to_end.py::TestConditionalResourceCount::test_conditional_resource_count",
        "tests/system/test_end_to_end.py::TestConditionalResourceCount::test_count_boundary_correct",
        "tests/system/test_end_to_end.py::TestConditionalResourceCount::test_condition_false_zero_resources",
        "tests/system/test_end_to_end.py::TestConditionalResourceCount::test_condition_true_count_positive",
        "tests/system/test_end_to_end.py::TestConditionalResourceCount::test_large_count",
    ],
    "K12": [
        "tests/system/test_end_to_end.py::TestDynamicBlockExpansion::test_dynamic_block_expansion",
        "tests/system/test_end_to_end.py::TestDynamicBlockExpansion::test_block_ordering_stable",
        "tests/system/test_end_to_end.py::TestDynamicBlockExpansion::test_static_blocks_preserved",
        "tests/system/test_end_to_end.py::TestDynamicBlockExpansion::test_empty_for_each",
        "tests/system/test_end_to_end.py::TestDynamicBlockExpansion::test_expansion_values_correct",
        "tests/system/test_end_to_end.py::TestDynamicBlockExpansion::test_no_blocks",
    ],
}

BUG_DEPENDENCIES = {}
