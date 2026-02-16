"""Reward model for VaultFS senior environment."""

from __future__ import annotations

THRESHOLDS = [0.50, 0.75, 0.90, 1.0]
REWARDS = [0.15, 0.35, 0.65, 1.0]

BUG_TEST_MAPPING = {
    # L: Setup / Configuration (4 bugs)
    "L1": [
        "test_no_nested_runtime_creation",
        "test_async_pool_creation",
    ],
    "L2": [
        "test_db_pool_configuration",
        "test_db_pool_timeout_settings",
    ],
    "L3": [
        "test_config_invalid_port_returns_error",
        "test_config_missing_env_returns_error",
        "test_config_invalid_upload_size_returns_error",
    ],
    "L4": [
        "test_graceful_shutdown_signal_handler",
        "test_shutdown_completes_inflight_requests",
    ],

    # A: Ownership / Borrowing (5 bugs)
    "A1": [
        "test_upload_file_no_use_after_move",
        "test_upload_preserves_metadata_size",
        "test_upload_source_no_use_after_move",
    ],
    "A2": [
        "test_get_changes_returns_owned_values",
        "test_changes_since_does_not_hold_lock",
        "test_sync_source_returns_owned",
    ],
    "A3": [
        "test_versioning_create_no_double_borrow",
        "test_versioning_prune_no_double_borrow",
        "test_versioning_source_immutable_ref",
    ],
    "A4": [
        "test_list_files_no_use_after_move",
        "test_list_files_skips_tmp_before_move",
    ],
    "A5": [
        "test_extract_info_no_partial_move",
        "test_split_metadata_no_partial_move",
    ],

    # B: Lifetime Issues (4 bugs)
    "B1": [
        "test_cache_get_with_fallback_returns_owned",
        "test_cache_config_value_returns_owned",
        "test_cache_source_get_with_fallback_returns_owned",
        "test_cache_source_get_config_value_returns_owned",
        "test_cache_fallback_idempotent",
    ],
    "B2": [
        "test_file_repo_lifetime_annotation",
        "test_file_repo_query_compiles",
    ],
    "B3": [
        "test_chunk_no_self_referential_struct",
        "test_chunk_can_be_moved",
    ],
    "B4": [
        "test_create_share_owned_across_await",
        "test_share_no_dangling_reference",
    ],

    # C: Concurrency / Async (5 bugs)
    "C1": [
        "test_no_deadlock_consistent_lock_order",
        "test_lock_file_for_user_completes",
        "test_lock_user_files_completes",
        "test_lock_manager_source_consistent_ordering",
        "test_concurrent_interleaved_locks_no_deadlock",
    ],
    "C2": [
        "test_save_to_disk_uses_async_io",
        "test_large_file_no_runtime_block",
    ],
    "C3": [
        "test_record_change_atomic_version",
        "test_concurrent_record_no_duplicate_version",
        "test_sync_source_atomic_version",
    ],
    "C4": [
        "test_upload_multipart_future_is_send",
        "test_upload_uses_arc_mutex_not_rc",
    ],
    "C5": [
        "test_notification_send_with_receiver_alive",
        "test_notification_subscribe_before_send",
        "test_notification_source_keeps_receiver",
    ],

    # D: Error Handling (4 bugs)
    "D1": [
        "test_get_file_empty_chunks_returns_error",
        "test_get_file_no_unwrap_on_none",
    ],
    "D2": [
        "test_get_file_handler_all_match_arms",
        "test_get_file_handles_db_error",
    ],
    "D3": [
        "test_user_repo_error_conversion",
        "test_user_repo_incompatible_error_handled",
    ],
    "D4": [
        "test_temp_file_drop_no_panic",
        "test_temp_dir_drop_no_panic",
        "test_temp_file_missing_no_panic",
        "test_temp_file_source_no_unwrap_in_drop",
    ],

    # E: Memory / Resource (3 bugs)
    "E1": [
        "test_folder_no_rc_cycle_leak",
        "test_folder_uses_weak_parent",
        "test_folder_source_uses_weak",
    ],
    "E2": [
        "test_chunker_file_handle_closed_on_error",
        "test_chunker_no_leaked_handles",
    ],
    "E3": [
        "test_sync_bounded_channel",
        "test_sync_backpressure",
        "test_sync_source_bounded_channel",
    ],

    # F: Security (4 bugs)
    "F1": [
        "test_path_traversal_rejected",
        "test_path_traversal_encoded_rejected",
        "test_path_within_base_dir_allowed",
    ],
    "F2": [
        "test_search_uses_parameterized_query",
        "test_sql_injection_query_escaped",
        "test_sql_injection_sort_column_validated",
    ],
    "F3": [
        "test_api_key_verification_correct",
        "test_api_key_constant_time_comparison",
        "test_signature_constant_time_comparison",
        "test_hash_constant_time_comparison",
    ],
    "F4": [
        "test_mmap_keeps_file_handle_alive",
        "test_mmap_bounds_checked",
        "test_mmap_null_ptr_check",
    ],
}

BUG_DEPENDENCIES = {
    # Setup chain (depth 3): L3 -> L2 -> L1
    "L2": ["L1"],
    "L3": ["L2"],
    "L4": ["L3"],

    # Ownership -> Concurrency -> Error chain (depth 3): D1 -> C2 -> A1
    "C2": ["A1"],
    "D1": ["C2"],

    # Diamond: C1 depends on BOTH A3 AND E1
    "C1": ["A3", "E1"],

    # Cross-category links
    "A2": ["C3"],
    "B1": ["L3"],
    "C4": ["B4"],
    "F2": ["A5"],
    "F1": ["D2"],
    "E3": ["C5"],
}


def sparse_reward(pass_rate: float) -> float:
    for threshold, reward in reversed(list(zip(THRESHOLDS, REWARDS))):
        if pass_rate >= threshold:
            return reward
    return 0.0
