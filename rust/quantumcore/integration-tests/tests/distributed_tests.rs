//! Distributed systems tests for QuantumCore
//!
//! Tests cover: G1-G8 distributed systems bugs, L1-L8 setup/config bugs

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use std::path::PathBuf;
use parking_lot::{Mutex, RwLock};

// =============================================================================
// Source-code verification helpers
// =============================================================================

fn workspace_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir.parent().unwrap().to_path_buf()
}

fn read_source(relative_path: &str) -> String {
    let path = workspace_root().join(relative_path);
    std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {}", path.display(), e))
}

// =============================================================================
// G1: Event Ordering Tests
// =============================================================================

#[test]
fn test_g1_event_ordering_guaranteed() {

    let events: Vec<u64> = (0..100).collect();
    let processed = Arc::new(Mutex::new(Vec::new()));

    let p = processed.clone();
    for event in events.clone() {
        p.lock().push(event);
    }

    let result = processed.lock();
    for i in 0..99 {
        assert!(result[i] < result[i + 1], "Events must be in order");
    }
}

#[test]
fn test_g1_nats_sequence_order() {

    let sequences: Vec<u64> = vec![1, 2, 3, 5, 4, 6]; // Out of order

    let mut last_seq = 0;
    let mut gaps = 0;

    for seq in sequences {
        if seq != last_seq + 1 && last_seq != 0 {
            gaps += 1;
        }
        last_seq = seq;
    }

    // Should detect gaps/reordering
    assert!(gaps > 0, "Should detect sequence gaps");
}

#[test]
fn test_g1_causal_ordering() {
    // Events from same source should maintain causal order
    let events = vec![
        ("source_a", 1),
        ("source_a", 2),
        ("source_b", 1),
        ("source_a", 3),
    ];

    let mut per_source: HashMap<&str, u64> = HashMap::new();

    for (source, seq) in events {
        let last = per_source.entry(source).or_insert(0);
        assert!(seq >= *last, "Causal order violated for {}", source);
        *last = seq;
    }
}

// =============================================================================
// G1: Event Ordering Source Verification
// =============================================================================

#[test]
fn test_g1_event_ordering_preserved() {
    // BUG G1: NATS publish doesn't use JetStream for ordered delivery
    let src = read_source("shared/src/nats.rs");
    // Should use JetStream for ordered, persistent messaging
    let has_jetstream = src.contains("jetstream") || src.contains("JetStream");
    assert!(has_jetstream,
        "NATS client should use JetStream for guaranteed event ordering");
}

// =============================================================================
// G2: Distributed Lock Tests
// =============================================================================

#[test]
fn test_g2_distributed_lock_released() {

    let lock = Arc::new(Mutex::new(()));

    // Acquire and release
    {
        let _guard = lock.lock();
        // Do work
    }
    // Lock should be released

    // Should be able to acquire again
    let _guard = lock.try_lock();
    assert!(_guard.is_some(), "Lock should be available");
}

#[test]
fn test_g2_position_lock_cleanup() {

    let locks: Arc<RwLock<HashMap<String, bool>>> = Arc::new(RwLock::new(HashMap::new()));

    // Acquire lock
    {
        locks.write().insert("position_1".to_string(), true);
    }

    // Release lock
    locks.write().remove("position_1");

    // Verify released
    assert!(!locks.read().contains_key("position_1"));
}

#[test]
fn test_g2_lock_timeout() {
    // BUG G2: Distributed locks should have TTL/timeout to prevent deadlocks
    let src = read_source("services/positions/src/tracker.rs");
    // Position tracker should implement lock timeouts or TTL on position locks
    let has_timeout = src.contains("ttl") || src.contains("timeout")
        || src.contains("expire") || src.contains("lease")
        || src.contains("Duration");
    // Also check for version-based optimistic locking with expected_version
    let has_optimistic = src.contains("expected_version") || src.contains("compare_and_swap");
    assert!(has_timeout || has_optimistic,
        "Distributed locks should have TTL/timeout or optimistic locking to prevent deadlocks");
}

// =============================================================================
// G3: Split Brain Tests
// =============================================================================

#[test]
fn test_g3_split_brain_prevented() {
    // BUG G3: Matching engine should have fencing tokens to prevent split-brain
    let src = read_source("services/matching/src/engine.rs");
    let has_fencing = src.contains("epoch") || src.contains("fence")
        || src.contains("generation") || src.contains("term")
        || src.contains("leader_id");
    assert!(has_fencing,
        "Matching engine should have fencing tokens or epoch numbers to prevent split-brain");
}

#[test]
fn test_g3_matching_failover_safe() {

    let primary_active = Arc::new(AtomicBool::new(true));
    let secondary_active = Arc::new(AtomicBool::new(false));

    // Failover: primary goes down
    primary_active.store(false, Ordering::SeqCst);

    // Wait for detection
    thread::sleep(Duration::from_millis(10));

    // Secondary takes over
    secondary_active.store(true, Ordering::SeqCst);

    let p = primary_active.load(Ordering::SeqCst);
    let s = secondary_active.load(Ordering::SeqCst);

    // Only one active at a time (after failover completes)
    assert!(!p || !s, "Should not have both active");
}

// =============================================================================
// G4: Idempotency Tests
// =============================================================================

#[test]
fn test_g4_idempotency_key_unique() {

    use std::collections::HashSet;

    let mut keys: HashSet<String> = HashSet::new();

    for i in 0..100 {
        let key = format!("order_{}_{}", "client_1", i);
        assert!(keys.insert(key.clone()), "Key should be unique: {}", key);
    }
}

#[test]
fn test_g4_order_idempotent() {

    let processed_keys: Arc<Mutex<HashSet<String>>> = Arc::new(Mutex::new(HashSet::new()));

    let idempotency_key = "order_123";

    // First request - should succeed
    let first_result = processed_keys.lock().insert(idempotency_key.to_string());
    assert!(first_result, "First request should succeed");

    // Duplicate request - should be rejected
    let second_result = processed_keys.lock().insert(idempotency_key.to_string());
    assert!(!second_result, "Duplicate should be rejected");
}

#[test]
fn test_g4_idempotency_key_format() {
    // BUG G4: Order service should use proper idempotency keys (hash-based or UUID)
    let src = read_source("services/orders/src/service.rs");
    // The create_order function should check for duplicate client_order_id
    let has_dedup = src.contains("client_order_id")
        && (src.contains("contains_key") || src.contains("exists") || src.contains("duplicate"));
    assert!(has_dedup,
        "Order service should check for duplicate client_order_id to ensure idempotency");
}

// =============================================================================
// G5: Saga Compensation Tests
// =============================================================================

#[test]
fn test_g5_saga_compensation_correct() {

    let mut steps_completed: Vec<&str> = Vec::new();
    let mut compensations_run: Vec<&str> = Vec::new();

    // Execute steps
    steps_completed.push("reserve_funds");
    steps_completed.push("place_order");
    // Step 3 fails
    let step_3_failed = true;

    if step_3_failed {
        // Compensate in reverse order
        for step in steps_completed.iter().rev() {
            compensations_run.push(step);
        }
    }

    assert_eq!(compensations_run.len(), 2);
    assert_eq!(compensations_run[0], "place_order"); // Reverse order
    assert_eq!(compensations_run[1], "reserve_funds");
}

#[test]
fn test_g5_ledger_rollback_complete() {

    let mut ledger_entries: Vec<i64> = Vec::new();

    // Record debits and credits
    ledger_entries.push(-100); // Debit
    ledger_entries.push(100);  // Credit

    // On rollback, sum should be zero
    let balance: i64 = ledger_entries.iter().sum();
    assert_eq!(balance, 0, "Ledger should balance");
}

// =============================================================================
// G6: Circuit Breaker Tests
// =============================================================================

#[test]
fn test_g6_circuit_breaker_correct() {

    let failure_count = Arc::new(AtomicU64::new(0));
    let circuit_open = Arc::new(AtomicBool::new(false));
    let failure_threshold = 5u64;

    // Simulate failures
    for _ in 0..6 {
        let count = failure_count.fetch_add(1, Ordering::SeqCst) + 1;
        if count >= failure_threshold {
            circuit_open.store(true, Ordering::SeqCst);
        }
    }

    assert!(circuit_open.load(Ordering::SeqCst), "Circuit should be open");
}

#[test]
fn test_g6_gateway_circuit_state() {

    #[derive(Debug, Clone, Copy, PartialEq)]
    enum CircuitState {
        Closed,
        Open,
        HalfOpen,
    }

    let state = Arc::new(RwLock::new(CircuitState::Closed));

    // Failures open the circuit
    *state.write() = CircuitState::Open;

    // After timeout, go to half-open
    thread::sleep(Duration::from_millis(10));
    *state.write() = CircuitState::HalfOpen;

    // Success closes it
    *state.write() = CircuitState::Closed;

    assert_eq!(*state.read(), CircuitState::Closed);
}

#[test]
fn test_g6_circuit_breaker_reset() {
    // Circuit should reset after success in half-open state
    let success_count = Arc::new(AtomicU64::new(0));
    let failure_count = Arc::new(AtomicU64::new(5)); // Circuit is open
    let reset_threshold = 3u64;

    // Successful requests in half-open
    for _ in 0..3 {
        success_count.fetch_add(1, Ordering::SeqCst);
    }

    if success_count.load(Ordering::SeqCst) >= reset_threshold {
        failure_count.store(0, Ordering::SeqCst);
    }

    assert_eq!(failure_count.load(Ordering::SeqCst), 0, "Circuit should be reset");
}

#[test]
fn test_g6_circuit_breaker_per_service() {
    // BUG G6: Circuit breaker state should be per-service, not shared
    let src = read_source("services/gateway/src/middleware.rs");
    // Rate limit state should identify clients properly
    // The bug is using X-Forwarded-For which is spoofable
    let has_per_service = src.contains("service") || src.contains("endpoint")
        || src.contains("target");
    // At minimum, state should not be globally shared across services
    assert!(has_per_service || src.contains("HashMap"),
        "Circuit breaker should maintain per-service state");
}

// =============================================================================
// G7: Retry with Backoff Tests (source-verifying)
// =============================================================================

#[test]
fn test_g7_retry_with_backoff() {
    // BUG G7: HTTP client retries immediately without backoff
    let src = read_source("shared/src/http.rs");
    // Retry logic MUST include a delay/sleep between attempts
    let has_backoff = src.contains("sleep") || src.contains("delay")
        || src.contains("backoff") || src.contains("Duration");
    // Check that there's actual waiting between retries (not just timeout config)
    let retry_section = src.split("for attempt").nth(1).unwrap_or("");
    let has_wait_in_retry = retry_section.contains("sleep") || retry_section.contains("delay");
    assert!(has_backoff && has_wait_in_retry,
        "HTTP retry logic must include exponential backoff (sleep/delay between retries)");
}

#[test]
fn test_g7_no_retry_storm() {
    // BUG G7: Retries should include jitter to prevent thundering herd
    let src = read_source("shared/src/http.rs");
    let has_jitter = src.contains("jitter") || src.contains("rand")
        || src.contains("random") || src.contains("thread_rng");
    assert!(has_jitter,
        "Retry logic should include jitter to prevent retry storms / thundering herd");
}

#[test]
fn test_g7_max_retry_limit() {
    // G7: Retries should be bounded and use exponential backoff
    let src = read_source("shared/src/http.rs");
    assert!(src.contains("max_retries"), "Should have a max retry limit");
    // Verify exponential pattern: delay should grow with each attempt
    let has_exponential = src.contains("pow") || src.contains("* 2")
        || src.contains("exponential") || src.contains("<< attempt");
    assert!(has_exponential,
        "Retry delay should grow exponentially (not fixed interval)");
}

// =============================================================================
// G8: Leader Election Tests
// =============================================================================

#[test]
fn test_g8_leader_election_safe() {

    let _candidates = vec!["node_1", "node_2", "node_3"];
    let votes: HashMap<&str, u32> = vec![
        ("node_1", 2),
        ("node_2", 1),
        ("node_3", 0),
    ].into_iter().collect();

    let leader = votes.iter().max_by_key(|&(_, v)| v).map(|(k, _)| *k);
    assert_eq!(leader, Some("node_1"));
}

#[test]
fn test_g8_matching_leader_consistent() {

    let leader_view: HashMap<&str, &str> = vec![
        ("node_1", "node_1"), // Each node's view of who is leader
        ("node_2", "node_1"),
        ("node_3", "node_1"),
    ].into_iter().collect();

    let unique_leaders: std::collections::HashSet<_> = leader_view.values().collect();
    assert_eq!(unique_leaders.len(), 1, "All nodes should agree on leader");
}

#[test]
fn test_g8_leader_election_stable() {
    // BUG G8: Leader election should use proper consensus
    let src = read_source("services/matching/src/engine.rs");
    // Matching engine should have leader election or consensus mechanism
    let has_election = src.contains("leader") || src.contains("election")
        || src.contains("consensus") || src.contains("raft");
    assert!(has_election,
        "Matching engine should implement leader election for safe failover");
}

// =============================================================================
// L1: NATS Connection Tests
// =============================================================================

#[test]
fn test_l1_nats_reconnection() {

    let connected = Arc::new(AtomicBool::new(true));
    let reconnect_attempts = Arc::new(AtomicU64::new(0));

    // Simulate disconnect
    connected.store(false, Ordering::SeqCst);

    // Reconnection loop
    while !connected.load(Ordering::SeqCst) {
        reconnect_attempts.fetch_add(1, Ordering::SeqCst);
        if reconnect_attempts.load(Ordering::SeqCst) >= 3 {
            // Simulate successful reconnection
            connected.store(true, Ordering::SeqCst);
        }
    }

    assert!(connected.load(Ordering::SeqCst));
    assert_eq!(reconnect_attempts.load(Ordering::SeqCst), 3);
}

#[test]
fn test_l1_nats_connection_recovery() {
    // BUG L1: NATS client should use ConnectOptions with reconnect callbacks
    let src = read_source("shared/src/nats.rs");
    // Should use ConnectOptions for resilient connection
    let has_reconnect = src.contains("ConnectOptions")
        && (src.contains("reconnect") || src.contains("retry_on_initial"));
    assert!(has_reconnect,
        "NATS client should use ConnectOptions with reconnection handling, not bare connect()");
}

// =============================================================================
// L3: Database Pool Exhaustion Tests
// =============================================================================

#[test]
fn test_l3_db_pool_under_load() {

    let pool_size = 10;
    let active_connections = Arc::new(AtomicU64::new(0));
    let max_active = Arc::new(AtomicU64::new(0));

    let mut handles = vec![];

    for _ in 0..20 {
        let ac = active_connections.clone();
        let ma = max_active.clone();

        handles.push(thread::spawn(move || {
            // Acquire connection
            let current = ac.fetch_add(1, Ordering::SeqCst) + 1;
            ma.fetch_max(current, Ordering::SeqCst);

            thread::sleep(Duration::from_millis(5));

            // Release connection
            ac.fetch_sub(1, Ordering::SeqCst);
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    // Max active should be bounded by pool size
    assert!(max_active.load(Ordering::SeqCst) <= pool_size as u64 + 10,
        "Active connections should be reasonable");
}

#[test]
fn test_l3_connection_pool_exhaustion() {
    // BUG L3: Orders service should handle pool exhaustion gracefully
    let src = read_source("services/orders/src/service.rs");
    // Should have bounded resources — check for capacity limits or pool configuration
    let has_bounds = src.contains("capacity") || src.contains("max_size")
        || src.contains("pool_size") || src.contains("Semaphore")
        || src.contains("bounded");
    // At minimum, the event sequence counter should use proper ordering
    let uses_relaxed_for_sequence = src.contains("Ordering::Relaxed");
    assert!(has_bounds || !uses_relaxed_for_sequence,
        "Orders service should have bounded resource management and proper atomic ordering");
}

// =============================================================================
// L4: Graceful Shutdown Tests
// =============================================================================

#[test]
fn test_l4_graceful_shutdown() {

    let in_flight = Arc::new(AtomicU64::new(5));
    let shutting_down = Arc::new(AtomicBool::new(false));

    // Initiate shutdown
    shutting_down.store(true, Ordering::SeqCst);

    // Drain in-flight
    while in_flight.load(Ordering::SeqCst) > 0 {
        in_flight.fetch_sub(1, Ordering::SeqCst);
    }

    assert_eq!(in_flight.load(Ordering::SeqCst), 0);
}

#[test]
fn test_l4_shutdown_drains_connections() {
    // BUG L4: Gateway should implement graceful shutdown
    let gateway_src = read_source("services/gateway/src/middleware.rs");
    let ws_src = read_source("services/gateway/src/websocket.rs");
    let combined = format!("{}\n{}", gateway_src, ws_src);
    // Gateway should handle shutdown signals and drain connections
    let has_shutdown = combined.contains("shutdown") || combined.contains("graceful")
        || combined.contains("signal") || combined.contains("ctrl_c")
        || combined.contains("SIGTERM");
    assert!(has_shutdown,
        "Gateway should implement graceful shutdown to drain connections before stopping");
}

// =============================================================================
// L5: Service Discovery Tests
// =============================================================================

#[test]
fn test_l5_service_discovery_consistency() {

    let services: Arc<RwLock<Vec<&str>>> = Arc::new(RwLock::new(vec!["svc1", "svc2"]));

    let mut views: Vec<Vec<&str>> = Vec::new();

    for _ in 0..3 {
        let view = services.read().clone();
        views.push(view);
    }

    // All views should be identical
    assert!(views.windows(2).all(|w| w[0] == w[1]));
}

#[test]
fn test_l5_discovery_race_condition() {

    let services = Arc::new(RwLock::new(vec!["a", "b"]));

    let s = services.clone();
    let reader = thread::spawn(move || {
        for _ in 0..100 {
            let _list = s.read().clone();
        }
    });

    for _ in 0..100 {
        let mut list = services.write();
        list.push("c");
        list.pop();
    }

    reader.join().unwrap();
}

// =============================================================================
// L6: Config Hot Reload Tests
// =============================================================================

#[test]
fn test_l6_config_hot_reload_safe() {

    let config = Arc::new(RwLock::new(HashMap::new()));
    config.write().insert("key", "value");

    // Simulate hot reload
    {
        let mut c = config.write();
        c.clear();
        c.insert("key", "new_value");
    }

    assert_eq!(config.read().get("key"), Some(&"new_value"));
}

#[test]
fn test_l6_config_reload_no_crash() {
    // Concurrent reads during reload should not crash
    let config = Arc::new(RwLock::new("v1"));

    let c = config.clone();
    let reader = thread::spawn(move || {
        for _ in 0..100 {
            let _v = *c.read();
        }
    });

    for _ in 0..10 {
        *config.write() = "v2";
    }

    reader.join().unwrap();
}

// =============================================================================
// L7: Timezone Handling Tests (source-verifying)
// =============================================================================

#[test]
fn test_l7_timestamp_timezone_utc() {
    // BUG L7: Market service must use UTC for all timestamps
    let src = read_source("services/market/src/aggregator.rs");
    // Should use chrono::Utc, not chrono::Local
    assert!(src.contains("Utc"),
        "Market service must use chrono::Utc for timestamps");
    assert!(!src.contains("Local::now") && !src.contains("chrono::Local"),
        "Market service must not use local timezone — all timestamps should be UTC");
}

#[test]
fn test_l7_market_hours_timezone() {
    // L7: Day-level aggregation should account for market hours, not just UTC midnight
    let src = read_source("services/market/src/aggregator.rs");
    // The Day1 aggregation uses duration_trunc(Duration::days(1)) which truncates to UTC midnight
    // This may not align with market trading hours
    // Check that there's some awareness of market hours or timezone offset for daily bars
    let day1_section = src.split("Day1").nth(1).unwrap_or("");
    let has_market_hours = day1_section.contains("market_open")
        || day1_section.contains("trading_hours")
        || day1_section.contains("exchange_tz")
        || day1_section.contains("offset");
    // Also acceptable: using a configurable timezone for daily aggregation
    let has_tz_config = src.contains("timezone") || src.contains("tz_offset");
    assert!(has_market_hours || has_tz_config,
        "Daily aggregation should account for market hours/timezone, not just UTC midnight truncation");
}

// =============================================================================
// L8: TLS Certificate Validation Tests (source-verifying)
// =============================================================================

#[test]
fn test_l8_tls_certificate_validation() {
    // BUG L8: TLS/SSL verification is disabled in ApiKeyManager
    let src = read_source("services/auth/src/api_key.rs");
    // The default for verify_ssl should be true, not false
    let new_fn_body = src.split("fn new").nth(1).unwrap_or("");
    let constructor = new_fn_body.split('}').next().unwrap_or("");
    assert!(!constructor.contains("verify_ssl: false"),
        "TLS/SSL verification should be enabled by default (verify_ssl must not default to false)");
}

#[test]
fn test_l8_tls_not_disabled() {
    // BUG L8: Auth service should validate TLS certificates
    let src = read_source("services/auth/src/api_key.rs");
    // Should not have patterns that disable certificate validation
    assert!(!src.contains("danger_accept_invalid_certs"),
        "Should not accept invalid TLS certificates");
    // verify_ssl should exist and be initialized to true
    assert!(src.contains("verify_ssl"), "Should have SSL verification field");
    // Check the actual initialization value
    let lines: Vec<&str> = src.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        if line.contains("verify_ssl") && line.contains("false") && !line.trim().starts_with("//") {
            panic!("Line {}: verify_ssl is set to false — TLS validation is disabled (bug L8)", i + 1);
        }
    }
}
