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
        0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0
    ])
    threshold_rewards: List[float] = field(default_factory=lambda: [
        0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0
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

# Bug-to-test mapping: maps bug IDs to the test functions that detect them
# Tests are from both unit tests (per-service) and integration tests
BUG_TEST_MAPPING = {
    # L: Setup/Configuration (8 bugs) - stray / chars prevent compilation
    "L1": ["test_nats_reconnection", "test_nats_connection_recovery", "test_l1_nats_connection_recovery"],
    "L2": ["test_tokio_runtime_cpu_bound", "test_blocking_in_async_detected"],
    "L3": ["test_db_pool_under_load", "test_connection_pool_exhaustion"],
    "L4": ["test_graceful_shutdown_waits_for_requests", "test_shutdown_signal_handling"],
    "L5": ["test_service_discovery_consistency", "test_discovery_race_condition"],
    "L6": ["test_config_hot_reload_safe", "test_config_reload_no_crash"],
    "L7": ["test_l7_timestamp_timezone_utc", "test_l7_market_hours_timezone"],
    "L8": ["test_tls_disabled", "test_l8_tls_certificate_validation", "test_l8_tls_not_disabled"],
    # A: Ownership/Borrowing (10 bugs)
    "A1": ["test_a1_use_after_move_in_order"],
    "A2": ["test_closure_borrow_safety", "test_order_add_no_dangling_ref"],
    "A3": ["test_a3_mutable_borrow_in_iterator"],
    "A4": ["test_a4_partial_move_option"],
    "A5": ["test_a5_reference_outlives_data"],
    "A6": ["test_a6_double_mutable_borrow"],
    "A7": ["test_a7_moved_value_async"],
    "A8": ["test_a8_interior_mutability"],
    "A9": ["test_no_self_referential"],
    "A10": ["test_a10_lifetime_variance"],
    # B: Concurrency (12 bugs)
    "B1": ["test_no_lock_ordering_deadlock", "test_b1_lock_ordering_consistent", "test_b1_lock_ordering_in_source"],
    "B2": ["test_b2_spawn_blocking_used", "test_b2_no_blocking_in_async"],
    "B3": ["test_best_prices_consistent", "test_b3_read_modify_write_atomic", "test_b3_race_in_order_book"],
    "B4": ["test_b4_data_is_send", "test_b4_data_is_sync"],
    "B5": ["test_b5_mutex_poison_handled", "test_b5_parking_lot_no_poison"],
    "B6": ["test_b6_channel_backpressure", "test_b6_bounded_channel"],
    "B7": ["test_b7_atomic_ordering_correct", "test_b7_seqcst_for_ordering"],
    "B8": ["test_b8_no_spin_loop_in_async", "test_b8_use_condvar"],
    "B9": ["test_b9_condvar_spurious_wakeup", "test_b9_wait_while"],
    "B10": ["test_b10_thread_pool_bounded"],
    "B11": ["test_lockfree_aba_prevention", "test_b11_aba_with_tagged_pointer"],
    "B12": ["test_memory_ordering_prices", "test_b12_memory_ordering_prices", "test_b12_memory_ordering_in_source"],
    # C: Error Handling (8 bugs)
    "C1": ["test_c1_no_unwrap_in_order_processing"],
    "C2": ["test_c2_error_preserves_context"],
    "C3": ["test_c3_async_panic_caught"],
    "C4": ["test_c4_result_in_drop_handled"],
    "C5": ["test_c5_error_chain_complete"],
    "C6": ["test_c6_error_has_context"],
    "C7": ["test_c7_expired_token_same_error", "test_error_hiding"],
    "C8": ["test_c8_panic_hook_set"],
    # D: Memory/Resources (8 bugs)
    "D1": ["test_d1_bounded_order_history"],
    "D2": ["test_d2_event_log_growth", "test_d2_arc_cycle_detection"],
    "D3": ["test_d3_file_handle_released"],
    "D4": ["test_d4_connection_pool_released"],
    "D5": ["test_d5_cache_eviction"],
    "D6": ["test_d6_no_string_alloc_hot_path"],
    "D7": ["test_d7_no_large_stack_alloc"],
    "D8": ["test_d8_websocket_buffer_released"],
    # E: Unsafe Code (6 bugs)
    "E1": ["test_price_conversion_safe", "test_no_ub_transmute"],
    "E2": ["test_e2_no_uninitialized_memory"],
    "E3": ["test_e3_pointer_arithmetic_safe"],
    "E4": ["test_atomic_ordering_no_data_race", "test_lockfree_ordering_correct"],
    "E5": ["test_e5_send_sync_correct", "test_b4_data_is_send", "test_b4_data_is_sync"],
    "E6": ["test_e6_no_use_after_free"],
    # F: Numerical/Financial (10 bugs)
    "F1": ["test_f1_price_decimal_precision", "test_f1_no_float_for_money"],
    "F2": ["test_f2_checked_arithmetic", "test_quantity_overflow_handled"],
    "F3": ["test_f3_banker_rounding"],
    "F4": ["test_no_float_conversion_rate", "test_f4_currency_conversion_atomic"],
    "F5": ["test_f5_fee_precision_maintained", "test_fee_no_truncation"],
    "F6": ["test_f6_unrealized_pnl_short_position", "test_f6_pnl_correct"],
    "F7": ["test_f7_margin_no_overflow"],
    "F8": ["test_f8_price_tick_validation", "test_price_tick_validation"],
    "F9": ["test_f9_order_value_decimal"],
    "F10": ["test_f10_tax_rounding"],
    # G: Distributed Systems (8 bugs)
    "G1": ["test_g1_event_ordering_preserved"],
    "G2": ["test_g2_distributed_lock_released"],
    "G3": ["test_g3_split_brain_detected", "test_g3_split_brain_prevented"],
    "G4": ["test_g4_order_idempotent"],
    "G5": ["test_g5_saga_compensation"],
    "G6": ["test_g6_circuit_breaker_per_service"],
    "G7": ["test_g7_retry_with_backoff"],
    "G8": ["test_g8_leader_election_stable"],
    # H: Security (5 bugs)
    "H1": ["test_h1_jwt_secret_not_hardcoded_in_source", "test_h1_jwt_uses_env_or_config_for_secret"],
    "H2": ["test_h2_uses_constant_time_comparison", "test_h2_timing_attack_practical"],
    "H3": ["test_h3_no_string_format_in_queries", "test_h3_uses_parameterized_queries"],
    "H4": ["test_h4_rate_limit_not_using_forwarded_header", "test_h4_rate_limit_uses_peer_addr"],
    "H5": ["test_h5_logger_masks_sensitive_fields", "test_h5_no_password_in_log_format"],
}

# Bug dependency chains: bug -> list of bugs that must be fixed first
BUG_DEPENDENCIES = {
    # Setup bugs block everything in their service
    "A2": ["L2"],   # matching engine must compile
    "A9": ["L2"],
    "B1": ["L2"],
    "B3": ["L2"],
    "E1": ["L2"],
    "E4": ["L2"],
    "D6": ["L2"],
    "F2": ["L2"],
    "F8": ["L2"],
    # Shared library setup bugs block all services
    "A10": ["L1", "L5"],
    "G1": ["L1"],
    "G7": ["L1"],
    "H5": ["L1"],
    "E5": ["L5"],
    # Financial bugs have chain dependencies
    "F5": ["F1"],    # fee precision needs price precision
    "F6": ["F1"],    # P&L needs price precision
    "F9": ["F1"],    # order value needs price precision
    "F10": ["F3"],   # tax rounding needs decimal rounding
    # Concurrency needs setup
    "B6": ["L1"],    # channel needs NATS connection
    "B12": ["L7"],   # market data ordering needs timestamps
    # Error handling chains
    "C5": ["C2"],    # error chain needs error context
    "C7": ["C3"],    # catch-all needs async panic handling
    # Distributed needs setup
    "G2": ["L5"],    # distributed lock needs discovery
    "G3": ["L5"],    # split brain needs discovery
    "G8": ["L5"],    # leader election needs discovery
    "G5": ["G1"],    # saga needs event ordering
    "G6": ["G7"],    # circuit breaker needs retry
}
