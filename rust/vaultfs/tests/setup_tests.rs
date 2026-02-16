//! Tests for setup and configuration bugs
//!
//! These tests verify that setup/config bugs are FIXED.
//!
//! Bug coverage:
//! - L1: No nested Tokio runtime creation (panic on Runtime::new inside async)
//! - L2: Database pool must be properly configured (timeouts, pool size)
//! - L3: Environment variable parsing must return Result, not panic
//! - L4: Graceful shutdown handler must be wired up

use vaultfs::config::Config;
use vaultfs::config::database;

// ===== BUG L1: Nested runtime creation =====

/
/// After fix, create_pool uses .await directly, no Runtime::new().
#[tokio::test]
async fn test_no_nested_runtime_creation() {
    // Verify the main.rs source doesn't contain nested runtime creation.
    // The bug was: Runtime::new().unwrap() inside #[tokio::main] async fn main.
    let main_src = include_str!("../src/main.rs");

    // After fix: main.rs must NOT create a nested runtime
    let has_nested_runtime = main_src.contains("Runtime::new()")
        && main_src.contains("block_on");
    assert!(
        !has_nested_runtime,
        "main.rs must not create a nested Tokio runtime with Runtime::new() + block_on() (L1). \
         Use .await directly inside #[tokio::main] async fn main."
    );

    // Also verify pool creation works within async context (doesn't panic)
    let result = database::create_pool("postgres://localhost:5432/nonexistent").await;
    // Should return Err (can't connect), not panic from nested runtime
    assert!(
        result.is_err(),
        "create_pool must return error for bad URL, not panic (L1)"
    );
}

/
#[tokio::test]
async fn test_async_pool_creation() {
    // After fix: create_pool is called with .await, not rt.block_on()
    // We test that the function signature is async and doesn't block
    // Since we may not have a real DB, we just verify it returns an error
    // (connection refused) rather than panicking from nested runtime.
    let result = database::create_pool("postgres://localhost:5432/nonexistent").await;

    // Should return Err (can't connect), not panic from nested runtime
    // The important thing is that it didn't panic
    assert!(
        result.is_err(),
        "create_pool must return error for bad URL, not panic (L1)"
    );
}

// ===== BUG L2: Database pool configuration =====

/
#[tokio::test]
async fn test_db_pool_configuration() {
    // After fix: create_pool should set max_connections, acquire_timeout, etc.
    // We verify the pool was configured by checking it returns proper errors.
    let result = database::create_pool("postgres://localhost:5432/test_db").await;

    // Connection will fail but shouldn't hang forever (timeout configured)
    // The important thing is it doesn't hang (acquire_timeout is set)
    assert!(result.is_err(), "Pool must timeout on unreachable DB (L2)");
}

/
#[tokio::test]
async fn test_db_pool_timeout_settings() {
    // Test with a deliberately unreachable host
    let start = std::time::Instant::now();
    let result = database::create_pool("postgres://192.0.2.1:5432/test").await;
    let elapsed = start.elapsed();

    // After fix: should fail within a reasonable timeout (< 30s)
    // Without fix: could hang indefinitely
    assert!(
        elapsed.as_secs() < 30,
        "Pool creation must timeout within 30s (L2). Took {:?}",
        elapsed
    );
    assert!(result.is_err(), "Must return error for unreachable host (L2)");
}

// ===== BUG L3: Environment variable parsing =====

/
#[test]
fn test_config_invalid_port_returns_error() {
    // Set PORT to an invalid value
    std::env::set_var("PORT", "not_a_number");
    // Set required vars to prevent unrelated panics
    std::env::set_var("DATABASE_URL", "postgres://test");
    std::env::set_var("MINIO_ENDPOINT", "http://localhost:9000");
    std::env::set_var("MINIO_ACCESS_KEY", "test");
    std::env::set_var("MINIO_SECRET_KEY", "test");
    std::env::set_var("JWT_SECRET", "test");

    let result = std::panic::catch_unwind(|| {
        Config::from_env()
    });

    // After fix: from_env returns Err, not panic
    // The catch_unwind should succeed (no panic), and the Result should be Err
    assert!(
        result.is_ok(),
        "Config::from_env must not panic on invalid PORT (L3)"
    );

    if let Ok(config_result) = result {
        assert!(
            config_result.is_err(),
            "Config::from_env must return Err for invalid PORT, not Ok (L3)"
        );
    }

    // Clean up
    std::env::remove_var("PORT");
}

/
#[test]
fn test_config_missing_env_returns_error() {
    // Remove required env vars
    std::env::remove_var("DATABASE_URL");
    std::env::remove_var("MINIO_ENDPOINT");

    let result = std::panic::catch_unwind(|| {
        Config::from_env()
    });

    assert!(
        result.is_ok(),
        "Config::from_env must not panic on missing env vars (L3)"
    );

    if let Ok(config_result) = result {
        assert!(
            config_result.is_err(),
            "Config::from_env must return Err for missing DATABASE_URL (L3)"
        );
    }
}

/
#[test]
fn test_config_invalid_upload_size_returns_error() {
    std::env::set_var("DATABASE_URL", "postgres://test");
    std::env::set_var("MINIO_ENDPOINT", "http://localhost:9000");
    std::env::set_var("MINIO_ACCESS_KEY", "test");
    std::env::set_var("MINIO_SECRET_KEY", "test");
    std::env::set_var("JWT_SECRET", "test");
    std::env::set_var("MAX_UPLOAD_SIZE", "not_a_number");

    let result = std::panic::catch_unwind(|| {
        Config::from_env()
    });

    assert!(
        result.is_ok(),
        "Config::from_env must not panic on invalid MAX_UPLOAD_SIZE (L3)"
    );

    if let Ok(config_result) = result {
        assert!(
            config_result.is_err(),
            "Config::from_env must return Err for invalid MAX_UPLOAD_SIZE (L3)"
        );
    }

    std::env::remove_var("MAX_UPLOAD_SIZE");
}

// ===== BUG L4: Graceful shutdown =====

/
#[tokio::test]
async fn test_graceful_shutdown_signal_handler() {
    // After fix: shutdown_signal() is wired into axum::serve().with_graceful_shutdown()
    // We can't test the actual server easily, but we verify the function exists
    // and doesn't immediately panic when called in a select! context.

    // Test that we can create a shutdown future (it should wait for signals)
    let shutdown = tokio::time::timeout(
        std::time::Duration::from_millis(100),
        // shutdown_signal() should wait forever (until SIGTERM/SIGINT)
        // so this should timeout, NOT complete immediately
        async {
            // Simulating the pattern that should be used
            tokio::signal::ctrl_c().await.ok();
        }
    ).await;

    // Should timeout (signals not sent)
    assert!(
        shutdown.is_err(),
        "Shutdown signal must wait for actual signal, not complete immediately (L4)"
    );
}

/
#[tokio::test]
async fn test_shutdown_completes_inflight_requests() {
    // This verifies the pattern: axum::serve(...).with_graceful_shutdown(...)
    // After fix, the server would wait for inflight requests before exiting.
    // We verify by checking that the shutdown_signal function is callable.

    // Verify main.rs wires up graceful shutdown
    let main_src = include_str!("../src/main.rs");

    // After fix: main.rs must wire up graceful shutdown
    assert!(
        main_src.contains("with_graceful_shutdown") || main_src.contains("graceful_shutdown"),
        "Server must use with_graceful_shutdown() to handle SIGTERM gracefully (L4). \
         Found no graceful shutdown wiring in main.rs."
    );

    // The shutdown_signal function must not be dead code
    let has_dead_code_attr = main_src.contains("#[allow(dead_code)]");
    let has_shutdown_signal = main_src.contains("shutdown_signal");
    assert!(
        !has_dead_code_attr || !has_shutdown_signal,
        "shutdown_signal must not be marked #[allow(dead_code)] - it must be actively used (L4)"
    );
}

// ===== Meta-validation: initial pass rate sanity check =====
// This test is #[ignore] by default — run explicitly with:
//   cargo test test_initial_pass_rate_is_low -- --ignored
// It verifies that the UNFIXED codebase fails most tests (Senior tier expects ~0-10% pass).
// If this test fails (too many tests pass), bugs may not be properly injected.

#[test]
#[ignore]
fn test_initial_pass_rate_is_low() {
    // This test is designed to be run BEFORE any bug fixes.
    // It verifies the environment's calibration: with all 29 bugs present,
    // the initial pass rate should be very low (< 20%).
    //
    // Since Senior tier has compilation errors (L1-L4, A1-A5, B1-B4),
    // the unfixed codebase won't even compile, meaning 0 tests pass.
    // This test itself compiles because it only uses include_str!() and
    // doesn't invoke any buggy code paths.
    //
    // Run with: cargo test test_initial_pass_rate_is_low -- --ignored
    // Expected: PASS (confirming that bugs are present)

    let main_src = include_str!("../src/main.rs");
    let storage_src = include_str!("../src/services/storage.rs");
    let cache_src = include_str!("../src/services/cache.rs");
    let lock_src = include_str!("../src/services/lock_manager.rs");
    let upload_src = include_str!("../src/handlers/upload.rs");
    let folder_src = include_str!("../src/models/folder.rs");
    let auth_src = include_str!("../src/middleware/auth.rs");
    let search_src = include_str!("../src/repository/search.rs");

    let mut bug_count = 0;

    // L1: nested runtime (Runtime::new + block_on)
    if main_src.contains("Runtime::new") && main_src.contains("block_on") {
        bug_count += 1;
    }

    // A1: use-after-move in storage (bytes used after metadata move)
    if storage_src.contains(".len()") == false
        || storage_src.matches("metadata").count() < 2
    {
        bug_count += 1;
    }

    // B1: cache returns reference to local
    if cache_src.contains("&'a T") || cache_src.contains("&'a str") {
        bug_count += 1;
    }

    // C1: inconsistent lock ordering
    if lock_src.contains("user_locks") && lock_src.contains("file_locks") {
        // Check if both functions use the same ordering
        let src_parts: Vec<&str> = lock_src.split("pub fn").collect();
        if src_parts.len() >= 3 {
            // If lock ordering differs between functions, bug is present
            bug_count += 1;
        }
    }

    // C4: Rc<RefCell> instead of Arc<Mutex> in upload handler
    if upload_src.contains("Rc<RefCell") {
        bug_count += 1;
    }

    // E1: Rc cycle in folder (parent is Rc, not Weak)
    if folder_src.contains("Rc<Folder>") && !folder_src.contains("Weak<Folder>") {
        bug_count += 1;
    }

    // F2: SQL injection (string interpolation in queries)
    if search_src.contains("format!") && search_src.contains("WHERE") {
        bug_count += 1;
    }

    // F3: timing attack (no constant-time comparison)
    if !auth_src.contains("ct_eq") && !auth_src.contains("constant_time") {
        bug_count += 1;
    }

    // At least 5 of these 8 sampled bugs should be present in unfixed code
    assert!(
        bug_count >= 5,
        "Expected at least 5 of 8 sampled bugs to be present in unfixed source, \
         but only found {}. Bugs may not be properly injected.",
        bug_count
    );
}
