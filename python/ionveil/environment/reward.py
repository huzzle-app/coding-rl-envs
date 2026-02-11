"""
IonVeil Reward Function
Terminal Bench v2 - Apex-Principal Environment

Planetary Emergency Command Center - apex-scale reward system.
10-tier sparse reward with regression penalties and service bonuses.
"""
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

# ============================================================================
# Service Isolation - bonus for fully passing services
# ============================================================================

SERVICE_TEST_GROUPS = {
    "gateway": ["test_gateway_*"],
    "auth": ["test_auth_*", "test_jwt_*", "test_oauth_*", "test_token_*"],
    "dispatch": ["test_dispatch_*", "test_priority_*"],
    "routing": ["test_route_*", "test_distance_*", "test_haversine_*"],
    "incidents": ["test_incident_*", "test_merge_*", "test_escalation_*"],
    "resources": ["test_resource_*", "test_shift_*", "test_capacity_*"],
    "notifications": ["test_notification_*", "test_channel_*"],
    "analytics": ["test_metric_*", "test_response_time_*"],
    "compliance": ["test_audit_*", "test_sla_*", "test_compliance_*"],
    "audit_events": ["test_event_store_*", "test_replay_*"],
}

# ============================================================================
# Base tests - the named tests that exercise expanded source modules
# ============================================================================

BASE_TESTS = [
    # Unit tests (9)
    "tests.unit.models_test.ModelTests.test_dispatch_order_urgency",
    "tests.unit.dispatch_test.DispatchTests.test_plan_dispatch_limits_capacity",
    "tests.unit.policy_test.PolicyTests.test_next_policy_escalates",
    "tests.unit.queue_test.QueueTests.test_should_shed_uses_hard_limit",
    "tests.unit.routing_test.RoutingTests.test_choose_route_filters_blocked",
    "tests.unit.statistics_test.StatisticsTests.test_percentile_returns_monotonic_rank",
    "tests.unit.resilience_test.ResilienceTests.test_replay_prefers_latest_sequence",
    "tests.unit.workflow_test.WorkflowTests.test_transition_graph_enforced",
    "tests.unit.security_test.SecurityTests.test_verify_signature_requires_exact_digest",
    # Integration tests (2)
    "tests.integration.mission_flow_test.MissionFlowTests.test_dispatch_routing_workflow_flow",
    "tests.integration.security_pipeline_test.SecurityPipelineTests.test_policy_queue_alignment",
    # Services test (1)
    "tests.services.contracts_test.ContractTests.test_contracts_expose_required_keys",
    # Chaos test (1)
    "tests.chaos.replay_chaos_test.ReplayChaosTests.test_ordered_vs_shuffled_replay_converges",
    # Extended tests (49)
    "tests.unit.extended_test.ExtModelsTest.test_severity_constants",
    "tests.unit.extended_test.ExtModelsTest.test_sla_by_severity",
    "tests.unit.extended_test.ExtModelsTest.test_classify_severity",
    "tests.unit.extended_test.ExtModelsTest.test_create_batch_orders",
    "tests.unit.extended_test.ExtModelsTest.test_validate_dispatch_order",
    "tests.unit.extended_test.ExtModelsTest.test_vessel_manifest",
    "tests.unit.extended_test.ExtDispatchTest.test_dispatch_batch",
    "tests.unit.extended_test.ExtDispatchTest.test_has_conflict",
    "tests.unit.extended_test.ExtDispatchTest.test_find_available_slots",
    "tests.unit.extended_test.ExtDispatchTest.test_estimate_cost",
    "tests.unit.extended_test.ExtDispatchTest.test_estimate_turnaround",
    "tests.unit.extended_test.ExtDispatchTest.test_check_capacity",
    "tests.unit.extended_test.ExtDispatchTest.test_validate_batch",
    "tests.unit.extended_test.ExtDispatchTest.test_rolling_window_scheduler",
    "tests.unit.extended_test.ExtRoutingTest.test_channel_score",
    "tests.unit.extended_test.ExtRoutingTest.test_estimate_transit_time",
    "tests.unit.extended_test.ExtRoutingTest.test_plan_multi_leg",
    "tests.unit.extended_test.ExtRoutingTest.test_route_table",
    "tests.unit.extended_test.ExtPolicyTest.test_previous_policy",
    "tests.unit.extended_test.ExtPolicyTest.test_should_deescalate",
    "tests.unit.extended_test.ExtPolicyTest.test_policy_engine",
    "tests.unit.extended_test.ExtPolicyTest.test_sla_percentage",
    "tests.unit.extended_test.ExtPolicyTest.test_check_sla_compliance",
    "tests.unit.extended_test.ExtQueueTest.test_queue_health",
    "tests.unit.extended_test.ExtQueueTest.test_priority_queue",
    "tests.unit.extended_test.ExtQueueTest.test_estimate_wait_time",
    "tests.unit.extended_test.ExtSecurityTest.test_sign_verify_manifest",
    "tests.unit.extended_test.ExtSecurityTest.test_sanitise_path",
    "tests.unit.extended_test.ExtSecurityTest.test_is_allowed_origin",
    "tests.unit.extended_test.ExtSecurityTest.test_token_store",
    "tests.unit.extended_test.ExtResilienceTest.test_deduplicate",
    "tests.unit.extended_test.ExtResilienceTest.test_replay_converges",
    "tests.unit.extended_test.ExtResilienceTest.test_checkpoint_manager",
    "tests.unit.extended_test.ExtResilienceTest.test_circuit_breaker",
    "tests.unit.extended_test.ExtStatisticsTest.test_mean",
    "tests.unit.extended_test.ExtStatisticsTest.test_variance_and_stddev",
    "tests.unit.extended_test.ExtStatisticsTest.test_median",
    "tests.unit.extended_test.ExtStatisticsTest.test_moving_average",
    "tests.unit.extended_test.ExtStatisticsTest.test_response_time_tracker",
    "tests.unit.extended_test.ExtStatisticsTest.test_generate_heatmap",
    "tests.unit.extended_test.ExtWorkflowTest.test_terminal_states",
    "tests.unit.extended_test.ExtWorkflowTest.test_is_valid_state",
    "tests.unit.extended_test.ExtWorkflowTest.test_allowed_transitions",
    "tests.unit.extended_test.ExtWorkflowTest.test_shortest_path",
    "tests.unit.extended_test.ExtWorkflowTest.test_workflow_engine",
    "tests.unit.extended_test.ExtContractsTest.test_get_service_url",
    "tests.unit.extended_test.ExtContractsTest.test_validate_contract",
    "tests.unit.extended_test.ExtContractsTest.test_topological_order",
    "tests.unit.extended_test.ExtContractsTest.test_service_defs",
    # Advanced tests - latent bugs (65)
    "tests.unit.advanced_test.LatentMergeManifestTest.test_merge_deduplicates_shared_orders",
    "tests.unit.advanced_test.LatentMergeManifestTest.test_merge_preserves_all_unique_orders",
    "tests.unit.advanced_test.LatentMergeManifestTest.test_merge_takes_higher_priority",
    "tests.unit.advanced_test.LatentTriagePriorityTest.test_moderate_in_dense_area_upgrades_once",
    "tests.unit.advanced_test.LatentTriagePriorityTest.test_critical_stays_critical_in_dense_area",
    "tests.unit.advanced_test.LatentTriagePriorityTest.test_low_density_no_upgrade",
    "tests.unit.advanced_test.LatentAggregateSLATest.test_duplicate_severity_weights_correctly",
    "tests.unit.advanced_test.LatentAggregateSLATest.test_mixed_severity_weighted_average",
    "tests.unit.advanced_test.LatentAggregateSLATest.test_empty_orders",
    # Advanced tests - domain logic
    "tests.unit.advanced_test.DomainFleetCostTest.test_volume_discount_for_large_fleet",
    "tests.unit.advanced_test.DomainFleetCostTest.test_no_discount_for_small_fleet",
    "tests.unit.advanced_test.DomainMutualAidTest.test_critical_needs_three_units",
    "tests.unit.advanced_test.DomainMutualAidTest.test_critical_with_three_units_no_aid",
    "tests.unit.advanced_test.DomainMutualAidTest.test_high_severity_one_unit",
    "tests.unit.advanced_test.DomainMutualAidTest.test_moderate_no_mutual_aid",
    "tests.unit.advanced_test.DomainIncidentCommandTest.test_mass_casualty_always_level_3",
    "tests.unit.advanced_test.DomainIncidentCommandTest.test_critical_severity_level_3",
    "tests.unit.advanced_test.DomainIncidentCommandTest.test_high_severity_level_2",
    "tests.unit.advanced_test.DomainIncidentCommandTest.test_low_severity_few_affected",
    "tests.unit.advanced_test.DomainHaversineTest.test_known_distance_nyc_london",
    "tests.unit.advanced_test.DomainHaversineTest.test_same_point_zero_distance",
    "tests.unit.advanced_test.DomainHaversineTest.test_different_hemispheres_accuracy",
    "tests.unit.advanced_test.DomainHaversineTest.test_equator_90_degrees",
    # Advanced tests - multi-step bugs
    "tests.unit.advanced_test.MultiStepRebalanceTest.test_rebalance_selects_highest_urgency",
    "tests.unit.advanced_test.MultiStepEscalationChainTest.test_deescalation_path_correct_order",
    "tests.unit.advanced_test.MultiStepEscalationChainTest.test_escalation_path",
    "tests.unit.advanced_test.MultiStepEscalationChainTest.test_same_level",
    "tests.unit.advanced_test.MultiStepAdjacencyMatrixTest.test_matrix_symmetric",
    "tests.unit.advanced_test.MultiStepAdjacencyMatrixTest.test_matrix_diagonal_zero",
    "tests.unit.advanced_test.MultiStepDispatchCostTest.test_dispatch_routing_cost_formula",
    # Advanced tests - state machine bugs
    "tests.unit.advanced_test.StateMachineRollbackTest.test_rollback_to_previous_state",
    "tests.unit.advanced_test.StateMachineRollbackTest.test_rollback_from_terminal_fails",
    "tests.unit.advanced_test.StateMachineRollbackTest.test_rollback_no_history",
    "tests.unit.advanced_test.StateMachineCloneTest.test_clone_nonexistent_source_fails",
    "tests.unit.advanced_test.StateMachineCloneTest.test_clone_nonexistent_no_none_state",
    "tests.unit.advanced_test.StateMachineCloneTest.test_clone_copies_state",
    "tests.unit.advanced_test.StateMachineValidatePathTest.test_reports_all_unknown_states",
    "tests.unit.advanced_test.StateMachineValidatePathTest.test_valid_path_no_errors",
    # Advanced tests - concurrency bugs
    "tests.unit.advanced_test.ConcurrencyTransferTest.test_transfer_respects_target_capacity",
    "tests.unit.advanced_test.ConcurrencyTransferTest.test_transfer_preserves_source_items",
    "tests.unit.advanced_test.ConcurrencyMergeTest.test_merge_maintains_sort_order",
    "tests.unit.advanced_test.ConcurrencyMergeTest.test_merge_preserves_all_items",
    "tests.unit.advanced_test.ConcurrencyCircuitBreakerExecuteTest.test_success_resets_failure_count",
    "tests.unit.advanced_test.ConcurrencyCircuitBreakerExecuteTest.test_exception_records_failure",
    "tests.unit.advanced_test.ConcurrencyCircuitBreakerExecuteTest.test_successful_execution_returns_result",
    # Advanced tests - integration bugs
    "tests.unit.advanced_test.IntegrationDispatchRoutingTest.test_rejected_orders_counted",
    "tests.unit.advanced_test.IntegrationDispatchRoutingTest.test_no_routes_all_rejected",
    "tests.unit.advanced_test.IntegrationEventStreamDiffTest.test_diff_finds_items_in_a_not_in_b",
    "tests.unit.advanced_test.IntegrationEventStreamDiffTest.test_diff_considers_sequence_not_just_id",
    "tests.unit.advanced_test.IntegrationEventStreamDiffTest.test_identical_streams_empty_diff",
    "tests.unit.advanced_test.IntegrationMergeCheckpointsTest.test_merge_keeps_higher_sequence_when_a_is_newer",
    "tests.unit.advanced_test.IntegrationMergeCheckpointsTest.test_merge_combines_unique_checkpoints",
    "tests.unit.advanced_test.IntegrationPolicyAutoEscalateTest.test_auto_escalate_at_threshold",
    "tests.unit.advanced_test.IntegrationPolicyAutoEscalateTest.test_auto_escalate_no_change_at_max",
    "tests.unit.advanced_test.IntegrationPolicyAutoEscalateTest.test_auto_escalate_below_threshold",
    "tests.unit.advanced_test.IntegrationProcessEventsTest.test_process_failure_burst_escalates",
    # Advanced tests - statistics, misc
    "tests.unit.advanced_test.StatisticsEMATest.test_ema_responds_to_step_change",
    "tests.unit.advanced_test.StatisticsEMATest.test_ema_weights_new_values_more",
    "tests.unit.advanced_test.StatisticsEMATest.test_ema_alpha_near_one_tracks_closely",
    "tests.unit.advanced_test.StatisticsBreachRateTest.test_partial_breach_rate",
    "tests.unit.advanced_test.StatisticsBreachRateTest.test_all_below_threshold",
    "tests.unit.advanced_test.CheapestRouteTest.test_unknown_cost_treated_conservatively",
    "tests.unit.advanced_test.DrainByPriorityTest.test_drains_at_exact_threshold",
    "tests.unit.advanced_test.TokenStoreTransferTest.test_transfer_preserves_remaining_ttl",
    "tests.unit.advanced_test.TokenStoreTransferTest.test_transfer_expired_token_fails",
]

# ============================================================================
# Constants
# ============================================================================

TOTAL_TESTS = len(BASE_TESTS) + 12400 + 600  # 127 base + 12400 stress + 600 advanced stress = 13127

# 10-tier apex-principal thresholds
THRESHOLDS = [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0]
REWARDS = [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0]

# ============================================================================
# Reward Functions
# ============================================================================

def sparse_reward(pass_rate: float) -> float:
    """Calculate sparse reward from pass rate using threshold table."""
    reward = 0.0
    for threshold, reward_value in zip(THRESHOLDS, REWARDS):
        if pass_rate >= threshold:
            reward = reward_value
        else:
            break
    return reward

def total_tests() -> int:
    return TOTAL_TESTS

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}

def total_bugs() -> int:
    """Legacy stub - returns 0 as bug tracking is removed."""
    return 0
