"""
SynapseNet Reward Function
Terminal Bench v2 - Extremely Sparse Reward System

This reward function is designed to be harder than NexusTrade:
- Very sparse rewards with 8 thresholds
- Regression penalties
- Service isolation bonuses
- ML pipeline test bonuses
- 120 bugs across 15 microservices
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
    'models': ['test_models_*'],
    'registry': ['test_registry_*'],
    'training': ['test_training_*'],
    'inference': ['test_inference_*'],
    'features': ['test_features_*'],
    'pipeline': ['test_pipeline_*'],
    'experiments': ['test_experiments_*'],
    'monitoring': ['test_monitoring_*'],
    'scheduler': ['test_scheduler_*'],
    'workers': ['test_workers_*'],
    'storage': ['test_storage_*'],
    'webhooks': ['test_webhooks_*'],
    'admin': ['test_admin_*'],
}

@dataclass
class RewardCalculator:
    """
    Extremely sparse reward calculator for SynapseNet.

    Features:
    - 8 threshold levels (same as NexusTrade)
    - Regression penalty: -0.15 per previously passing test that fails
    - Service isolation bonus: +0.02 per fully passing service (15 services = +0.30 max)
    - ML pipeline test bonus: +0.10 for passing ML-specific tests
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
    ml_pipeline_bonus: float = 0.10
    efficiency_bonus_weight: float = 0.03

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

        # Component 1: Sparse threshold reward (65%)
        base_reward = self._calculate_sparse_reward(pass_rate) * 0.65

        # Component 2: Regression penalty
        regression = self._calculate_regression_penalty(test_results, previous_results)

        # Component 3: Service isolation bonus (15%)
        service_bonus = self._calculate_service_bonus(test_results) * 0.15

        # Component 4: ML pipeline bonus (15%)
        ml_bonus = self._calculate_ml_bonus(test_results) * 0.15

        # Component 5: Efficiency bonus (5%) - only if all tests pass
        efficiency = 0.0
        if pass_rate >= 1.0:
            efficiency = max(0, 1 - step_count / max_steps) * self.efficiency_bonus_weight

        total = base_reward + regression + service_bonus + ml_bonus + efficiency

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

    def _calculate_ml_bonus(self, test_results: Dict[str, Any]) -> float:
        """Calculate bonus for passing ML pipeline tests."""
        test_detail = test_results.get('test_detail', {})
        if not test_detail:
            return 0.0

        # ML-related test prefixes
        ml_prefixes = ['test_model_', 'test_gradient_', 'test_batch_norm_',
                       'test_feature_drift_', 'test_training_', 'test_lr_scheduler_',
                       'test_checkpoint_', 'test_mixed_precision_', 'test_data_augmentation_',
                       'test_tokenizer_', 'test_parameter_server_', 'test_allreduce_',
                       'test_data_parallelism_', 'test_tensor_split_', 'test_elastic_',
                       'test_ring_', 'test_async_sgd_', 'test_fault_tolerant_']
        ml_tests_total = 0
        ml_tests_passed = 0
        for test_name, passed in test_detail.items():
            for prefix in ml_prefixes:
                if test_name.startswith(prefix):
                    ml_tests_total += 1
                    if passed:
                        ml_tests_passed += 1
                    break

        if ml_tests_total == 0:
            return 0.0
        ml_pass_rate = ml_tests_passed / ml_tests_total
        if ml_pass_rate >= 0.90:
            return self.ml_pipeline_bonus
        elif ml_pass_rate >= 0.50:
            return self.ml_pipeline_bonus * 0.5
        return 0.0

    def get_bug_status(self, test_results: Dict[str, Any]) -> Dict[str, bool]:
        """
        Determine which bugs are fixed based on test results.

        Returns:
            Empty dictionary as bug tracking has been removed.
        """
        return {}

# Bug-to-test mapping: maps each bug ID to the test function names that detect it.
# Used by setup.py's _estimate_bugs_fixed() to count how many bugs an agent has fixed.
# Test names are bare function names (no class prefix, no parameterization suffix).
BUG_TEST_MAPPING = {
    # === L: Setup Hell (L1-L15) ===
    "L1": ["test_import_success", "test_circular_import_resolved", "test_import_chain_l1_to_l3"],
    "L2": ["test_model_loader_import", "test_optional_dependency_guard"],
    "L3": ["test_import_chain_l1_to_l3"],
    "L4": ["test_kafka_topic_exists", "test_topic_creation"],
    "L5": ["test_consul_health_check"],
    "L6": ["test_redis_connection_pool"],
    "L7": ["test_db_migration_ordering"],
    "L8": ["test_env_variable_loading"],
    "L9": ["test_minio_bucket", "test_artifact_upload_basic", "test_minio_bucket_creation"],
    "L10": ["test_celery_task_discovery"],
    "L11": ["test_cors_config", "test_cross_service_call"],
    "L12": ["test_logging_config", "test_log_handler_init", "test_logging_handler_import"],
    "L13": ["test_schema_validation_init", "test_circular_schema_ref"],
    "L14": ["test_middleware_ordering"],
    "L15": ["test_worker_registration", "test_scheduler_worker_link", "test_worker_registration_before_scheduler"],

    # === M: ML Pipeline (M1-M10) ===
    "M1": ["test_model_version_rollback", "test_version_mismatch_detection",
            "test_model_version_rollback_preserves_weights", "test_rollback_returns_previous_version",
            "test_checkpoint_save_load_roundtrip", "test_rollback_loads_previous_version", "test_double_rollback"],
    "M2": ["test_gradient_accumulation_overflow", "test_gradient_clipping",
            "test_large_gradient_accumulation", "test_nan_propagation_in_accumulator",
            "test_gradient_accumulator_returns_independent_copy"],
    "M3": ["test_batch_norm_train_eval_mode", "test_batch_norm_statistics_isolation",
            "test_eval_mode_freezes_stats", "test_eval_mode_freezes_running_stats"],
    "M4": ["test_feature_drift_detection_accuracy", "test_drift_false_positive_rate"],
    "M5": ["test_training_data_shuffle", "test_epoch_data_order_varies", "test_data_order_changes_between_epochs"],
    "M6": ["test_lr_scheduler_step_count", "test_lr_scheduler_boundary", "test_lr_at_warmup_boundary",
            "test_initial_lr_is_base_lr", "test_mid_period_lr", "test_end_of_period_lr",
            "test_warm_restart_at_exact_period_boundary", "test_warm_restart_resets_lr",
            "test_restart_happens_at_period_not_period_plus_one", "test_period_doubling",
            "test_lr_values_form_cosine_curve_within_period"],
    "M7": ["test_checkpoint_concurrent_save", "test_concurrent_checkpoint_save"],
    "M8": ["test_mixed_precision_nan", "test_mixed_precision_gradient_scale", "test_mixed_precision_loss_scale",
            "test_mixed_precision_accumulation_scaling", "test_mixed_precision_nan_propagation"],
    "M9": ["test_data_augmentation_seed", "test_augmentation_reproducibility", "test_augmentation_seed_reproducibility"],
    "M10": ["test_distributed_data_loader"],

    # === A: Distributed Training (A1-A10) ===
    "A1": ["test_parameter_server_race", "test_param_update_ordering",
            "test_concurrent_gradient_application_version_consistency", "test_concurrent_read_during_write"],
    "A2": ["test_gradient_allreduce_deadlock", "test_allreduce_timeout_recovery",
            "test_concurrent_submit_and_reduce", "test_barrier_count_accuracy"],
    "A3": ["test_data_parallelism_shard_overlap", "test_shard_uniqueness"],
    "A4": ["test_model_parallelism_tensor_split", "test_tensor_split_boundary", "test_even_split",
            "test_tensor_split_preserves_elements", "test_split_merge_roundtrip_1d", "test_split_even_division",
            "test_split_merge_roundtrip_2d_axis1", "test_split_merge_roundtrip_2d_axis0", "test_split_merge_3d_axis1"],
    "A5": ["test_elastic_scaling_registration", "test_worker_join_leave",
            "test_concurrent_registration_unique_indices",
            "test_reregister_same_worker", "test_reregister_preserves_index",
            "test_reregister_does_not_create_index_gaps", "test_reregister_then_new_worker_sequential_indices"],
    "A6": ["test_checkpoint_barrier_timeout", "test_barrier_synchronization", "test_barrier_with_slow_worker"],
    "A7": ["test_gradient_compression_threshold", "test_compression_accuracy",
            "test_error_feedback_improves_accuracy", "test_compression_ratio_respected",
            "test_error_feedback_with_2d_tensors", "test_error_feedback_2d_multiple_rounds"],
    "A8": ["test_ring_allreduce_topology", "test_topology_reconstruction", "test_ring_with_failed_worker",
            "test_reduce_after_worker_removal_averages_correctly", "test_reduce_with_all_workers_present",
            "test_remove_worker_clears_stale_buffer", "test_reduce_after_node_removal"],
    "A9": ["test_async_sgd_staleness_bound", "test_staleness_rejection",
            "test_stale_gradient_still_applied_bug_a9",
            "test_stale_gradient_rejected", "test_near_stale_gradient_scaled_lr",
            "test_version_reflects_completed_update", "test_staleness_boundary_exactly_at_max",
            "test_staleness_one_beyond_max_rejected"],
    "A10": ["test_fault_tolerant_resume", "test_resume_point_correctness"],

    # === B: Model Serving (B1-B10) ===
    "B1": ["test_model_loading_memory_leak", "test_model_unload_cleanup"],
    "B2": ["test_request_batching_timeout", "test_batch_size_limit"],
    "B3": ["test_ab_testing_traffic_split", "test_traffic_split_precision", "test_ab_testing_weight_validation"],
    "B4": ["test_canary_deployment_rollback", "test_canary_rollback_race",
            "test_canary_significance_test", "test_canary_rollback_decision",
            "test_canary_promote_decision", "test_canary_unequal_sample_sizes_df_calculation",
            "test_canary_start_and_promote", "test_canary_rollback", "test_rollback_nonexistent_deployment"],
    "B5": ["test_model_warmup_execution", "test_warmup_before_serving"],
    "B6": ["test_model_fallback_behavior"],
    "B7": ["test_input_validation_schema", "test_schema_drift_detection"],
    "B8": ["test_output_postprocess_type", "test_postprocess_type_mismatch"],
    "B9": ["test_concurrent_model_swap", "test_model_swap_atomicity", "test_swap_atomicity"],
    "B10": ["test_model_timeout_handling"],

    # === C: Feature Store (C1-C8) ===
    "C1": ["test_online_offline_consistency", "test_feature_value_match", "test_write_failure_rollback",
            "test_feature_consistency_during_training", "test_consistency_after_transform_update"],
    "C2": ["test_pit_join_timezone", "test_pit_join_utc_conversion"],
    "C3": ["test_drift_threshold_float", "test_drift_threshold_comparison",
            "test_drift_at_exact_threshold", "test_small_shift_not_flagged_at_low_threshold",
            "test_small_shift_within_noise_not_flagged", "test_large_shift_flagged"],
    "C4": ["test_feature_transform_order", "test_transform_pipeline_sequence",
            "test_dependent_transforms_order", "test_none_propagation_in_pipeline",
            "test_transform_then_drift_detection"],
    "C5": ["test_feature_backfill_race", "test_backfill_idempotency"],
    "C6": ["test_feature_schema_evolution", "test_schema_type_change_rejected",
            "test_feature_schema_evolution_compatibility"],
    "C7": ["test_feature_serving_cache_stampede", "test_concurrent_cache_miss"],
    "C8": ["test_feature_dependency_cycle", "test_self_cycle_detected", "test_has_cycle_bug_c8"],

    # === D: Data Pipeline (D1-D10) ===
    "D1": ["test_data_validation_schema", "test_schema_mismatch_detection",
            "test_validation_uses_correct_schema_version"],
    "D2": ["test_data_dedup_across_partitions"],
    "D3": ["test_backfill_dedup", "test_duplicate_processing_prevention"],
    "D4": ["test_late_arriving_data", "test_window_close_handling"],
    "D5": ["test_partition_distribution", "test_skew_detection"],
    "D6": ["test_checkpoint_uses_min_step", "test_checkpoint_requires_all_workers",
            "test_should_checkpoint_uses_last_checkpoint_step", "test_second_checkpoint_timing"],
    "D7": ["test_watermark_advancement"],
    "D8": ["test_pipeline_dag_cycle", "test_dag_cycle_detection"],
    "D9": ["test_idempotent_processing"],
    "D10": ["test_schema_registry_versioning"],

    # === E: Experiment Tracking (E1-E8) ===
    "E1": ["test_metric_logging_race", "test_concurrent_metric_write", "test_concurrent_metric_logging"],
    "E2": ["test_hyperparameter_float_equality", "test_hyperparameter_comparison",
            "test_float_precision_comparison", "test_hyperparameter_comparison_after_experiment"],
    "E3": ["test_reproducibility_seed", "test_seed_propagation"],
    "E4": ["test_experiment_fork_parent", "test_parent_reference_integrity",
            "test_delete_parent_orphans_children", "test_fork_deleted_parent_bug_e4",
            "test_delete_experiment_orphans_children_bug_e4",
            "test_experiment_fork_inherits_hyperparameters", "test_experiment_fork_from_deleted_parent"],
    "E5": ["test_artifact_upload_partial", "test_partial_upload_cleanup"],
    "E6": ["test_comparison_query_n_plus_1", "test_comparison_query_count",
            "test_compare_experiments_n1_pattern_bug_e6"],
    "E7": ["test_metric_aggregation_overflow", "test_aggregation_precision",
            "test_metric_aggregation_large_values_bug_e7"],
    "E8": ["test_tag_search_injection", "test_tag_search_parameterized"],

    # === F: Database Transactions (F1-F10) ===
    "F1": ["test_cross_db_isolation"],
    "F2": ["test_transaction_rollback_on_error"],
    "F3": ["test_read_replica_consistency"],
    "F4": ["test_outbox_delivery"],
    "F5": ["test_connection_pool_exhaustion"],
    "F6": ["test_migration_backward_compat"],
    "F7": ["test_optimistic_locking"],
    "F8": ["test_batch_insert_atomicity"],
    "F9": ["test_cascade_delete_ordering"],
    "F10": ["test_lock_ordering", "test_deadlock_prevention",
             "test_no_deadlock_acquiring_multiple_locks", "test_lock_context_manager_no_leak"],

    # === G: Authentication & RBAC (G1-G6) ===
    "G1": ["test_jwt_claim_propagation", "test_downstream_claims_preserved", "test_auth_token_forwarding"],
    "G2": ["test_token_refresh_race", "test_concurrent_refresh_safety",
            "test_concurrent_token_refresh_safety", "test_double_refresh_same_token"],
    "G3": ["test_service_auth_required", "test_internal_auth_bypass_blocked", "test_service_client_auth_bypass"],
    "G4": ["test_rbac_cache_invalidation", "test_permission_update_propagation",
            "test_permission_cache_invalidated_on_token_refresh"],
    "G5": ["test_api_key_rotation_window", "test_rotation_grace_period", "test_no_gap_during_rotation"],
    "G6": ["test_mtls_certificate_chain", "test_certificate_validation",
            "test_validate_valid_chain_bug_g6", "test_validate_untrusted_chain_bug_g6"],

    # === H: Caching & Performance (H1-H8) ===
    "H1": ["test_model_cache_eviction", "test_eviction_during_inference_safe",
            "test_concurrent_put_and_get", "test_eviction_during_use"],
    "H2": ["test_feature_cache_ttl_race", "test_ttl_expiry_consistency"],
    "H3": ["test_distributed_cache_sync"],
    "H4": ["test_cache_warmup_priority"],
    "H5": ["test_cache_coherence_protocol"],
    "H6": ["test_cache_aside_stale_data"],
    "H7": ["test_write_behind_buffer"],
    "H8": ["test_lru_eviction_priority"],

    # === I: Security (I1-I10) ===
    "I1": ["test_experiment_filter_injection", "test_parameterized_query_used"],
    "I2": ["test_webhook_ssrf_blocked", "test_internal_url_rejected", "test_external_url_accepted",
            "test_webhook_allows_internal_url_bug_i2", "test_webhook_allows_localhost_bug_i2",
            "test_webhook_allows_private_network_bug_i2"],
    "I3": ["test_pickle_deserialization_blocked", "test_safe_serialization_used"],
    "I4": ["test_rate_limit_bypass_blocked", "test_rate_limit_uniform",
            "test_rate_limit_bypass_via_forwarded_for_bug_i4", "test_rate_limit_bypass_with_many_ips",
            "test_rate_limit_with_forwarded_header", "test_concurrent_rate_limiting"],
    "I5": ["test_model_idor_blocked", "test_authorization_check_model"],
    "I6": ["test_xxe_prevention", "test_xml_safe_parsing"],
    "I7": ["test_mass_assignment_blocked", "test_field_allowlist_enforced",
            "test_mass_assignment_privilege_escalation_bug_i7", "test_mass_assignment_tenant_override_bug_i7"],
    "I8": ["test_api_key_timing_attack", "test_constant_time_compare", "test_timing_attack_api_key_bug_i8"],
    "I9": ["test_path_traversal_blocked", "test_artifact_path_validated", "test_storage_path_traversal_blocked"],
    "I10": ["test_redos_prevention", "test_search_regex_safe"],

    # === J: Observability (J1-J7) ===
    "J1": ["test_trace_context_kafka", "test_distributed_trace_propagation", "test_gateway_propagates_trace_context"],
    "J2": ["test_correlation_id_match"],
    "J3": ["test_metric_cardinality", "test_label_count_limit"],
    "J4": ["test_log_sampling_rate"],
    "J5": ["test_error_aggregation_groups", "test_error_aggregation_grouping"],
    "J6": ["test_inference_latency_histogram", "test_histogram_bucket_overflow", "test_prediction_latency_units"],
    "J7": ["test_alert_dedup_window"],

    # === K: Configuration (K1-K8) ===
    "K1": ["test_env_var_precedence", "test_config_override_order", "test_config_precedence"],
    "K2": ["test_secret_rotation_zero_downtime"],
    "K3": ["test_feature_flag_race", "test_flag_evaluation_consistency",
            "test_concurrent_flag_evaluation_and_update"],
    "K4": ["test_config_reload_atomic", "test_partial_config_prevention"],
    "K5": ["test_service_discovery_stale"],
    "K6": ["test_config_schema_validation"],
    "K7": ["test_env_specific_config"],
    "K8": ["test_config_encryption"],
}

# Bug dependency graph: a bug can only be considered "fixed" after its prerequisites are fixed.
# Maps bug_id -> list of prerequisite bug_ids that must be fixed first.
BUG_DEPENDENCIES = {
    # Setup bugs are prerequisites for many downstream bugs
    "L3": ["L1"],
    "L4": ["L1"],
    "L9": ["L1"],
    "L11": ["L1"],
    "L12": ["L1"],
    "L13": ["L1"],
    "L15": ["L1"],

    # ML pipeline depends on setup
    "M1": ["L1", "L2"],
    "M2": ["L1"],
    "M3": ["L1"],
    "M4": ["L1"],
    "M5": ["L1"],
    "M6": ["L1"],
    "M7": ["L1", "M1"],
    "M8": ["L1", "M2"],
    "M9": ["L1"],
    "M10": ["L1"],

    # Distributed training depends on setup and some ML pipeline
    "A1": ["L1"],
    "A2": ["L1", "A1"],
    "A3": ["L1"],
    "A4": ["L1"],
    "A5": ["L1"],
    "A6": ["L1"],
    "A7": ["L1", "A1"],
    "A8": ["L1", "A2"],
    "A9": ["L1", "A1"],
    "A10": ["L1", "A6"],

    # Model serving depends on setup
    "B1": ["L1"],
    "B2": ["L1"],
    "B3": ["L1", "B2"],
    "B4": ["L1", "B3"],
    "B5": ["L1"],
    "B6": ["L1", "B1"],
    "B7": ["L1"],
    "B8": ["L1", "B7"],
    "B9": ["L1", "B1"],
    "B10": ["L1"],

    # Feature store depends on setup
    "C1": ["L1"],
    "C2": ["L1", "C1"],
    "C3": ["L1", "C1"],
    "C4": ["L1"],
    "C5": ["L1", "C1"],
    "C6": ["L1", "C1"],
    "C7": ["L1", "C1"],
    "C8": ["L1"],

    # Data pipeline depends on setup and Kafka
    "D1": ["L1", "L4"],
    "D2": ["L1", "L4"],
    "D3": ["L1", "D1"],
    "D4": ["L1", "D1"],
    "D5": ["L1", "L4"],
    "D6": ["L1"],
    "D7": ["L1", "D4"],
    "D8": ["L1"],
    "D9": ["L1", "D3"],
    "D10": ["L1", "D1"],

    # Experiment tracking depends on setup and DB
    "E1": ["L1"],
    "E2": ["L1"],
    "E3": ["L1"],
    "E4": ["L1", "E1"],
    "E5": ["L1", "L9"],
    "E6": ["L1", "E1"],
    "E7": ["L1", "E1"],
    "E8": ["L1"],

    # Database depends on setup
    "F1": ["L1"],
    "F2": ["L1", "F1"],
    "F3": ["L1", "F1"],
    "F4": ["L1", "L4"],
    "F5": ["L1"],
    "F6": ["L1"],
    "F7": ["L1", "F1"],
    "F8": ["L1", "F1"],
    "F9": ["L1", "F1"],
    "F10": ["L1"],

    # Auth depends on setup
    "G1": ["L1"],
    "G2": ["L1", "G1"],
    "G3": ["L1", "G1"],
    "G4": ["L1", "G1"],
    "G5": ["L1"],
    "G6": ["L1"],

    # Caching depends on setup and Redis
    "H1": ["L1", "L6"],
    "H2": ["L1", "L6"],
    "H3": ["L1", "L6"],
    "H4": ["L1", "H1"],
    "H5": ["L1", "H1"],
    "H6": ["L1", "H1"],
    "H7": ["L1", "H1"],
    "H8": ["L1", "H1"],

    # Security has fewer dependencies
    "I1": ["L1"],
    "I2": ["L1"],
    "I3": ["L1"],
    "I4": ["L1"],
    "I5": ["L1"],
    "I6": ["L1"],
    "I7": ["L1"],
    "I8": ["L1", "G5"],
    "I9": ["L1", "L9"],
    "I10": ["L1"],

    # Observability depends on setup
    "J1": ["L1", "L4"],
    "J2": ["L1", "J1"],
    "J3": ["L1"],
    "J4": ["L1", "L12"],
    "J5": ["L1"],
    "J6": ["L1"],
    "J7": ["L1", "J5"],

    # Configuration depends on setup
    "K1": ["L1"],
    "K2": ["L1"],
    "K3": ["L1"],
    "K4": ["L1", "K1"],
    "K5": ["L1", "L5"],
    "K6": ["L1", "K1"],
    "K7": ["L1", "K1"],
    "K8": ["L1", "K2"],
}
