"""Reward model for VectorHarbor hyper-principal environment."""

THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]

TOTAL_TESTS = 9283

def sparse_reward(pass_rate: float) -> float:
    for threshold, reward in reversed(list(zip(THRESHOLDS, REWARDS))):
        if pass_rate >= threshold:
            return reward
    return 0.0

def total_tests() -> int:
    return TOTAL_TESTS

# Bug-to-test mapping: each bug ID maps to the test functions it affects.
# Tests in the dependency chain will only pass when ALL prerequisite bugs are fixed.
BUG_TEST_MAPPING = {
    # === allocator.rs bugs ===
    "allocator_sort_direction": [
        "allocator_enforces_capacity",       # core_tests
        "allocator_batch",                   # extended_tests
        "hyper_matrix_allocator",            # hyper_matrix (1150 allocator scenarios)
    ],
    "allocator_turnaround_rounding": [
        "turnaround_rounds_up_partial_batches",        # advanced_tests
        "turnaround_partial_batch_includes_full_cycle", # advanced_tests
    ],
    "allocator_berth_boundary": [
        "berth_adjacent_slots_conflict_at_boundary",   # advanced_tests
        "berth_back_to_back_slots_same_hour",          # advanced_tests
    ],
    "allocator_cost_formula": [
        "allocator_cost_estimation",         # extended_tests
    ],
    "allocator_rolling_window_boundary": [
        "rolling_window_flush_boundary_retained",      # advanced_tests
        "rolling_window_boundary_determines_active_set", # advanced_tests
    ],

    # === contracts.rs bugs ===
    "contracts_missing_port": [
        "contracts_url",                     # extended_tests
    ],
    "contracts_topo_sort_direction": [
        "topological_order_siblings_alphabetical",     # advanced_tests
    ],

    # === policy.rs bugs ===
    "policy_escalation_wrapping": [
        "policy_escalation_caps_at_halted",            # advanced_tests
        "policy_engine_saturates_at_max_escalation",   # advanced_tests
        "policy_escalation_ceiling_with_deescalation", # advanced_tests
    ],

    # === queue.rs bugs ===
    "queue_shed_boundary": [
        "queue_shed_on_hard_limit",          # core_tests
    ],
    "queue_wait_time_formula": [
        "queue_wait_estimation",             # extended_tests
        "hyper_matrix_queue",                # hyper_matrix (1150 queue scenarios)
    ],
    "queue_rate_limiter_ordering": [
        "rate_limiter_refill_before_acquire",          # advanced_tests
        "rate_limiter_incremental_refill_timing",      # advanced_tests
    ],
    "queue_priority_admission": [
        "priority_queue_rejects_at_capacity",          # advanced_tests
        "priority_queue_high_priority_cannot_displace_at_capacity", # advanced_tests
    ],

    # === resilience.rs bugs ===
    "resilience_circuit_breaker_half_open": [
        "circuit_breaker_half_open_single_failure_trips",    # advanced_tests
        "circuit_breaker_half_open_recovery_then_failure",   # advanced_tests
    ],

    # === routing.rs bugs ===
    "routing_cost_operator": [
        "routing_cost",                      # extended_tests
    ],

    # === security.rs bugs ===
    "security_path_sanitization": [
        "security_path_sanitise",            # extended_tests
        "hyper_matrix_security",             # hyper_matrix (1150 security scenarios)
    ],
    "security_token_expiry_boundary": [
        "token_expires_at_exact_boundary",             # advanced_tests
        "token_validate_cleanup_boundary_consistency",  # advanced_tests
    ],

    # === statistics.rs bugs ===
    "statistics_percentile_formula": [
        "statistics_percentile_monotonic",   # core_tests
    ],
    "statistics_variance_bessel": [
        "sample_variance_bessel_correction", # advanced_tests
        "stddev_uses_sample_variance",       # advanced_tests
    ],

    # === workflow.rs bugs ===
    "workflow_missing_transition": [
        "workflow_departed_can_arrive",                # advanced_tests
        "active_count_decreases_on_arrival",           # advanced_tests (masked)
        "audit_log_shows_correct_transition_direction", # advanced_tests (masked)
        "multi_entity_lifecycle_with_audit_trail",     # advanced_tests (masked)
        "cross_module_dispatch_lifecycle",              # advanced_tests (masked)
        "workflow_engine",                             # extended_tests
        "workflow_shortest_path",                      # extended_tests
        "hyper_matrix_workflow",                       # hyper_matrix (1150 workflow scenarios)
    ],
    "workflow_active_count_inversion": [
        "active_count_decreases_on_arrival",           # advanced_tests
        "multi_entity_lifecycle_with_audit_trail",     # advanced_tests
        "cross_module_dispatch_lifecycle",              # advanced_tests
        "workflow_engine",                             # extended_tests
    ],
    "workflow_audit_log_order": [
        "audit_log_shows_correct_transition_direction", # advanced_tests
        "multi_entity_lifecycle_with_audit_trail",     # advanced_tests
        "cross_module_dispatch_lifecycle",              # advanced_tests
    ],

    # === models.rs bugs ===
    "models_urgency_formula": [
        "model_urgency_score",               # core_tests
    ],
    "models_batch_clamp_range": [
        "batch_create_preserves_extreme_severities",   # advanced_tests
        "model_batch_creation",              # extended_tests
    ],
}

# Bug dependency chains: some bugs are masked by prerequisite bugs.
# A masked bug's tests will only start failing (and become fixable) after
# the prerequisite bugs are resolved.
BUG_DEPENDENCIES = {
    # workflow chain: can_transition -> active_count -> audit_log
    "workflow_active_count_inversion": ["workflow_missing_transition"],
    "workflow_audit_log_order": ["workflow_missing_transition"],
}
