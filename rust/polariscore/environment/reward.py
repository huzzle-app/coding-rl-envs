"""Reward model for PolarisCore hyper-principal environment."""

THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]

TOTAL_TESTS = 164

def sparse_reward(pass_rate: float) -> float:
    for threshold, reward in reversed(list(zip(THRESHOLDS, REWARDS))):
        if pass_rate >= threshold:
            return reward
    return 0.0

def total_tests() -> int:
    return TOTAL_TESTS

# Maps each bug ID to the test files (binary names) that detect it.
BUG_TEST_MAPPING = {
    # Statistics (5)
    "statistics.percentile_complement": [
        "queue_statistics_tests", "statistics_targeted_tests", "hyper_matrix_tests",
    ],
    "statistics.rolling_sla_divisor": [
        "queue_statistics_tests", "statistics_targeted_tests", "hyper_matrix_tests",
    ],
    "statistics.trimmed_mean_divisor": [
        "queue_statistics_tests", "statistics_targeted_tests", "hyper_matrix_tests",
    ],
    "statistics.ema_alpha_swap": [
        "statistics_targeted_tests", "hyper_matrix_tests",
    ],
    "statistics.anomalies_population_variance": [
        "statistics_targeted_tests", "hyper_matrix_tests",
    ],
    # Queue (4)
    "queue.order_ascending": [
        "queue_statistics_tests", "hyper_matrix_tests",
    ],
    "queue.pressure_coefficient": [
        "queue_statistics_tests", "hyper_matrix_tests",
    ],
    "queue.round_robin_while_drain": [
        "queue_targeted_tests", "hyper_matrix_tests",
    ],
    "queue.merge_descending": [
        "hyper_matrix_tests",
    ],
    # Economics (3)
    "economics.surge_divisor": [
        "economics_targeted_tests", "hyper_matrix_tests", "workflow_integration_tests",
    ],
    "economics.break_even_plus": [
        "economics_targeted_tests", "hyper_matrix_tests",
    ],
    "economics.margin_clamp_zero": [
        "economics_targeted_tests", "hyper_matrix_tests",
    ],
    # Policy (3)
    "policy.risk_score_load_divisor": [
        "policy_tests", "hyper_matrix_tests",
    ],
    "policy.risk_score_severity_mult": [
        "policy_tests", "hyper_matrix_tests",
    ],
    "policy.compound_risk_correlation": [
        "hyper_matrix_tests",
    ],
    # Allocator (3)
    "allocator.reallocate_window_sort": [
        "hyper_matrix_tests",
    ],
    "allocator.zone_deterministic_order": [
        "hyper_matrix_tests",
    ],
    "allocator.risk_adjusted_zone_sort": [
        "hyper_matrix_tests",
    ],
    # Routing (3)
    "routing.select_hub_penalty_not_filter": [
        "hyper_matrix_tests",
    ],
    "routing.cold_chain_resets_on_safe": [
        "hyper_matrix_tests",
    ],
    "routing.route_segments_unknown_default": [
        "hyper_matrix_tests",
    ],
    # Resilience (4)
    "resilience.retry_backoff_base": [
        "resilience_tests", "hyper_matrix_tests",
    ],
    "resilience.replay_budget_multiplier": [
        "resilience_tests", "chaos_replay_tests", "hyper_matrix_tests",
    ],
    "resilience.breaker_recovery_reset": [
        "hyper_matrix_tests",
    ],
    "resilience.adaptive_factor_formula": [
        "hyper_matrix_tests",
    ],
    # Security (2)
    "security.signature_tolerance": [
        "security_tests", "hyper_matrix_tests",
    ],
    "security.step_up_threshold": [
        "security_tests", "hyper_matrix_tests",
    ],
    # Workflow (5)
    "workflow.can_deliver_includes_allocated": [
        "workflow_targeted_tests", "hyper_matrix_tests",
    ],
    "workflow.held_to_delivered": [
        "workflow_targeted_tests", "hyper_matrix_tests",
    ],
    "workflow.plan_fulfillment_max_vs_avg": [
        "workflow_targeted_tests", "hyper_matrix_tests",
    ],
    "workflow.plan_margin_cost_divisor": [
        "workflow_targeted_tests", "hyper_matrix_tests",
    ],
    "workflow.multi_batch_shared_capacity": [
        "workflow_targeted_tests", "hyper_matrix_tests",
    ],
}

# Prerequisite chains: a bug must be fixed before its dependents' tests can pass.
BUG_DEPENDENCIES = {
    # Statistics — all independent
    "statistics.percentile_complement": [],
    "statistics.rolling_sla_divisor": [],
    "statistics.trimmed_mean_divisor": [],
    "statistics.ema_alpha_swap": [],
    "statistics.anomalies_population_variance": [],
    # Queue — all independent
    "queue.order_ascending": [],
    "queue.pressure_coefficient": [],
    "queue.round_robin_while_drain": [],
    "queue.merge_descending": [],
    # Economics — all independent
    "economics.surge_divisor": [],
    "economics.break_even_plus": [],
    "economics.margin_clamp_zero": [],
    # Policy — compound_risk depends on base risk_score being correct
    "policy.risk_score_load_divisor": [],
    "policy.risk_score_severity_mult": [],
    "policy.compound_risk_correlation": [
        "policy.risk_score_load_divisor",
        "policy.risk_score_severity_mult",
    ],
    # Allocator — risk_adjusted depends on compound_risk
    "allocator.reallocate_window_sort": [],
    "allocator.zone_deterministic_order": [],
    "allocator.risk_adjusted_zone_sort": ["policy.compound_risk_correlation"],
    # Routing — all independent
    "routing.select_hub_penalty_not_filter": [],
    "routing.cold_chain_resets_on_safe": [],
    "routing.route_segments_unknown_default": [],
    # Resilience — adaptive depends on base backoff
    "resilience.retry_backoff_base": [],
    "resilience.replay_budget_multiplier": [],
    "resilience.breaker_recovery_reset": [],
    "resilience.adaptive_factor_formula": ["resilience.retry_backoff_base"],
    # Security — all independent
    "security.signature_tolerance": [],
    "security.step_up_threshold": [],
    # Workflow — plan_margin depends on economics.surge being correct
    "workflow.can_deliver_includes_allocated": [],
    "workflow.held_to_delivered": [],
    "workflow.plan_fulfillment_max_vs_avg": [],
    "workflow.plan_margin_cost_divisor": ["economics.surge_divisor"],
    "workflow.multi_batch_shared_capacity": [],
}
