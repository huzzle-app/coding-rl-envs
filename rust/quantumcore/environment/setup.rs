use std::collections::{HashMap, HashSet};
use std::process::{Command, Output};
use std::time::Instant;
use serde::{Deserialize, Serialize};

// ==============================================================================
// QuantumCore RL Environment Wrapper
// Terminal Bench v2 - Rust HFT Platform with 75 bugs across 10 services
// ==============================================================================

/// The set of valid action types an agent can perform
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ActionType {
    /// Edit a file: provide file path and new content
    Edit { file: String, content: String },
    /// Create a new file
    Create { file: String, content: String },
    /// Delete a file
    Delete { file: String },
    /// Run a shell command
    Command { command: String },
    /// Run tests for a specific service
    TestService { service: String },
    /// Run tests matching a pattern
    TestPattern { pattern: String },
    /// Read a file
    Read { file: String },
    /// List files in a directory
    ListDir { path: String },
    /// Search for a pattern in files
    Grep { pattern: String, path: Option<String> },
}

/// Defines the valid observation space
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ObservationSpace {
    /// Current step number
    pub step: usize,
    /// Maximum steps allowed
    pub max_steps: usize,
    /// Total number of bugs to fix
    pub total_bugs: usize,
    /// List of services in the platform
    pub services: Vec<String>,
    /
    pub bug_categories: HashMap<String, usize>,
    /// Test categories with counts
    pub test_categories: HashMap<String, usize>,
    /
    pub bug_dependencies: HashMap<String, Vec<String>>,
    /// Files that can be modified (source files only, not tests)
    pub editable_file_patterns: Vec<String>,
}

/// Defines the valid action space
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionSpace {
    /// Valid action types
    pub action_types: Vec<String>,
    /// Valid services for targeted testing
    pub services: Vec<String>,
    /// File path patterns that can be edited
    pub editable_paths: Vec<String>,
    /// Maximum command length
    pub max_command_length: usize,
    /// Maximum file content length
    pub max_content_length: usize,
}

const SERVICES: [&str; 10] = [
    "gateway", "auth", "orders", "matching", "risk",
    "positions", "market", "portfolio", "ledger", "alerts"
];

/
const BUG_CATEGORIES: [(&str, &str, usize); 11] = [
    ("L", "Setup/Configuration", 8),
    ("A", "Ownership/Borrowing", 10),
    ("B", "Concurrency", 12),
    ("C", "Error Handling", 8),
    ("D", "Memory/Resources", 8),
    ("E", "Unsafe Code", 6),
    ("F", "Numerical/Financial", 10),
    ("G", "Distributed Systems", 8),
    ("H", "Security", 5),
    ("I", "Request Validation", 3),  // I1, I2, I3 from gateway/auth
    ("J", "Observability", 2),       // J1, J2 from market/portfolio
];

/
fn bug_test_mapping() -> HashMap<String, Vec<String>> {
    let mut map = HashMap::new();

    // L: Setup/Configuration (8 bugs)
    map.insert("L1".to_string(), vec!["test_nats_reconnection".to_string(), "test_nats_connection_recovery".to_string()]);
    map.insert("L2".to_string(), vec!["test_tokio_runtime_cpu_bound".to_string(), "test_blocking_in_async_detected".to_string()]);
    map.insert("L3".to_string(), vec!["test_db_pool_under_load".to_string(), "test_connection_pool_exhaustion".to_string()]);
    map.insert("L4".to_string(), vec!["test_graceful_shutdown".to_string(), "test_shutdown_drains_connections".to_string()]);
    map.insert("L5".to_string(), vec!["test_service_discovery_consistency".to_string(), "test_discovery_race_condition".to_string()]);
    map.insert("L6".to_string(), vec!["test_config_hot_reload_safe".to_string(), "test_config_reload_no_crash".to_string()]);
    map.insert("L7".to_string(), vec!["test_timestamp_timezone_handling".to_string(), "test_utc_consistency".to_string()]);
    map.insert("L8".to_string(), vec!["test_tls_certificate_validation".to_string(), "test_tls_not_disabled".to_string()]);

    // A: Ownership/Borrowing (10 bugs)
    map.insert("A1".to_string(), vec!["test_order_no_use_after_move".to_string(), "test_order_processing_ownership".to_string()]);
    map.insert("A2".to_string(), vec!["test_closure_borrow_safety".to_string(), "test_order_add_no_dangling_ref".to_string()]);
    map.insert("A3".to_string(), vec!["test_position_iterator_no_mutable_borrow".to_string(), "test_fill_during_iteration".to_string()]);
    map.insert("A4".to_string(), vec!["test_option_partial_move_safe".to_string(), "test_risk_option_handling".to_string()]);
    map.insert("A5".to_string(), vec!["test_market_ref_lifetime".to_string(), "test_no_dangling_reference".to_string()]);
    map.insert("A6".to_string(), vec!["test_portfolio_no_double_borrow".to_string(), "test_concurrent_portfolio_update".to_string()]);
    map.insert("A7".to_string(), vec!["test_async_block_ownership".to_string(), "test_ledger_async_move".to_string()]);
    map.insert("A8".to_string(), vec!["test_interior_mutability_safe".to_string(), "test_alert_borrow_checker".to_string()]);
    map.insert("A9".to_string(), vec!["test_no_self_referential".to_string(), "test_orderbook_structure_safe".to_string()]);
    map.insert("A10".to_string(), vec!["test_lifetime_variance_sound".to_string(), "test_price_ref_safety".to_string()]);

    // B: Concurrency (12 bugs)
    map.insert("B1".to_string(), vec!["test_no_lock_ordering_deadlock".to_string(), "test_concurrent_order_and_risk_no_deadlock".to_string()]);
    map.insert("B2".to_string(), vec!["test_no_blocking_in_async".to_string(), "test_order_processing_async_safe".to_string()]);
    map.insert("B3".to_string(), vec!["test_order_book_race_condition".to_string(), "test_best_prices_consistent".to_string()]);
    map.insert("B4".to_string(), vec!["test_future_is_send".to_string(), "test_gateway_futures_send".to_string()]);
    map.insert("B5".to_string(), vec!["test_mutex_poison_handled".to_string(), "test_risk_mutex_recovery".to_string()]);
    map.insert("B6".to_string(), vec!["test_channel_backpressure".to_string(), "test_market_feed_backpressure".to_string()]);
    map.insert("B7".to_string(), vec!["test_atomic_ordering_correct".to_string(), "test_position_atomic_visibility".to_string()]);
    map.insert("B8".to_string(), vec!["test_no_spin_loop_in_async".to_string(), "test_ledger_no_busy_wait".to_string()]);
    map.insert("B9".to_string(), vec!["test_condvar_spurious_wakeup".to_string(), "test_alert_condvar_loop".to_string()]);
    map.insert("B10".to_string(), vec!["test_thread_pool_bounded".to_string(), "test_gateway_pool_limit".to_string()]);
    map.insert("B11".to_string(), vec!["test_lockfree_aba_prevention".to_string(), "test_order_book_aba_safe".to_string()]);
    map.insert("B12".to_string(), vec!["test_memory_ordering_prices".to_string(), "test_market_price_visibility".to_string()]);

    // C: Error Handling (8 bugs)
    map.insert("C1".to_string(), vec!["test_no_unwrap_in_production".to_string(), "test_order_error_handling".to_string()]);
    map.insert("C2".to_string(), vec!["test_error_type_preserves_info".to_string(), "test_risk_error_chain".to_string()]);
    map.insert("C3".to_string(), vec!["test_async_panic_caught".to_string(), "test_matching_panic_recovery".to_string()]);
    map.insert("C4".to_string(), vec!["test_drop_handles_error".to_string(), "test_position_drop_safe".to_string()]);
    map.insert("C5".to_string(), vec!["test_error_chain_complete".to_string(), "test_ledger_error_context".to_string()]);
    map.insert("C6".to_string(), vec!["test_error_context_present".to_string(), "test_portfolio_error_detail".to_string()]);
    map.insert("C7".to_string(), vec!["test_no_catchall_error".to_string(), "test_auth_error_specific".to_string()]);
    map.insert("C8".to_string(), vec!["test_panic_hook_set".to_string(), "test_gateway_panic_handling".to_string()]);

    // D: Memory/Resources (8 bugs)
    map.insert("D1".to_string(), vec!["test_vec_growth_bounded".to_string(), "test_order_vec_limit".to_string()]);
    map.insert("D2".to_string(), vec!["test_no_arc_cycle_leak".to_string(), "test_position_memory_stable".to_string()]);
    map.insert("D3".to_string(), vec!["test_file_handle_closed".to_string(), "test_ledger_file_cleanup".to_string()]);
    map.insert("D4".to_string(), vec!["test_connection_pool_no_leak".to_string(), "test_market_conn_cleanup".to_string()]);
    map.insert("D5".to_string(), vec!["test_cache_has_eviction".to_string(), "test_risk_cache_bounded".to_string()]);
    map.insert("D6".to_string(), vec!["test_no_string_alloc_hot_path".to_string(), "test_matching_perf_allocation".to_string()]);
    map.insert("D7".to_string(), vec!["test_no_large_stack_alloc".to_string(), "test_portfolio_stack_safe".to_string()]);
    map.insert("D8".to_string(), vec!["test_buffer_released".to_string(), "test_gateway_buffer_cleanup".to_string()]);

    // E: Unsafe Code (6 bugs)
    map.insert("E1".to_string(), vec!["test_price_conversion_safe".to_string(), "test_no_ub_transmute".to_string()]);
    map.insert("E2".to_string(), vec!["test_no_uninit_read".to_string(), "test_market_memory_init".to_string()]);
    map.insert("E3".to_string(), vec!["test_pointer_arithmetic_safe".to_string(), "test_ledger_pointer_bounds".to_string()]);
    map.insert("E4".to_string(), vec!["test_atomic_ordering_no_data_race".to_string(), "test_lockfree_ordering_correct".to_string()]);
    map.insert("E5".to_string(), vec!["test_send_sync_correct".to_string(), "test_shared_thread_safety".to_string()]);
    map.insert("E6".to_string(), vec!["test_no_use_after_free".to_string(), "test_market_ffi_safe".to_string()]);

    // F: Numerical/Financial (10 bugs)
    map.insert("F1".to_string(), vec!["test_price_decimal_precision".to_string(), "test_no_float_for_money".to_string()]);
    map.insert("F2".to_string(), vec!["test_quantity_overflow_handled".to_string(), "test_checked_arithmetic".to_string()]);
    map.insert("F3".to_string(), vec!["test_decimal_rounding_correct".to_string(), "test_ledger_rounding_mode".to_string()]);
    map.insert("F4".to_string(), vec!["test_currency_conversion_precise".to_string(), "test_no_float_conversion_rate".to_string()]);
    map.insert("F5".to_string(), vec!["test_fee_calculation_precise".to_string(), "test_fee_no_truncation".to_string()]);
    map.insert("F6".to_string(), vec!["test_pnl_calculation_correct".to_string(), "test_position_pnl_accurate".to_string()]);
    map.insert("F7".to_string(), vec!["test_margin_no_overflow".to_string(), "test_risk_margin_safe".to_string()]);
    map.insert("F8".to_string(), vec!["test_price_tick_validation".to_string(), "test_invalid_tick_rejected".to_string()]);
    map.insert("F9".to_string(), vec!["test_order_value_correct".to_string(), "test_no_stale_mark_to_market".to_string()]);
    map.insert("F10".to_string(), vec!["test_tax_rounding_correct".to_string(), "test_compound_rounding_safe".to_string()]);

    // G: Distributed Systems (8 bugs)
    map.insert("G1".to_string(), vec!["test_event_ordering_guaranteed".to_string(), "test_nats_sequence_order".to_string()]);
    map.insert("G2".to_string(), vec!["test_distributed_lock_released".to_string(), "test_position_lock_cleanup".to_string()]);
    map.insert("G3".to_string(), vec!["test_split_brain_prevented".to_string(), "test_matching_failover_safe".to_string()]);
    map.insert("G4".to_string(), vec!["test_idempotency_key_unique".to_string(), "test_order_idempotent".to_string()]);
    map.insert("G5".to_string(), vec!["test_saga_compensation_correct".to_string(), "test_ledger_rollback_complete".to_string()]);
    map.insert("G6".to_string(), vec!["test_circuit_breaker_correct".to_string(), "test_gateway_circuit_state".to_string()]);
    map.insert("G7".to_string(), vec!["test_retry_with_backoff".to_string(), "test_no_retry_storm".to_string()]);
    map.insert("G8".to_string(), vec!["test_leader_election_safe".to_string(), "test_matching_leader_consistent".to_string()]);

    // H: Security (5 bugs)
    map.insert("H1".to_string(), vec!["test_jwt_secret_not_hardcoded".to_string(), "test_jwt_secret_rotatable".to_string()]);
    map.insert("H2".to_string(), vec!["test_constant_time_comparison".to_string(), "test_no_timing_attack".to_string()]);
    map.insert("H3".to_string(), vec!["test_sql_injection_prevented".to_string(), "test_parameterized_queries".to_string()]);
    map.insert("H4".to_string(), vec!["test_rate_limit_not_bypassable".to_string(), "test_header_spoof_blocked".to_string()]);
    map.insert("H5".to_string(), vec!["test_no_sensitive_data_logged".to_string(), "test_api_key_masked_in_logs".to_string()]);

    map
}

/
fn bug_dependencies() -> HashMap<String, Vec<String>> {
    let mut deps = HashMap::new();

    // Setup chain (depth 3): L1 -> L5 -> L6 -> L7
    deps.insert("L5".to_string(), vec!["L1".to_string()]);
    deps.insert("L6".to_string(), vec!["L5".to_string()]);
    deps.insert("L7".to_string(), vec!["L6".to_string()]);

    // Setup -> Concurrency: L2 -> B2 -> B8
    deps.insert("B2".to_string(), vec!["L2".to_string()]);
    deps.insert("B8".to_string(), vec!["B2".to_string()]);

    // Setup -> Security: L8 -> H1
    deps.insert("H1".to_string(), vec!["L8".to_string()]);

    // Ownership chain: A2 -> A9 -> B11
    deps.insert("A9".to_string(), vec!["A2".to_string()]);
    deps.insert("B11".to_string(), vec!["A9".to_string()]);

    // Concurrency diamond: B1 + B3 -> B12
    deps.insert("B12".to_string(), vec!["B1".to_string(), "B3".to_string()]);
    deps.insert("G8".to_string(), vec!["B1".to_string()]);

    // Concurrency -> Distributed: B5 -> G6
    deps.insert("G6".to_string(), vec!["B5".to_string()]);

    // Error chain: C1 -> C3 -> C8
    deps.insert("C3".to_string(), vec!["C1".to_string()]);
    deps.insert("C8".to_string(), vec!["C3".to_string()]);

    // Memory chain: D1 -> D5 -> D6
    deps.insert("D5".to_string(), vec!["D1".to_string()]);
    deps.insert("D6".to_string(), vec!["D5".to_string()]);

    // Memory diamond: D2 + D4 -> D8
    deps.insert("D8".to_string(), vec!["D2".to_string(), "D4".to_string()]);

    // Unsafe chain: E1 -> E4 -> E5
    deps.insert("E4".to_string(), vec!["E1".to_string()]);
    deps.insert("E5".to_string(), vec!["E4".to_string()]);

    // Financial chain (depth 4): F1 -> F5 -> F6 -> F9
    deps.insert("F1".to_string(), vec!["E2".to_string()]);
    deps.insert("F5".to_string(), vec!["F1".to_string()]);
    deps.insert("F6".to_string(), vec!["F5".to_string()]);
    deps.insert("F9".to_string(), vec!["F6".to_string()]);

    // Financial diamond: F1 + F2 -> F7
    deps.insert("F7".to_string(), vec!["F1".to_string(), "F2".to_string()]);

    // Distributed chain: G1 -> G2 -> G3
    deps.insert("G2".to_string(), vec!["G1".to_string()]);
    deps.insert("G3".to_string(), vec!["G2".to_string()]);

    // Cross-category diamond: G7 + G6 -> H4
    deps.insert("H4".to_string(), vec!["G7".to_string(), "G6".to_string()]);

    // Security chain: H2 -> H3 -> H5
    deps.insert("H3".to_string(), vec!["H2".to_string()]);
    deps.insert("H5".to_string(), vec!["H3".to_string()]);

    deps
}

/// QuantumCore RL Environment
pub struct Environment {
    work_dir: String,
    max_steps: usize,
    start_time: Option<Instant>,
    step_count: usize,
    test_results: TestResults,
    previous_pass_rate: f64,
    previous_passed_tests: HashSet<String>,
    bug_test_map: HashMap<String, Vec<String>>,
    bug_deps: HashMap<String, Vec<String>>,
}

#[derive(Default, Clone, Serialize, Deserialize)]
pub struct TestResults {
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
    pub skipped: usize,
    pub all_passed: bool,
    pub pass_rate: f64,
    pub failed_tests: Vec<String>,
    pub passed_tests: Vec<String>,
    pub service_results: HashMap<String, ServiceTestResults>,
}

#[derive(Default, Clone, Serialize, Deserialize)]
pub struct ServiceTestResults {
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
}

impl Environment {
    pub fn new(work_dir: &str, max_steps: usize) -> Self {
        Self {
            work_dir: work_dir.to_string(),
            max_steps,
            start_time: None,
            step_count: 0,
            test_results: TestResults::default(),
            previous_pass_rate: 0.0,
            previous_passed_tests: HashSet::new(),
            bug_test_map: bug_test_mapping(),
            bug_deps: bug_dependencies(),
        }
    }

    /// Get the observation space description for the agent
    pub fn observation_space(&self) -> ObservationSpace {
        let mut bug_categories = HashMap::new();
        for (prefix, name, count) in BUG_CATEGORIES.iter() {
            bug_categories.insert(format!("{} ({})", name, prefix), *count);
        }

        let mut test_categories = HashMap::new();
        test_categories.insert("unit".to_string(), 180);
        test_categories.insert("integration".to_string(), 120);
        test_categories.insert("concurrency".to_string(), 60);
        test_categories.insert("performance".to_string(), 50);
        test_categories.insert("security".to_string(), 50);
        test_categories.insert("chaos".to_string(), 30);
        test_categories.insert("e2e".to_string(), 20);

        let mut dep_map = HashMap::new();
        for (bug, deps) in &self.bug_deps {
            dep_map.insert(bug.clone(), deps.clone());
        }

        ObservationSpace {
            step: self.step_count,
            max_steps: self.max_steps,
            total_bugs: 75,
            services: SERVICES.iter().map(|s| s.to_string()).collect(),
            bug_categories,
            test_categories,
            bug_dependencies: dep_map,
            editable_file_patterns: vec![
                "services/*/src/*.rs".to_string(),
                "shared/src/*.rs".to_string(),
            ],
        }
    }

    /// Get the action space description for the agent
    pub fn action_space(&self) -> ActionSpace {
        ActionSpace {
            action_types: vec![
                "Edit".to_string(),
                "Create".to_string(),
                "Delete".to_string(),
                "Command".to_string(),
                "TestService".to_string(),
                "TestPattern".to_string(),
                "Read".to_string(),
                "ListDir".to_string(),
                "Grep".to_string(),
            ],
            services: SERVICES.iter().map(|s| s.to_string()).collect(),
            editable_paths: vec![
                "services/*/src/*.rs".to_string(),
                "shared/src/*.rs".to_string(),
                "Cargo.toml".to_string(),
                "services/*/Cargo.toml".to_string(),
                "shared/Cargo.toml".to_string(),
            ],
            max_command_length: 4096,
            max_content_length: 1_000_000,
        }
    }

    /// Validate an action before execution
    pub fn validate_action(&self, action: &ActionType) -> Result<(), String> {
        match action {
            ActionType::Edit { file, content } => {
                // Path traversal check
                if file.contains("..") || file.starts_with('/') {
                    return Err("Path traversal not allowed".to_string());
                }
                // Must not edit test files
                if file.starts_with("tests/") || file.contains("/tests/") {
                    return Err("Cannot edit test files".to_string());
                }
                // Must be a Rust or TOML file
                if !file.ends_with(".rs") && !file.ends_with(".toml") && !file.ends_with(".yml") {
                    return Err("Can only edit .rs, .toml, or .yml files".to_string());
                }
                // Content length check
                if content.len() > 1_000_000 {
                    return Err("Content too large (max 1MB)".to_string());
                }
                Ok(())
            }
            ActionType::Create { file, content } => {
                if file.contains("..") || file.starts_with('/') {
                    return Err("Path traversal not allowed".to_string());
                }
                if file.contains("tests/") {
                    return Err("Cannot create test files".to_string());
                }
                if content.len() > 1_000_000 {
                    return Err("Content too large (max 1MB)".to_string());
                }
                Ok(())
            }
            ActionType::Delete { file } => {
                if file.contains("..") || file.starts_with('/') {
                    return Err("Path traversal not allowed".to_string());
                }
                if file.contains("tests/") {
                    return Err("Cannot delete test files".to_string());
                }
                Ok(())
            }
            ActionType::Command { command } => {
                if command.len() > 4096 {
                    return Err("Command too long (max 4096 chars)".to_string());
                }
                // Allowlist: only safe commands
                let parts: Vec<&str> = command.split_whitespace().collect();
                if parts.is_empty() {
                    return Err("Empty command".to_string());
                }
                const SAFE_COMMANDS: &[&str] = &[
                    "cargo", "docker", "cat", "ls", "grep", "find", "head", "tail", "wc",
                ];
                if !SAFE_COMMANDS.contains(&parts[0]) {
                    return Err(format!("Command not allowed: {}", parts[0]));
                }
                Ok(())
            }
            ActionType::TestService { service } => {
                if !SERVICES.contains(&service.as_str()) {
                    return Err(format!("Unknown service: {}. Valid: {:?}", service, SERVICES));
                }
                Ok(())
            }
            ActionType::TestPattern { pattern } => {
                if pattern.is_empty() {
                    return Err("Test pattern cannot be empty".to_string());
                }
                Ok(())
            }
            ActionType::Read { file } => {
                if file.contains("..") || file.starts_with('/') {
                    return Err("Path traversal not allowed".to_string());
                }
                Ok(())
            }
            ActionType::ListDir { path } => {
                if path.contains("..") || path.starts_with('/') {
                    return Err("Path traversal not allowed".to_string());
                }
                Ok(())
            }
            ActionType::Grep { path, .. } => {
                if let Some(p) = path {
                    if p.contains("..") || p.starts_with('/') {
                        return Err("Path traversal not allowed".to_string());
                    }
                }
                Ok(())
            }
        }
    }

    pub fn reset(&mut self) -> Observation {
        self.start_time = Some(Instant::now());
        self.step_count = 0;
        self.test_results = TestResults::default();
        self.previous_pass_rate = 0.0;
        self.previous_passed_tests.clear();

        // Reset git state
        self.run_command("git", &["checkout", "."]);
        self.run_command("git", &["clean", "-fd"]);

        // Rebuild all services
        self.run_command("cargo", &["build", "--workspace"]);

        // Restart Docker services
        self.run_command("docker", &["compose", "down", "-v"]);
        self.run_command("docker", &["compose", "up", "-d"]);

        // Wait for services
        std::thread::sleep(std::time::Duration::from_secs(30));

        Observation {
            output: ActionOutput { success: true, output: "Environment reset".to_string() },
            test_results: self.test_results.clone(),
            observation_space: self.observation_space(),
            bugs_fixed: Vec::new(),
            bugs_fixable: self.get_fixable_bugs(&HashSet::new()),
        }
    }

    pub fn step(&mut self, action: &ActionType) -> (Observation, f64, bool, bool, Info) {
        self.step_count += 1;

        // Validate action
        if let Err(e) = self.validate_action(action) {
            let obs = Observation {
                output: ActionOutput { success: false, output: format!("Invalid action: {}", e) },
                test_results: self.test_results.clone(),
                observation_space: self.observation_space(),
                bugs_fixed: Vec::new(),
                bugs_fixable: Vec::new(),
            };
            let info = self.make_info();
            return (obs, -0.01, false, self.step_count >= self.max_steps, info);
        }

        // Execute action
        let output = self.execute_action(action);

        // Run tests after code modifications
        let should_run_tests = matches!(action,
            ActionType::Edit { .. } | ActionType::Create { .. } | ActionType::Delete { .. }
        );

        if should_run_tests {
            self.test_results = self.run_tests();
        }

        // For targeted test actions, run specific tests
        match action {
            ActionType::TestService { service } => {
                self.test_results = self.run_service_tests(service);
            }
            ActionType::TestPattern { pattern } => {
                self.test_results = self.run_pattern_tests(pattern);
            }
            _ => {}
        }

        let reward = self.calculate_reward(&self.test_results);
        let done = self.test_results.all_passed;
        let truncated = self.step_count >= self.max_steps;

        // Determine bug status
        let fixed_bugs = self.get_fixed_bugs();
        let fixable_bugs = self.get_fixable_bugs(&fixed_bugs);

        let obs = Observation {
            output,
            test_results: self.test_results.clone(),
            observation_space: self.observation_space(),
            bugs_fixed: fixed_bugs.iter().cloned().collect(),
            bugs_fixable: fixable_bugs,
        };

        let info = self.make_info();

        // Update previous state
        self.previous_pass_rate = self.test_results.pass_rate;
        self.previous_passed_tests = self.test_results.passed_tests.iter().cloned().collect();

        (obs, reward, done, truncated, info)
    }

    pub fn close(&self) {
        self.run_command("docker", &["compose", "down"]);
    }

    fn execute_action(&self, action: &ActionType) -> ActionOutput {
        match action {
            ActionType::Edit { file, content } => {
                let full = std::path::Path::new(&self.work_dir).join(file);
                if let Some(parent) = full.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                let canonical = match full.canonicalize().or_else(|_| {
                    full.parent().and_then(|p| p.canonicalize().ok())
                        .map(|p| p.join(full.file_name().unwrap_or_default()))
                        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "bad path"))
                }) {
                    Ok(p) => p,
                    Err(e) => return ActionOutput { success: false, output: format!("Path error: {}", e) },
                };
                let work_canonical = std::path::Path::new(&self.work_dir).canonicalize().unwrap_or_default();
                if !canonical.starts_with(&work_canonical) {
                    return ActionOutput { success: false, output: "Path escapes work directory".to_string() };
                }
                match std::fs::write(&canonical, content) {
                    Ok(_) => ActionOutput { success: true, output: format!("Edited: {}", file) },
                    Err(e) => ActionOutput { success: false, output: format!("Edit failed: {}", e) },
                }
            }
            ActionType::Create { file, content } => {
                let full = std::path::Path::new(&self.work_dir).join(file);
                if let Some(parent) = full.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                let canonical = match full.canonicalize().or_else(|_| {
                    full.parent().and_then(|p| p.canonicalize().ok())
                        .map(|p| p.join(full.file_name().unwrap_or_default()))
                        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "bad path"))
                }) {
                    Ok(p) => p,
                    Err(e) => return ActionOutput { success: false, output: format!("Path error: {}", e) },
                };
                let work_canonical = std::path::Path::new(&self.work_dir).canonicalize().unwrap_or_default();
                if !canonical.starts_with(&work_canonical) {
                    return ActionOutput { success: false, output: "Path escapes work directory".to_string() };
                }
                match std::fs::write(&canonical, content) {
                    Ok(_) => ActionOutput { success: true, output: format!("Created: {}", file) },
                    Err(e) => ActionOutput { success: false, output: format!("Create failed: {}", e) },
                }
            }
            ActionType::Delete { file } => {
                let full = std::path::Path::new(&self.work_dir).join(file);
                let canonical = match full.canonicalize() {
                    Ok(p) => p,
                    Err(e) => return ActionOutput { success: false, output: format!("Path error: {}", e) },
                };
                let work_canonical = std::path::Path::new(&self.work_dir).canonicalize().unwrap_or_default();
                if !canonical.starts_with(&work_canonical) {
                    return ActionOutput { success: false, output: "Path escapes work directory".to_string() };
                }
                match std::fs::remove_file(&canonical) {
                    Ok(_) => ActionOutput { success: true, output: format!("Deleted: {}", file) },
                    Err(e) => ActionOutput { success: false, output: format!("Delete failed: {}", e) },
                }
            }
            ActionType::Command { command } => {
                let parts: Vec<&str> = command.split_whitespace().collect();
                if parts.is_empty() {
                    return ActionOutput { success: false, output: "Empty command".to_string() };
                }
                let output = self.run_command(parts[0], &parts[1..]);
                ActionOutput {
                    success: output.status.success(),
                    output: format!(
                        "{}{}",
                        String::from_utf8_lossy(&output.stdout),
                        String::from_utf8_lossy(&output.stderr)
                    ),
                }
            }
            ActionType::TestService { service } => {
                ActionOutput { success: true, output: format!("Running tests for {}", service) }
            }
            ActionType::TestPattern { pattern } => {
                ActionOutput { success: true, output: format!("Running tests matching {}", pattern) }
            }
            ActionType::Read { file } => {
                let full = std::path::Path::new(&self.work_dir).join(file);
                let canonical = match full.canonicalize() {
                    Ok(p) => p,
                    Err(e) => return ActionOutput { success: false, output: format!("Path error: {}", e) },
                };
                let work_canonical = std::path::Path::new(&self.work_dir).canonicalize().unwrap_or_default();
                if !canonical.starts_with(&work_canonical) {
                    return ActionOutput { success: false, output: "Path escapes work directory".to_string() };
                }
                match std::fs::read_to_string(&canonical) {
                    Ok(content) => ActionOutput { success: true, output: content },
                    Err(e) => ActionOutput { success: false, output: format!("Read failed: {}", e) },
                }
            }
            ActionType::ListDir { path } => {
                let full_path = format!("{}/{}", self.work_dir, path);
                let output = self.run_command("ls", &["-la", &full_path]);
                ActionOutput {
                    success: output.status.success(),
                    output: String::from_utf8_lossy(&output.stdout).to_string(),
                }
            }
            ActionType::Grep { pattern, path } => {
                let search_path = path.as_deref().unwrap_or(".");
                let full_path = format!("{}/{}", self.work_dir, search_path);
                let output = self.run_command("grep", &["-rn", pattern, &full_path]);
                ActionOutput {
                    success: output.status.success(),
                    output: String::from_utf8_lossy(&output.stdout).to_string(),
                }
            }
        }
    }

    fn run_tests(&mut self) -> TestResults {
        let output = self.run_command("cargo", &["test", "--workspace", "--", "--format=json"]);
        self.parse_test_output(&output)
    }

    /// Run tests for a specific service
    fn run_service_tests(&mut self, service: &str) -> TestResults {
        let package = match service {
            "matching" => "matching-engine",
            "orders" => "orders-service",
            "risk" => "risk-service",
            "positions" => "positions-service",
            "market" => "market-data",
            "portfolio" => "portfolio-service",
            "ledger" => "ledger-service",
            "alerts" => "alerts-service",
            "gateway" => "gateway-service",
            "auth" => "auth-service",
            _ => service,
        };
        let output = self.run_command("cargo", &["test", "-p", package, "--", "--format=json"]);
        self.parse_test_output(&output)
    }

    /// Run tests matching a pattern
    fn run_pattern_tests(&mut self, pattern: &str) -> TestResults {
        let output = self.run_command("cargo", &["test", "--workspace", "--", pattern, "--format=json"]);
        self.parse_test_output(&output)
    }

    fn parse_test_output(&self, output: &Output) -> TestResults {
        let stdout = String::from_utf8_lossy(&output.stdout);
        let mut results = TestResults::default();

        for line in stdout.lines() {
            if let Ok(event) = serde_json::from_str::<TestEvent>(line) {
                match event.event.as_str() {
                    "test" => {
                        results.total += 1;
                        let name = event.name.clone().unwrap_or_default();
                        if event.result == Some("ok".to_string()) {
                            results.passed += 1;
                            results.passed_tests.push(name.clone());

                            // Categorize by service
                            if let Some(service) = self.test_to_service(&name) {
                                let entry = results.service_results
                                    .entry(service)
                                    .or_insert_with(ServiceTestResults::default);
                                entry.total += 1;
                                entry.passed += 1;
                            }
                        } else if event.result == Some("failed".to_string()) {
                            results.failed += 1;
                            results.failed_tests.push(name.clone());

                            if let Some(service) = self.test_to_service(&name) {
                                let entry = results.service_results
                                    .entry(service)
                                    .or_insert_with(ServiceTestResults::default);
                                entry.total += 1;
                                entry.failed += 1;
                            }
                        } else if event.result == Some("ignored".to_string()) {
                            results.skipped += 1;
                        }
                    }
                    _ => {}
                }
            }
        }

        results.pass_rate = if results.total > 0 {
            results.passed as f64 / results.total as f64
        } else {
            0.0
        };
        results.all_passed = results.failed == 0 && results.total > 0;
        results
    }

    /// Map a test name to its service
    fn test_to_service(&self, test_name: &str) -> Option<String> {
        let lower = test_name.to_lowercase();
        if lower.contains("matching") || lower.contains("order_book") || lower.contains("orderbook") {
            Some("matching".to_string())
        } else if lower.contains("order") && !lower.contains("order_book") {
            Some("orders".to_string())
        } else if lower.contains("risk") || lower.contains("margin") || lower.contains("circuit_breaker") {
            Some("risk".to_string())
        } else if lower.contains("position") || lower.contains("fill") || lower.contains("snapshot") {
            Some("positions".to_string())
        } else if lower.contains("market") || lower.contains("quote") || lower.contains("ohlcv") || lower.contains("feed") {
            Some("market".to_string())
        } else if lower.contains("portfolio") || lower.contains("valuation") {
            Some("portfolio".to_string())
        } else if lower.contains("ledger") || lower.contains("journal") || lower.contains("transaction") {
            Some("ledger".to_string())
        } else if lower.contains("alert") || lower.contains("notification") {
            Some("alerts".to_string())
        } else if lower.contains("gateway") || lower.contains("router") || lower.contains("rate_limit") {
            Some("gateway".to_string())
        } else if lower.contains("auth") || lower.contains("jwt") || lower.contains("api_key") {
            Some("auth".to_string())
        } else {
            None
        }
    }

    fn calculate_reward(&mut self, results: &TestResults) -> f64 {
        if results.total == 0 {
            return 0.0;
        }

        let pass_rate = results.pass_rate;
        let mut reward = sparse_reward(pass_rate) * 0.70;

        // Regression penalty
        if pass_rate < self.previous_pass_rate {
            let regression_ratio = self.previous_pass_rate - pass_rate;
            reward += -0.15 * regression_ratio;
        }

        // Service isolation bonus (10%)
        let services_fully_passing = results.service_results.values()
            .filter(|sr| sr.failed == 0 && sr.total > 0)
            .count();
        reward += 0.02 * services_fully_passing as f64;

        // Concurrency tests bonus (5%)
        let concurrency_failing = results.failed_tests.iter()
            .any(|t| {
                let lower = t.to_lowercase();
                lower.contains("concurrency") || lower.contains("race") ||
                lower.contains("deadlock") || lower.contains("atomic")
            });
        if !concurrency_failing && results.total > 0 {
            reward += 0.05;
        }

        // Financial tests bonus (5%)
        let financial_failing = results.failed_tests.iter()
            .any(|t| {
                let lower = t.to_lowercase();
                lower.contains("precision") || lower.contains("decimal") ||
                lower.contains("overflow") || lower.contains("rounding") ||
                lower.contains("pnl")
            });
        if !financial_failing && results.total > 0 {
            reward += 0.05;
        }

        // Efficiency bonus at completion (5%)
        if results.all_passed {
            let efficiency = 1.0 - (self.step_count as f64 / self.max_steps as f64);
            reward += 0.03 * efficiency.max(0.0);
        }

        reward.clamp(-1.0, 1.0)
    }

    /// Determine which bugs are currently fixed based on passing tests
    fn get_fixed_bugs(&self) -> HashSet<String> {
        let passed: HashSet<String> = self.test_results.passed_tests.iter().cloned().collect();
        let mut fixed = HashSet::new();

        for (bug_id, required_tests) in &self.bug_test_map {
            if required_tests.iter().all(|t| passed.contains(t)) {
                fixed.insert(bug_id.clone());
            }
        }

        fixed
    }

    /// Get bugs whose dependencies are all satisfied
    fn get_fixable_bugs(&self, fixed: &HashSet<String>) -> Vec<String> {
        let all_bugs: HashSet<String> = self.bug_test_map.keys().cloned().collect();
        let mut fixable = Vec::new();

        for bug_id in &all_bugs {
            if fixed.contains(bug_id) {
                continue;
            }
            let deps = self.bug_deps.get(bug_id).cloned().unwrap_or_default();
            if deps.iter().all(|d| fixed.contains(d)) {
                fixable.push(bug_id.clone());
            }
        }

        fixable.sort();
        fixable
    }

    fn make_info(&self) -> Info {
        let fixed = self.get_fixed_bugs();
        Info {
            work_dir: self.work_dir.clone(),
            elapsed_time: self.start_time.map(|t| t.elapsed().as_secs_f64()).unwrap_or(0.0),
            step: self.step_count,
            max_steps: self.max_steps,
            total_bugs: 75,
            bugs_fixed: fixed.len(),
            services: SERVICES.iter().map(|s| s.to_string()).collect(),
            service_results: self.test_results.service_results.clone(),
            bugs_with_dependencies: self.bug_deps.len(),
        }
    }

    fn run_command(&self, cmd: &str, args: &[&str]) -> Output {
        Command::new(cmd)
            .args(args)
            .current_dir(&self.work_dir)
            .output()
            .expect("Failed to execute command")
    }
}

fn sparse_reward(pass_rate: f64) -> f64 {
    const THRESHOLDS: [f64; 8] = [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0];
    const REWARDS: [f64; 8] = [0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0];

    for (i, &threshold) in THRESHOLDS.iter().rev().enumerate() {
        if pass_rate >= threshold {
            return REWARDS[REWARDS.len() - 1 - i];
        }
    }
    0.0
}

#[derive(Serialize, Deserialize)]
struct TestEvent {
    #[serde(rename = "type")]
    event: String,
    name: Option<String>,
    result: Option<String>,
}

#[derive(Serialize)]
pub struct Observation {
    pub output: ActionOutput,
    pub test_results: TestResults,
    pub observation_space: ObservationSpace,
    pub bugs_fixed: Vec<String>,
    pub bugs_fixable: Vec<String>,
}

#[derive(Serialize)]
pub struct ActionOutput {
    pub success: bool,
    pub output: String,
}

#[derive(Serialize)]
pub struct Info {
    pub work_dir: String,
    pub elapsed_time: f64,
    pub step: usize,
    pub max_steps: usize,
    pub total_bugs: usize,
    pub bugs_fixed: usize,
    pub services: Vec<String>,
    pub service_results: HashMap<String, ServiceTestResults>,
    pub bugs_with_dependencies: usize,
}

fn main() {
    let mut env = Environment::new(".", 200);

    println!("QuantumCore RL Environment");
    println!("=========================");

    // Print observation and action spaces
    let obs_space = env.observation_space();
    println!("\nObservation Space:");
    println!("  Total bugs: {}", obs_space.total_bugs);
    println!("  Services: {:?}", obs_space.services);
    println!("  Bug categories: {:?}", obs_space.bug_categories);
    println!("  Dependencies: {} bugs have prerequisites", obs_space.bug_dependencies.len());

    let action_space = env.action_space();
    println!("\nAction Space:");
    println!("  Action types: {:?}", action_space.action_types);
    println!("  Services: {:?}", action_space.services);

    // Print dependency stats
    let deps = bug_dependencies();
    let max_depth = deps.keys()
        .map(|k| chain_depth(k, &deps, &mut HashSet::new()))
        .max()
        .unwrap_or(0);
    let diamonds = deps.values().filter(|v| v.len() > 1).count();

    println!("\nDependency Graph:");
    println!("  Bugs with dependencies: {}", deps.len());
    println!("  Max chain depth: {}", max_depth);
    println!("  Diamond patterns: {}", diamonds);

    println!("\nEnvironment ready. Run tests with: cargo test --workspace");
}

fn chain_depth(bug: &str, deps: &HashMap<String, Vec<String>>, visited: &mut HashSet<String>) -> usize {
    if visited.contains(bug) {
        return 0;
    }
    visited.insert(bug.to_string());
    match deps.get(bug) {
        Some(prerequisites) if !prerequisites.is_empty() => {
            1 + prerequisites.iter()
                .map(|d| chain_depth(d, deps, visited))
                .max()
                .unwrap_or(0)
        }
        _ => 0,
    }
}
