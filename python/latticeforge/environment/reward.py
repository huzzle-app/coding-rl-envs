"""Reward model for LatticeForge apex-principal environment."""

from __future__ import annotations

THRESHOLDS = [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0]
REWARDS = [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0]

BASE_TESTS = [
    "test_full_mission_cycle",
    "test_hold_gate_for_risky_replay",
    "test_signature_and_mfa",
    "test_hyper_matrix_00000",
    "test_service_mesh_matrix_00000",
    "test_batch_keeps_distinct_command_ids",
    "test_authorize_allows_exact_clearance_match",
    "test_select_primary_prefers_lowest_score",
    "test_degraded_comms_triggers_hold_at_lower_threshold",
    "test_plan_avoids_degraded_failover_region",
    "test_ledger_rejects_duplicate_event_id",
    "test_invalid_transition_raises",
    "test_severity_five_uses_all_channels",
    "test_rank_incidents_descending_severity",
    "test_intake_to_policy_pipeline",
]

TOTAL_TESTS = 16729

def sparse_reward(pass_rate: float) -> float:
    for threshold, reward in reversed(list(zip(THRESHOLDS, REWARDS))):
        if pass_rate >= threshold:
            return reward
    return 0.0

def total_tests() -> int:
    return TOTAL_TESTS

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}

def total_bugs() -> int:
    """Legacy stub - returns 0 as bug tracking is removed."""
    return 0
