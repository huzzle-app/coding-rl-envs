use std::collections::HashMap;
use std::process::{Command, Output};
use std::time::Instant;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
pub fn bug_test_mapping() -> HashMap<&'static str, Vec<&'static str>> {
    let mut m = HashMap::new();

    // L: Setup / Configuration (4 bugs)
    m.insert("L1", vec![
        "test_no_nested_runtime_creation",
        "test_async_pool_creation",
    ]);
    m.insert("L2", vec![
        "test_db_pool_configuration",
        "test_db_pool_timeout_settings",
    ]);
    m.insert("L3", vec![
        "test_config_invalid_port_returns_error",
        "test_config_missing_env_returns_error",
        "test_config_invalid_upload_size_returns_error",
    ]);
    m.insert("L4", vec![
        "test_graceful_shutdown_signal_handler",
        "test_shutdown_completes_inflight_requests",
    ]);

    // A: Ownership / Borrowing (5 bugs)
    m.insert("A1", vec![
        "test_upload_file_no_use_after_move",
        "test_upload_preserves_metadata_size",
    ]);
    m.insert("A2", vec![
        "test_get_changes_returns_owned_values",
        "test_changes_since_does_not_hold_lock",
    ]);
    m.insert("A3", vec![
        "test_versioning_create_no_double_borrow",
        "test_versioning_prune_no_double_borrow",
    ]);
    m.insert("A4", vec![
        "test_list_files_no_use_after_move",
        "test_list_files_skips_tmp_before_move",
    ]);
    m.insert("A5", vec![
        "test_extract_info_no_partial_move",
        "test_split_metadata_no_partial_move",
    ]);

    // B: Lifetime Issues (4 bugs)
    m.insert("B1", vec![
        "test_cache_get_with_fallback_returns_owned",
        "test_cache_config_value_returns_owned",
    ]);
    m.insert("B2", vec![
        "test_file_repo_lifetime_annotation",
        "test_file_repo_query_compiles",
    ]);
    m.insert("B3", vec![
        "test_chunk_no_self_referential_struct",
        "test_chunk_can_be_moved",
    ]);
    m.insert("B4", vec![
        "test_create_share_owned_across_await",
        "test_share_no_dangling_reference",
    ]);

    // C: Concurrency / Async (5 bugs)
    m.insert("C1", vec![
        "test_no_deadlock_consistent_lock_order",
        "test_lock_file_for_user_completes",
        "test_lock_user_files_completes",
    ]);
    m.insert("C2", vec![
        "test_save_to_disk_uses_async_io",
        "test_large_file_no_runtime_block",
    ]);
    m.insert("C3", vec![
        "test_record_change_atomic_version",
        "test_concurrent_record_no_duplicate_version",
    ]);
    m.insert("C4", vec![
        "test_upload_multipart_future_is_send",
        "test_upload_uses_arc_mutex_not_rc",
    ]);
    m.insert("C5", vec![
        "test_notification_send_with_receiver_alive",
        "test_notification_subscribe_before_send",
    ]);

    // D: Error Handling (4 bugs)
    m.insert("D1", vec![
        "test_get_file_empty_chunks_returns_error",
        "test_get_file_no_unwrap_on_none",
    ]);
    m.insert("D2", vec![
        "test_get_file_handler_all_match_arms",
        "test_get_file_handles_db_error",
    ]);
    m.insert("D3", vec![
        "test_user_repo_error_conversion",
        "test_user_repo_incompatible_error_handled",
    ]);
    m.insert("D4", vec![
        "test_temp_file_drop_no_panic",
        "test_temp_dir_drop_no_panic",
        "test_temp_file_missing_no_panic",
    ]);

    // E: Memory / Resource (3 bugs)
    m.insert("E1", vec![
        "test_folder_no_rc_cycle_leak",
        "test_folder_uses_weak_parent",
    ]);
    m.insert("E2", vec![
        "test_chunker_file_handle_closed_on_error",
        "test_chunker_no_leaked_handles",
    ]);
    m.insert("E3", vec![
        "test_sync_bounded_channel",
        "test_sync_backpressure",
    ]);

    // F: Security (4 bugs)
    m.insert("F1", vec![
        "test_path_traversal_rejected",
        "test_path_traversal_encoded_rejected",
        "test_path_within_base_dir_allowed",
    ]);
    m.insert("F2", vec![
        "test_search_uses_parameterized_query",
        "test_sql_injection_query_escaped",
        "test_sql_injection_sort_column_validated",
    ]);
    m.insert("F3", vec![
        "test_api_key_constant_time_comparison",
        "test_signature_constant_time_comparison",
        "test_hash_constant_time_comparison",
    ]);
    m.insert("F4", vec![
        "test_mmap_keeps_file_handle_alive",
        "test_mmap_bounds_checked",
        "test_mmap_null_ptr_check",
    ]);

    m
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
pub fn bug_categories() -> HashMap<&'static str, Vec<&'static str>> {
    let mut m = HashMap::new();
    m.insert("setup",        vec!["L1", "L2", "L3", "L4"]);
    m.insert("ownership",    vec!["A1", "A2", "A3", "A4", "A5"]);
    m.insert("lifetime",     vec!["B1", "B2", "B3", "B4"]);
    m.insert("concurrency",  vec!["C1", "C2", "C3", "C4", "C5"]);
    m.insert("error",        vec!["D1", "D2", "D3", "D4"]);
    m.insert("memory",       vec!["E1", "E2", "E3"]);
    m.insert("security",     vec!["F1", "F2", "F3", "F4"]);
    m
}

// ---------------------------------------------------------------------------

//
// Dependency chains include:
//   Depth-3: L1 -> L2 -> L3 (setup must be solved in order)
//   Depth-3: A1 -> C2 -> D1 (use-after-move blocks async-io blocks unwrap fix)
//   Diamond: C1 depends on BOTH A3 AND E1 (lock ordering needs borrow fix + Weak refs)
//   Cross-category links span setup, ownership, lifetime, concurrency, security
// ---------------------------------------------------------------------------
pub fn bug_dependencies() -> HashMap<&'static str, Vec<&'static str>> {
    let mut m = HashMap::new();

    // --- Setup chain (depth 3): L3 -> L2 -> L1 ---
    // Pool config (L2) requires runtime fix (L1) to even initialize
    m.insert("L2", vec!["L1"]);
    // Env parsing (L3) only testable once pool config works (L2)
    m.insert("L3", vec!["L2"]);
    // Graceful shutdown (L4) depends on correct config loading (L3)
    m.insert("L4", vec!["L3"]);

    // --- Ownership -> Concurrency -> Error chain (depth 3): D1 -> C2 -> A1 ---
    // Blocking async I/O (C2) depends on use-after-move fix (A1) since
    // upload_file calls save_to_disk with the data that was moved
    m.insert("C2", vec!["A1"]);
    // Unwrap on None (D1) only reachable after blocking I/O fixed (C2)
    // because get_file never returns chunks until upload works
    m.insert("D1", vec!["C2"]);

    // --- Diamond: C1 depends on BOTH A3 AND E1 ---
    // Deadlock from lock ordering (C1) requires:
    //   - A3 (double mutable borrow in versioning) because lock_file_for_user
    //     calls versioning internally
    //   - E1 (Rc cycle in Folder) because folder locks participate in ordering
    m.insert("C1", vec!["A3", "E1"]);

    // --- Cross-category links ---
    // Borrowed value in sync (A2) surfaces after race condition (C3) is fixed
    // because the borrow checker error is masked by the earlier runtime panic
    m.insert("A2", vec!["C3"]);

    // Lifetime in cache (B1) depends on env config (L3) because cache
    // initialization reads config values that panic without L3 fix
    m.insert("B1", vec!["L3"]);

    // Future not Send (C4) depends on lifetime fix (B4) because the
    // handler shares a lifetime-bounded reference across the await point
    m.insert("C4", vec!["B4"]);

    // SQL injection (F2) depends on partial move fix (A5) because the
    // search repository uses FileMetadata fields that trigger partial move
    m.insert("F2", vec!["A5"]);

    // Path traversal (F1) depends on error handling match arms (D2)
    // because download_file goes through get_file handler first
    m.insert("F1", vec!["D2"]);

    // Unbounded channel (E3) depends on channel receiver fix (C5)
    // because both share the notification/sync event pipeline
    m.insert("E3", vec!["C5"]);

    m
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
pub fn bug_correlations() -> HashMap<&'static str, Vec<&'static str>> {
    let mut m = HashMap::new();
    m.insert("L1", vec!["L2", "L3"]);
    m.insert("A1", vec!["C2", "D1"]);
    m.insert("A3", vec!["C1"]);
    m.insert("B1", vec!["B4"]);
    m.insert("C3", vec!["A2"]);
    m.insert("E1", vec!["C1"]);
    m.insert("F1", vec!["F2"]);
    m
}

// ---------------------------------------------------------------------------
// File-to-test mapping for targeted test runs
// ---------------------------------------------------------------------------
pub fn file_test_map() -> HashMap<&'static str, Vec<&'static str>> {
    let mut m = HashMap::new();
    m.insert("src/main.rs",                   vec!["tests/setup_tests.rs"]);
    m.insert("src/config/",                   vec!["tests/setup_tests.rs"]);
    m.insert("src/services/storage.rs",       vec!["tests/storage_tests.rs", "tests/concurrency_tests.rs"]);
    m.insert("src/services/sync.rs",          vec!["tests/concurrency_tests.rs", "tests/storage_tests.rs"]);
    m.insert("src/services/versioning.rs",    vec!["tests/storage_tests.rs"]);
    m.insert("src/services/lock_manager.rs",  vec!["tests/lock_tests.rs"]);
    m.insert("src/services/cache.rs",         vec!["tests/cache_tests.rs"]);
    m.insert("src/services/notification.rs",  vec!["tests/concurrency_tests.rs"]);
    m.insert("src/handlers/files.rs",         vec!["tests/storage_tests.rs", "tests/security_tests.rs"]);
    m.insert("src/handlers/shares.rs",        vec!["tests/storage_tests.rs"]);
    m.insert("src/handlers/upload.rs",        vec!["tests/concurrency_tests.rs"]);
    m.insert("src/models/file.rs",            vec!["tests/storage_tests.rs"]);
    m.insert("src/models/folder.rs",          vec!["tests/storage_tests.rs"]);
    m.insert("src/models/temp_file.rs",       vec!["tests/storage_tests.rs"]);
    m.insert("src/middleware/auth.rs",         vec!["tests/security_tests.rs"]);
    m.insert("src/repository/search.rs",      vec!["tests/security_tests.rs"]);
    m.insert("src/storage/mmap.rs",           vec!["tests/security_tests.rs"]);
    m
}

// ---------------------------------------------------------------------------
// Test category weights
// ---------------------------------------------------------------------------
pub fn category_weights() -> HashMap<&'static str, f64> {
    let mut m = HashMap::new();
    m.insert("unit",        1.0);
    m.insert("integration", 1.5);
    m.insert("concurrency", 2.5);
    m.insert("security",    2.0);
    m
}

// ---------------------------------------------------------------------------
// Observation and action spaces (Gym-style description)
// ---------------------------------------------------------------------------

#[derive(Serialize)]
pub struct SpaceDescription {
    pub r#type: String,
    pub details: HashMap<String, String>,
}

pub fn observation_space() -> HashMap<&'static str, SpaceDescription> {
    let mut m = HashMap::new();
    m.insert("test_results", SpaceDescription {
        r#type: "Dict".to_string(),
        details: [
            ("keys".into(), "total, passed, failed, pass_rate, passed_tests, failed_tests".into()),
        ].into_iter().collect(),
    });
    m.insert("reward", SpaceDescription {
        r#type: "Box".to_string(),
        details: [
            ("low".into(), "0.0".into()),
            ("high".into(), "1.0".into()),
            ("shape".into(), "(1,)".into()),
        ].into_iter().collect(),
    });
    m.insert("step_count", SpaceDescription {
        r#type: "Discrete".to_string(),
        details: [("n".into(), "101".into())].into_iter().collect(),
    });
    m.insert("action_result", SpaceDescription {
        r#type: "Dict".to_string(),
        details: HashMap::new(),
    });
    m.insert("bugs_remaining", SpaceDescription {
        r#type: "MultiBinary".to_string(),
        details: [("n".into(), "25".into())].into_iter().collect(),
    });
    m
}

pub fn action_space() -> HashMap<&'static str, SpaceDescription> {
    let mut m = HashMap::new();
    m.insert("type", SpaceDescription {
        r#type: "Discrete".to_string(),
        details: [("values".into(), "edit, read, run_command".into())].into_iter().collect(),
    });
    m.insert("file", SpaceDescription {
        r#type: "Text".to_string(),
        details: [("max_length".into(), "256".into())].into_iter().collect(),
    });
    m.insert("content", SpaceDescription {
        r#type: "Text".to_string(),
        details: [("max_length".into(), "100000".into())].into_iter().collect(),
    });
    m.insert("command", SpaceDescription {
        r#type: "Text".to_string(),
        details: [("max_length".into(), "1000".into())].into_iter().collect(),
    });
    m
}

// ---------------------------------------------------------------------------
// Action validation
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
pub struct ValidationError {
    pub success: bool,
    pub error: String,
}

/// Validate an action before execution.
/// Returns None if valid, or Some(error) if invalid.
pub fn validate_action(action: &str) -> Option<ValidationError> {
    if action.starts_with("EDIT:") {
        let spec = &action[5..];
        if spec.len() > 100_000 {
            return Some(ValidationError {
                success: false,
                error: "Edit content exceeds 100K character limit".to_string(),
            });
        }
        // Check for path traversal in file path portion
        if let Some(file_part) = spec.split('\n').next() {
            if file_part.contains("..") || file_part.starts_with('/') {
                return Some(ValidationError {
                    success: false,
                    error: "Path traversal not allowed in edit target".to_string(),
                });
            }
            if file_part.starts_with("tests/") || file_part.contains("/tests/") {
                return Some(ValidationError {
                    success: false,
                    error: "Editing test files is not allowed".to_string(),
                });
            }
            if file_part.len() > 256 {
                return Some(ValidationError {
                    success: false,
                    error: "File path exceeds 256 characters".to_string(),
                });
            }
        }
        None
    } else if action.starts_with("RUN:") {
        let cmd = &action[4..];
        if cmd.len() > 1000 {
            return Some(ValidationError {
                success: false,
                error: "Command exceeds 1000 character limit".to_string(),
            });
        }
        if cmd.trim().is_empty() {
            return Some(ValidationError {
                success: false,
                error: "Empty command".to_string(),
            });
        }
        None
    } else if action.starts_with("READ:") {
        let path = &action[5..];
        if path.contains("..") || path.starts_with('/') {
            return Some(ValidationError {
                success: false,
                error: "Path traversal not allowed".to_string(),
            });
        }
        if path.len() > 256 {
            return Some(ValidationError {
                success: false,
                error: "File path exceeds 256 characters".to_string(),
            });
        }
        None
    } else {
        Some(ValidationError {
            success: false,
            error: format!("Unknown action type. Expected EDIT:, RUN:, or READ:"),
        })
    }
}

// ---------------------------------------------------------------------------
// Core environment
// ---------------------------------------------------------------------------

/// VaultFS RL Environment wrapper
pub struct Environment {
    work_dir: String,
    start_time: Option<Instant>,
    test_results: TestResults,
    previous_pass_rate: f64,
    step_count: usize,
    max_steps: usize,
    previous_results: Vec<String>,  // previously passing test names
}

#[derive(Default, Clone, Serialize, Deserialize)]
pub struct TestResults {
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
    pub skipped: usize,
    pub all_passed: bool,
    pub failed_tests: Vec<String>,
    pub passed_tests: Vec<String>,
}

impl Environment {
    pub fn new(work_dir: &str) -> Self {
        Self {
            work_dir: work_dir.to_string(),
            start_time: None,
            test_results: TestResults::default(),
            previous_pass_rate: 0.0,
            step_count: 0,
            max_steps: 100,
            previous_results: Vec::new(),
        }
    }

    pub fn reset(&mut self) -> &mut Self {
        self.start_time = Some(Instant::now());
        self.test_results = TestResults::default();
        self.step_count = 0;
        self.previous_pass_rate = 0.0;
        self.previous_results = Vec::new();

        // Reset git state
        self.run_command("git", &["checkout", "."]);
        self.run_command("git", &["clean", "-fd"]);

        // Rebuild project
        self.run_command("cargo", &["build"]);

        self
    }

    pub fn step(&mut self, action: &str) -> (Observation, f64, bool, Info) {
        self.step_count += 1;

        // Validate the action first
        if let Some(err) = validate_action(action) {
            return (
                Observation {
                    output: ActionOutput {
                        success: false,
                        output: err.error,
                    },
                    test_results: self.test_results.clone(),
                },
                0.0,
                false,
                self.make_info(),
            );
        }

        // Execute the action
        let output = self.execute_action(action);

        // Run targeted tests if this was an edit, full tests otherwise
        let results = if action.starts_with("EDIT:") {
            let file_part = action[5..].split('\n').next().unwrap_or("");
            let targeted = self.run_targeted_tests(file_part);
            if targeted.total > 0 {
                targeted
            } else {
                self.run_tests()
            }
        } else {
            self.run_tests()
        };

        // Calculate reward with bug-dependency-aware scoring
        let reward = self.calculate_reward(&results);

        // Check done conditions
        let done = results.all_passed || self.step_count >= self.max_steps;
        let truncated = self.step_count >= self.max_steps && !results.all_passed;

        // Store current passing tests for regression detection
        self.previous_results = results.passed_tests.clone();

        (
            Observation { output, test_results: results.clone() },
            reward,
            done,
            Info {
                work_dir: self.work_dir.clone(),
                elapsed_time: self.start_time.map(|t| t.elapsed().as_secs_f64()).unwrap_or(0.0),
                total_bugs: 25,
                step_count: self.step_count,
                max_steps: self.max_steps,
                truncated,
                bugs_fixed: self.count_fixed_bugs(&results),
            },
        )
    }

    pub fn close(&self) {
        self.run_command("docker", &["compose", "down"]);
    }

    /// Run only tests relevant to a changed file for fast feedback
    fn run_targeted_tests(&mut self, changed_file: &str) -> TestResults {
        let ftm = file_test_map();
        let mut test_files: Vec<&str> = Vec::new();

        for (prefix, tests) in &ftm {
            if changed_file.starts_with(prefix) || changed_file == *prefix {
                test_files.extend(tests.iter());
            }
        }

        if test_files.is_empty() {
            return TestResults::default();
        }

        // Deduplicate
        test_files.sort();
        test_files.dedup();

        // Build cargo test command with specific test files
        let mut args = vec!["test"];
        for tf in &test_files {
            args.push("--test");
            // Extract test name from path (e.g., "tests/storage_tests.rs" -> "storage_tests")
            let test_name = tf.trim_start_matches("tests/").trim_end_matches(".rs");
            args.push(test_name);
        }
        args.push("--");
        args.push("--format=json");

        let output = self.run_command("cargo", &args);
        self.parse_test_output(&output)
    }

    /// Count how many bugs are fully fixed based on test results
    fn count_fixed_bugs(&self, results: &TestResults) -> usize {
        let mapping = bug_test_mapping();
        let deps = bug_dependencies();
        let passing: std::collections::HashSet<&str> =
            results.passed_tests.iter().map(|s| s.as_str()).collect();

        let mut fixed_count = 0;
        for (bug_id, test_names) in &mapping {
            // Check if all tests for this bug pass
            let all_pass = test_names.iter().all(|t| {
                passing.iter().any(|p| p.contains(t))
            });
            if !all_pass {
                continue;
            }
            // Check dependencies
            let bug_deps = deps.get(bug_id).cloned().unwrap_or_default();
            let deps_met = bug_deps.iter().all(|dep| {
                if let Some(dep_tests) = mapping.get(dep) {
                    dep_tests.iter().all(|t| passing.iter().any(|p| p.contains(t)))
                } else {
                    false
                }
            });
            if deps_met {
                fixed_count += 1;
            }
        }
        fixed_count
    }

    fn execute_action(&self, action: &str) -> ActionOutput {
        if action.starts_with("EDIT:") {
            self.handle_edit(&action[5..])
        } else if action.starts_with("RUN:") {
            self.handle_run(&action[4..])
        } else if action.starts_with("READ:") {
            self.handle_read(&action[5..])
        } else {
            ActionOutput {
                success: false,
                output: "Unknown action type".to_string(),
            }
        }
    }

    fn handle_edit(&self, edit_spec: &str) -> ActionOutput {
        // Parse: first line is file path, rest is content
        let mut lines = edit_spec.splitn(2, '\n');
        let file_part = match lines.next() {
            Some(f) => f.trim(),
            None => return ActionOutput { success: false, output: "Empty edit spec".to_string() },
        };
        let content = lines.next().unwrap_or("");

        // Path safety: reject absolute paths and canonicalize
        if file_part.starts_with('/') {
            return ActionOutput { success: false, output: "Absolute paths not allowed".to_string() };
        }
        let full_path = std::path::Path::new(&self.work_dir).join(file_part);
        let canonical = match full_path.canonicalize().or_else(|_| {
            // File may not exist yet; canonicalize parent
            if let Some(parent) = full_path.parent() {
                std::fs::create_dir_all(parent).ok();
                parent.canonicalize().map(|p| p.join(full_path.file_name().unwrap_or_default()))
            } else {
                Err(std::io::Error::new(std::io::ErrorKind::NotFound, "bad path"))
            }
        }) {
            Ok(p) => p,
            Err(e) => return ActionOutput { success: false, output: format!("Path error: {}", e) },
        };
        let work_canonical = match std::path::Path::new(&self.work_dir).canonicalize() {
            Ok(p) => p,
            Err(e) => return ActionOutput { success: false, output: format!("Work dir error: {}", e) },
        };
        if !canonical.starts_with(&work_canonical) {
            return ActionOutput { success: false, output: "Path escapes work directory".to_string() };
        }

        match std::fs::write(&canonical, content) {
            Ok(_) => ActionOutput { success: true, output: format!("Edit applied: {}", file_part) },
            Err(e) => ActionOutput { success: false, output: format!("Write failed: {}", e) },
        }
    }

    fn handle_read(&self, file_path: &str) -> ActionOutput {
        if file_path.starts_with('/') {
            return ActionOutput { success: false, output: "Absolute paths not allowed".to_string() };
        }
        let full_path = std::path::Path::new(&self.work_dir).join(file_path);
        let canonical = match full_path.canonicalize() {
            Ok(p) => p,
            Err(e) => return ActionOutput { success: false, output: format!("Path error: {}", e) },
        };
        let work_canonical = match std::path::Path::new(&self.work_dir).canonicalize() {
            Ok(p) => p,
            Err(e) => return ActionOutput { success: false, output: format!("Work dir error: {}", e) },
        };
        if !canonical.starts_with(&work_canonical) {
            return ActionOutput { success: false, output: "Path escapes work directory".to_string() };
        }
        match std::fs::read_to_string(&canonical) {
            Ok(content) => ActionOutput { success: true, output: content },
            Err(e) => ActionOutput { success: false, output: format!("Failed to read {}: {}", file_path, e) },
        }
    }

    fn handle_run(&self, command: &str) -> ActionOutput {
        let parts: Vec<&str> = command.split_whitespace().collect();
        if parts.is_empty() {
            return ActionOutput {
                success: false,
                output: "Empty command".to_string(),
            };
        }

        const SAFE_COMMANDS: &[&str] = &[
            "cargo", "docker", "cat", "ls", "grep", "find", "head", "tail", "wc",
        ];
        if !SAFE_COMMANDS.contains(&parts[0]) {
            return ActionOutput {
                success: false,
                output: format!("Command not allowed: {}", parts[0]),
            };
        }

        let output = self.run_command(parts[0], &parts[1..]);
        ActionOutput {
            success: output.status.success(),
            output: String::from_utf8_lossy(&output.stdout).to_string(),
        }
    }

    fn run_tests(&mut self) -> TestResults {
        let output = self.run_command("cargo", &["test", "--", "--format=json"]);
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
                        if event.result == Some("ok".to_string()) {
                            results.passed += 1;
                            if let Some(name) = &event.name {
                                results.passed_tests.push(name.clone());
                            }
                        } else if event.result == Some("failed".to_string()) {
                            results.failed += 1;
                            if let Some(name) = &event.name {
                                results.failed_tests.push(name.clone());
                            }
                        } else if event.result == Some("ignored".to_string()) {
                            results.skipped += 1;
                        }
                    }
                    _ => {}
                }
            }
        }

        results.all_passed = results.failed == 0 && results.total > 0;
        results
    }

    fn calculate_reward(&mut self, results: &TestResults) -> f64 {
        if results.total == 0 {
            return 0.0;
        }

        let pass_rate = results.passed as f64 / results.total as f64;

        // Component 1: Sparse test pass score (40%)
        let test_pass_score = sparse_reward(pass_rate) * 0.40;

        // Component 2: Category completion bonus (25%)
        let completion_bonus = self.calculate_category_bonus(results) * 0.25;

        // Component 3: Bug fix bonus with dependency awareness (25%)
        let bug_bonus = self.calculate_bug_bonus(results) * 0.25;

        // Component 4: Efficiency bonus (5%)
        let remaining_budget = 1.0 - (self.step_count as f64 / self.max_steps as f64);
        let efficiency_bonus = if pass_rate >= 1.0 {
            remaining_budget.max(0.0) * 0.05
        } else {
            0.0
        };

        // Component 5: Regression penalty (up to -15%)
        let regression_penalty = self.calculate_regression_penalty(results);

        // Concurrency bonus
        let concurrency_passing = !results.failed_tests.iter()
            .any(|t| t.contains("deadlock") || t.contains("race") || t.contains("concurrent"));
        let concurrency_bonus = if concurrency_passing { 0.03 } else { 0.0 };

        // Security bonus
        let security_passing = !results.failed_tests.iter()
            .any(|t| t.contains("injection") || t.contains("traversal") || t.contains("timing"));
        let security_bonus = if security_passing { 0.02 } else { 0.0 };

        let total = test_pass_score + completion_bonus + bug_bonus
            + efficiency_bonus + concurrency_bonus + security_bonus
            - regression_penalty;

        self.previous_pass_rate = pass_rate;
        total.clamp(0.0, 1.0)
    }

    /// Category bonus: only complete categories count
    fn calculate_category_bonus(&self, results: &TestResults) -> f64 {
        let cats = bug_categories();
        let mapping = bug_test_mapping();
        let passing: std::collections::HashSet<&str> =
            results.passed_tests.iter().map(|s| s.as_str()).collect();

        let mut complete = 0usize;
        for (_cat_name, bug_ids) in &cats {
            let all_pass = bug_ids.iter().all(|bug_id| {
                if let Some(tests) = mapping.get(bug_id) {
                    tests.iter().all(|t| passing.iter().any(|p| p.contains(t)))
                } else {
                    false
                }
            });
            if all_pass {
                complete += 1;
            }
        }

        if complete < 2 {
            return 0.0;
        }
        ((complete - 1) as f64 * 0.20).min(1.0)
    }

    /
    fn calculate_bug_bonus(&self, results: &TestResults) -> f64 {
        let mapping = bug_test_mapping();
        let deps = bug_dependencies();
        let passing: std::collections::HashSet<&str> =
            results.passed_tests.iter().map(|s| s.as_str()).collect();

        let mut total_score = 0.0;
        let total_bugs = mapping.len() as f64;

        for (bug_id, test_names) in &mapping {
            let pass_count = test_names.iter().filter(|t| {
                passing.iter().any(|p| p.contains(*t))
            }).count();

            let mut score = pass_count as f64 / test_names.len() as f64;

            // Apply dependency penalty: half credit if deps not met
            let bug_deps = deps.get(bug_id).cloned().unwrap_or_default();
            if !bug_deps.is_empty() {
                let all_deps_met = bug_deps.iter().all(|dep| {
                    if let Some(dep_tests) = mapping.get(dep) {
                        dep_tests.iter().all(|t| passing.iter().any(|p| p.contains(t)))
                    } else {
                        false
                    }
                });
                if !all_deps_met {
                    score *= 0.5;
                }
            }

            total_score += score;
        }

        if total_bugs == 0.0 { 0.0 } else { total_score / total_bugs }
    }

    /// Regression penalty for tests that were passing but now fail
    fn calculate_regression_penalty(&self, results: &TestResults) -> f64 {
        if self.previous_results.is_empty() {
            return 0.0;
        }

        let current_passing: std::collections::HashSet<&str> =
            results.passed_tests.iter().map(|s| s.as_str()).collect();

        let regressions = self.previous_results.iter()
            .filter(|prev| !current_passing.contains(prev.as_str()))
            .count();

        let penalty_rate = regressions as f64 / self.previous_results.len() as f64;
        (penalty_rate * 0.15).min(0.15)
    }

    fn make_info(&self) -> Info {
        Info {
            work_dir: self.work_dir.clone(),
            elapsed_time: self.start_time.map(|t| t.elapsed().as_secs_f64()).unwrap_or(0.0),
            total_bugs: 25,
            step_count: self.step_count,
            max_steps: self.max_steps,
            truncated: false,
            bugs_fixed: 0,
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
    const THRESHOLDS: [f64; 4] = [0.50, 0.75, 0.90, 1.0];
    const REWARDS: [f64; 4] = [0.15, 0.35, 0.65, 1.0];

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
    pub total_bugs: usize,
    pub step_count: usize,
    pub max_steps: usize,
    pub truncated: bool,
    pub bugs_fixed: usize,
}

fn main() {
    let mut env = Environment::new(".");
    env.reset();

    println!("VaultFS environment initialized");
    println!("Total bugs: 25");
    println!("Bug categories: {:?}", bug_categories().keys().collect::<Vec<_>>());
    println!("Bug dependencies: {} entries", bug_dependencies().len());
    println!("Observation space keys: {:?}", observation_space().keys().collect::<Vec<_>>());
    println!("Action space keys: {:?}", action_space().keys().collect::<Vec<_>>());
    println!("\nRunning initial tests...");

    let results = env.run_tests();
    println!("\nTest Results:");
    println!("Total: {}, Passed: {}, Failed: {}", results.total, results.passed, results.failed);

    let reward = env.calculate_reward(&results);
    println!("Initial Reward: {:.4}", reward);
    println!("Bugs fixed: {}", env.count_fixed_bugs(&results));
}
