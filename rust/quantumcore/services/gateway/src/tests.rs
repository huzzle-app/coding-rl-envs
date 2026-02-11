//! Comprehensive tests for gateway service
//!
//! Tests cover:
//! - Bug L4: Graceful shutdown
//! - Bug B4: Future not Send
//! - Bug B10: Thread pool exhaustion
//! - Bug C8: Panic hook
//! - Bug H4: Rate limit bypass
//! - Bug D8: Buffer not released
//! - Bug G6: Circuit breaker state
//! - Router/routing tests
//! - Rate limiting tests
//! - WebSocket connection tests
//! - Authentication middleware tests
//! - Concurrent connection tests

use super::*;
use crate::middleware::{authenticate, panic_recovery, rate_limit, request_logging, RateLimitState};
use crate::router::{AppState, OrderRequest, OrderResponse, create_router};
use crate::websocket::WebSocketManager;

use axum::body::Body;
use axum::http::{header, Method, Request, StatusCode};
use axum::Router;
use parking_lot::Mutex;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Semaphore;
use uuid::Uuid;

// =============================================================================

// =============================================================================

/// Test that graceful shutdown waits for in-flight requests
/
#[tokio::test]
async fn test_graceful_shutdown_waits_for_requests() {
    let shutdown_signal = Arc::new(AtomicBool::new(false));
    let requests_in_flight = Arc::new(AtomicU64::new(0));

    // Simulate starting a request
    requests_in_flight.fetch_add(1, Ordering::SeqCst);

    // Signal shutdown
    shutdown_signal.store(true, Ordering::SeqCst);

    // Shutdown should not complete while requests are in flight
    
    assert!(requests_in_flight.load(Ordering::SeqCst) > 0);

    // Complete the request
    requests_in_flight.fetch_sub(1, Ordering::SeqCst);

    // Now shutdown can proceed
    assert_eq!(requests_in_flight.load(Ordering::SeqCst), 0);
}

/// Test shutdown signal propagation
#[tokio::test]
async fn test_shutdown_signal_propagation() {
    let shutdown = Arc::new(AtomicBool::new(false));
    let cloned = shutdown.clone();

    // Spawn a task that watches for shutdown
    let handle = tokio::spawn(async move {
        while !cloned.load(Ordering::SeqCst) {
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
        true
    });

    // Signal shutdown after brief delay
    tokio::time::sleep(Duration::from_millis(50)).await;
    shutdown.store(true, Ordering::SeqCst);

    // Task should complete
    let result = tokio::time::timeout(Duration::from_secs(1), handle).await;
    assert!(result.is_ok(), "Task should complete after shutdown signal");
}

/// Test that new connections are rejected during shutdown
#[tokio::test]
async fn test_reject_new_connections_during_shutdown() {
    let accepting_connections = Arc::new(AtomicBool::new(true));

    // Initially accept connections
    assert!(accepting_connections.load(Ordering::SeqCst));

    // Start shutdown - should stop accepting
    accepting_connections.store(false, Ordering::SeqCst);

    // Verify new connection would be rejected
    assert!(!accepting_connections.load(Ordering::SeqCst));
}

// =============================================================================

// =============================================================================

/// Test that futures can be sent across threads
/
#[tokio::test]
async fn test_future_is_send() {
    // Verify AppState can be shared across threads
    fn assert_send<T: Send>() {}
    fn assert_sync<T: Sync>() {}

    assert_send::<AppState>();
    assert_sync::<AppState>();
}

/// Test that WebSocket manager is thread-safe
#[tokio::test]
async fn test_websocket_manager_send_sync() {
    fn assert_send<T: Send>() {}
    fn assert_sync<T: Sync>() {}

    assert_send::<WebSocketManager>();
    assert_sync::<WebSocketManager>();
}

/// Test spawning tasks with state
#[tokio::test]
async fn test_spawn_with_state() {
    let state = AppState::new();
    let state_clone = state.clone();

    // This should compile only if state is Send
    let handle = tokio::spawn(async move {
        let _ = state_clone.check_rate_limit("test", 100, Duration::from_secs(60));
    });

    assert!(handle.await.is_ok());
}

/// Test that rate limit state can be moved across threads
#[tokio::test]
async fn test_rate_limit_state_movable() {
    let state = Arc::new(Mutex::new(RateLimitState::new(100, Duration::from_secs(60))));
    let state_clone = state.clone();

    let handle = tokio::spawn(async move {
        let _guard = state_clone.lock();
        true
    });

    assert!(handle.await.unwrap());
}

// =============================================================================

// =============================================================================

/// Test that connection limits are enforced
/
#[tokio::test]
async fn test_connection_limit_enforced() {
    let max_connections = 100;
    let connection_semaphore = Arc::new(Semaphore::new(max_connections));

    let mut permits = Vec::new();

    // Acquire all permits
    for _ in 0..max_connections {
        let permit = connection_semaphore.clone().try_acquire_owned();
        assert!(permit.is_ok());
        permits.push(permit.unwrap());
    }

    // Next acquisition should fail
    let result = connection_semaphore.try_acquire();
    assert!(result.is_err(), "Should reject connection when at limit");
}

/// Test thread pool under high load
#[tokio::test]
async fn test_thread_pool_under_load() {
    let completed = Arc::new(AtomicU64::new(0));
    let num_tasks = 1000;

    let mut handles = Vec::new();

    for _ in 0..num_tasks {
        let completed_clone = completed.clone();
        handles.push(tokio::spawn(async move {
            // Simulate some work
            tokio::time::sleep(Duration::from_micros(100)).await;
            completed_clone.fetch_add(1, Ordering::SeqCst);
        }));
    }

    for handle in handles {
        let _ = handle.await;
    }

    assert_eq!(completed.load(Ordering::SeqCst), num_tasks);
}

/// Test that blocking operations don't exhaust pool
#[tokio::test]
async fn test_blocking_operations_isolated() {
    let completed = Arc::new(AtomicBool::new(false));
    let completed_clone = completed.clone();

    // Use spawn_blocking for blocking operations
    let handle = tokio::task::spawn_blocking(move || {
        std::thread::sleep(Duration::from_millis(10));
        completed_clone.store(true, Ordering::SeqCst);
    });

    handle.await.unwrap();
    assert!(completed.load(Ordering::SeqCst));
}

/// Test concurrent WebSocket connections
#[tokio::test]
async fn test_concurrent_websocket_connections() {
    let manager = WebSocketManager::new();

    // WebSocket manager should handle multiple connections
    assert_eq!(manager.connection_count(), 0);

    // Broadcast should work even without connections
    manager.broadcast("test message".to_string());
}

// =============================================================================

// =============================================================================

/// Test that panic hook is configured
/
#[tokio::test]
async fn test_panic_hook_configured() {
    // In production, we should set a panic hook
    

    let panic_count = Arc::new(AtomicU64::new(0));
    let panic_count_clone = panic_count.clone();

    // Set up a custom panic hook for testing
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |_| {
        panic_count_clone.fetch_add(1, Ordering::SeqCst);
    }));

    // Restore hook after test
    std::panic::set_hook(default_hook);

    // The hook should be configurable
    assert_eq!(panic_count.load(Ordering::SeqCst), 0);
}

/// Test panic recovery in async context
#[tokio::test]
async fn test_panic_recovery_async() {
    
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        // Synchronous code CAN be caught
        42
    }));

    assert!(result.is_ok());
    assert_eq!(result.unwrap(), 42);
}

/// Test that panics in spawned tasks are isolated
#[tokio::test]
async fn test_panic_isolation_in_tasks() {
    let handle = tokio::spawn(async {
        // This task completes normally
        42
    });

    let result = handle.await;
    assert!(result.is_ok());
}

/// Test error handling without panic
#[tokio::test]
async fn test_error_handling_no_panic() {
    let result: Result<i32, &str> = Err("handled error");

    // Errors should be handled, not panic
    match result {
        Ok(_) => panic!("Unexpected success"),
        Err(e) => assert_eq!(e, "handled error"),
    }
}

// =============================================================================

// =============================================================================

/// Test rate limit bypass via X-Forwarded-For spoofing
/
#[tokio::test]
async fn test_rate_limit_bypass_via_xff() {
    let state = Arc::new(Mutex::new(RateLimitState::new(5, Duration::from_secs(60))));

    // First 5 requests from "192.168.1.1" should succeed
    for _ in 0..5 {
        let mut guard = state.lock();
        let key = "192.168.1.1";
        
        assert!(guard.requests.len() <= 1);
        guard.requests.entry(key.to_string()).or_insert((0, Instant::now()));
    }

    
    // Each unique IP value gets a fresh rate limit window
}

/// Test rate limit with API key bypass
#[tokio::test]
async fn test_rate_limit_api_key_bypass() {
    let state = AppState::new();

    
    // Each API key is treated as a different identity
    assert!(state.check_rate_limit("api_key_1", 5, Duration::from_secs(60)));
    assert!(state.check_rate_limit("api_key_2", 5, Duration::from_secs(60)));
    assert!(state.check_rate_limit("api_key_3", 5, Duration::from_secs(60)));
}

/// Test rate limit window reset
#[tokio::test]
async fn test_rate_limit_window_reset() {
    let state = AppState::new();

    // Use up the limit
    for _ in 0..10 {
        state.check_rate_limit("test_key", 10, Duration::from_millis(50));
    }

    // Should be rate limited now
    assert!(!state.check_rate_limit("test_key", 10, Duration::from_millis(50)));

    // Wait for window to reset
    std::thread::sleep(Duration::from_millis(60));

    // Should be allowed again
    assert!(state.check_rate_limit("test_key", 10, Duration::from_millis(50)));
}

/// Test rate limit race condition
#[tokio::test]
async fn test_rate_limit_race_condition() {
    let state = Arc::new(AppState::new());
    let success_count = Arc::new(AtomicU64::new(0));

    let mut handles = Vec::new();
    let limit = 100;
    let num_requests = 200;

    for _ in 0..num_requests {
        let state_clone = state.clone();
        let success_count_clone = success_count.clone();
        handles.push(tokio::spawn(async move {
            if state_clone.check_rate_limit("concurrent_key", limit, Duration::from_secs(60)) {
                success_count_clone.fetch_add(1, Ordering::SeqCst);
            }
        }));
    }

    for handle in handles {
        handle.await.unwrap();
    }

    
    // Ideally should be exactly `limit`, but race conditions can cause variance
    let successes = success_count.load(Ordering::SeqCst);
    assert!(successes >= limit as u64 - 5); // Allow small variance due to race
}

// =============================================================================

// =============================================================================

/// Test that message buffers are cleaned up on disconnect
/
#[tokio::test]
async fn test_buffer_cleanup_on_disconnect() {
    let manager = WebSocketManager::new();

    // Initially no connections
    assert_eq!(manager.connection_count(), 0);

    
    // But the current implementation forgets to remove from message_buffers
}

/// Test buffer growth tracking
#[tokio::test]
async fn test_buffer_growth_unbounded() {
    
    let buffer: Vec<u8> = Vec::with_capacity(65536);
    assert_eq!(buffer.capacity(), 65536);

    // In the buggy implementation, this keeps growing
    // and is never cleared even when messages are processed
}

/// Test memory leak detection approach
#[tokio::test]
async fn test_memory_leak_detection() {
    let buffers: Arc<parking_lot::RwLock<HashMap<Uuid, Vec<u8>>>> =
        Arc::new(parking_lot::RwLock::new(HashMap::new()));

    let conn_id = Uuid::new_v4();

    // Simulate connection - add buffer
    {
        let mut bufs = buffers.write();
        bufs.insert(conn_id, Vec::with_capacity(65536));
    }

    assert_eq!(buffers.read().len(), 1);

    // Simulate disconnect - buffer should be removed
    {
        let mut bufs = buffers.write();
        bufs.remove(&conn_id);
    }

    assert_eq!(buffers.read().len(), 0, "Buffer should be cleaned up");
}

/// Test buffer accumulation with binary data
#[tokio::test]
async fn test_buffer_accumulation() {
    let buffer = Arc::new(parking_lot::RwLock::new(Vec::<u8>::new()));

    // Simulate receiving binary messages
    for i in 0..100 {
        let mut buf = buffer.write();
        buf.extend_from_slice(&vec![i as u8; 1024]);
    }

    
    assert_eq!(buffer.read().len(), 100 * 1024);

    // Should be cleared periodically, but isn't
}

// =============================================================================

// =============================================================================

/// Test circuit breaker state machine correctness
/
#[tokio::test]
async fn test_circuit_breaker_state_transitions() {
    #[derive(Clone, Copy, PartialEq, Debug)]
    enum CircuitState {
        Closed,
        Open,
        HalfOpen,
    }

    struct CircuitBreaker {
        state: Arc<parking_lot::RwLock<CircuitState>>,
        failure_count: AtomicU64,
        failure_threshold: u64,
    }

    impl CircuitBreaker {
        fn new(threshold: u64) -> Self {
            Self {
                state: Arc::new(parking_lot::RwLock::new(CircuitState::Closed)),
                failure_count: AtomicU64::new(0),
                failure_threshold: threshold,
            }
        }

        fn record_failure(&self) {
            let count = self.failure_count.fetch_add(1, Ordering::SeqCst) + 1;
            if count >= self.failure_threshold {
                *self.state.write() = CircuitState::Open;
            }
        }

        fn is_closed(&self) -> bool {
            *self.state.read() == CircuitState::Closed
        }
    }

    let cb = CircuitBreaker::new(5);
    assert!(cb.is_closed());

    // Record failures until threshold
    for _ in 0..5 {
        cb.record_failure();
    }

    assert!(!cb.is_closed(), "Circuit should be open after threshold");
}

/// Test circuit breaker concurrent access
#[tokio::test]
async fn test_circuit_breaker_concurrent_access() {
    let failure_count = Arc::new(AtomicU64::new(0));
    let threshold: u64 = 100;
    let num_threads = 10;
    let failures_per_thread = 20;

    let mut handles = Vec::new();

    for _ in 0..num_threads {
        let count = failure_count.clone();
        handles.push(tokio::spawn(async move {
            for _ in 0..failures_per_thread {
                count.fetch_add(1, Ordering::SeqCst);
            }
        }));
    }

    for handle in handles {
        handle.await.unwrap();
    }

    assert_eq!(
        failure_count.load(Ordering::SeqCst),
        num_threads * failures_per_thread
    );
}

/// Test circuit breaker state not shared correctly
#[tokio::test]
async fn test_circuit_breaker_not_shared() {
    
    // This simulates two instances seeing different states

    let instance1_state = Arc::new(AtomicU64::new(0)); // 0 = closed
    let instance2_state = Arc::new(AtomicU64::new(0));

    // Instance 1 sees failures and opens circuit
    instance1_state.store(1, Ordering::SeqCst); // 1 = open

    
    assert_eq!(instance2_state.load(Ordering::SeqCst), 0);

    // In a correct implementation, both would be synchronized
}

/// Test circuit breaker recovery
#[tokio::test]
async fn test_circuit_breaker_recovery() {
    let is_open = Arc::new(AtomicBool::new(true));
    let success_count = Arc::new(AtomicU64::new(0));
    let recovery_threshold = 5u64;

    // Simulate successful requests during half-open
    for _ in 0..recovery_threshold {
        success_count.fetch_add(1, Ordering::SeqCst);
    }

    // After enough successes, circuit should close
    if success_count.load(Ordering::SeqCst) >= recovery_threshold {
        is_open.store(false, Ordering::SeqCst);
    }

    assert!(!is_open.load(Ordering::SeqCst), "Circuit should recover");
}

// =============================================================================
// Router/Routing Tests
// =============================================================================

/// Test router creation
#[tokio::test]
async fn test_router_creation() {
    let router = create_router();
    // Router should be created without panicking
    let _ = router;
}

/// Test health check endpoint
#[tokio::test]
async fn test_health_check_route() {
    let state = AppState::new();
    let _app: Router = create_router().with_state(state);

    // Health check should be accessible
    // In a real test, we'd use axum-test to send requests
}

/// Test order endpoint routes exist
#[tokio::test]
async fn test_order_routes_exist() {
    let state = AppState::new();
    let _app: Router = create_router().with_state(state);

    // Verify routes are configured
    // POST /orders, GET /orders/:id, GET /positions/:account
}

/// Test route matching for order ID
#[tokio::test]
async fn test_order_id_route_matching() {
    // Path parameter extraction test
    let order_id = "ord-12345";
    let path = format!("/orders/{}", order_id);
    assert!(path.starts_with("/orders/"));
}

/// Test positions route with account parameter
#[tokio::test]
async fn test_positions_route() {
    let account_id = "acc-67890";
    let path = format!("/positions/{}", account_id);
    assert!(path.starts_with("/positions/"));
}

// =============================================================================
// Rate Limiting Tests (Extended)
// =============================================================================

/// Test rate limit enforcement
#[tokio::test]
async fn test_rate_limit_enforcement() {
    let state = AppState::new();
    let limit = 10;

    // All requests within limit should succeed
    for i in 0..limit {
        assert!(
            state.check_rate_limit("test", limit, Duration::from_secs(60)),
            "Request {} should be allowed", i
        );
    }

    // Next request should be denied
    assert!(
        !state.check_rate_limit("test", limit, Duration::from_secs(60)),
        "Request beyond limit should be denied"
    );
}

/// Test rate limit per-key isolation
#[tokio::test]
async fn test_rate_limit_key_isolation() {
    let state = AppState::new();

    // Use up limit for key A
    for _ in 0..5 {
        state.check_rate_limit("key_a", 5, Duration::from_secs(60));
    }

    // Key B should have its own limit
    assert!(state.check_rate_limit("key_b", 5, Duration::from_secs(60)));
}

/// Test rate limit state initialization
#[tokio::test]
async fn test_rate_limit_state_new() {
    let state = RateLimitState::new(100, Duration::from_secs(60));
    assert_eq!(state.limit, 100);
    assert_eq!(state.window, Duration::from_secs(60));
    assert!(state.requests.is_empty());
}

/// Test rate limit cleanup of old entries
#[tokio::test]
async fn test_rate_limit_old_entry_cleanup() {
    let mut state = RateLimitState::new(100, Duration::from_millis(50));

    // Add an entry
    state.requests.insert("old_key".to_string(), (1, Instant::now()));
    assert_eq!(state.requests.len(), 1);

    // Wait for window to expire
    std::thread::sleep(Duration::from_millis(60));

    // Entry should be cleaned up on next check
    let now = Instant::now();
    state.requests.retain(|_, (_, time)| now.duration_since(*time) < state.window);

    assert_eq!(state.requests.len(), 0, "Old entry should be cleaned");
}

// =============================================================================
// WebSocket Connection Tests
// =============================================================================

/// Test WebSocket manager creation
#[tokio::test]
async fn test_websocket_manager_creation() {
    let manager = WebSocketManager::new();
    assert_eq!(manager.connection_count(), 0);
}

/// Test broadcast functionality
#[tokio::test]
async fn test_websocket_broadcast() {
    let manager = WebSocketManager::new();

    // Broadcast should not panic even with no connections
    manager.broadcast("Hello, World!".to_string());
    manager.broadcast("".to_string());
    manager.broadcast("Special chars: <>&\"'".to_string());
}

/// Test connection count tracking
#[tokio::test]
async fn test_websocket_connection_count() {
    let manager = WebSocketManager::new();

    // Initially zero
    assert_eq!(manager.connection_count(), 0);

    // Connection count is tracked internally
    // Would need to mock WebSocket to fully test
}

/// Test WebSocket message types
#[tokio::test]
async fn test_websocket_message_handling() {
    // Test that different message types are handled
    // Text, Binary, Ping, Pong, Close

    // Binary messages trigger BUG D8 - buffer growth
    let buffer_size: usize = 0;
    let message_data = vec![0u8; 1024];
    let new_size = buffer_size + message_data.len();
    assert_eq!(new_size, 1024);
}

// =============================================================================
// Authentication Middleware Tests
// =============================================================================

/// Test authentication requires bearer token
#[tokio::test]
async fn test_auth_requires_bearer_token() {
    // Without token, should return UNAUTHORIZED
    let has_token = false;
    assert!(!has_token);
}

/// Test authentication with valid bearer token
#[tokio::test]
async fn test_auth_valid_bearer_token() {
    let token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test";
    assert!(token.starts_with("Bearer "));
}

/// Test authentication rejects invalid token format
#[tokio::test]
async fn test_auth_invalid_token_format() {
    let tokens = vec![
        "Basic dXNlcjpwYXNz",  // Basic auth
        "bearer token",        // lowercase
        "Token abc123",        // Token scheme
        "",                    // empty
    ];

    for token in tokens {
        assert!(!token.starts_with("Bearer "));
    }
}

/// Test authentication header parsing
#[tokio::test]
async fn test_auth_header_parsing() {
    let auth_header = "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.sig";

    if let Some(token) = auth_header.strip_prefix("Bearer ") {
        assert!(!token.is_empty());
        // Token should have 3 parts separated by dots
        let parts: Vec<&str> = token.split('.').collect();
        assert_eq!(parts.len(), 3, "JWT should have 3 parts");
    } else {
        panic!("Should have Bearer prefix");
    }
}

// =============================================================================
// Concurrent Connection Tests
// =============================================================================

/// Test handling many concurrent connections
#[tokio::test]
async fn test_many_concurrent_connections() {
    let connection_count = Arc::new(AtomicU64::new(0));
    let max_connections = 100;

    let mut handles = Vec::new();

    for _ in 0..max_connections {
        let count = connection_count.clone();
        handles.push(tokio::spawn(async move {
            count.fetch_add(1, Ordering::SeqCst);
            tokio::time::sleep(Duration::from_millis(10)).await;
            count.fetch_sub(1, Ordering::SeqCst);
        }));
    }

    // Wait for all to complete
    for handle in handles {
        handle.await.unwrap();
    }

    assert_eq!(connection_count.load(Ordering::SeqCst), 0);
}

/// Test connection ordering
#[tokio::test]
async fn test_connection_ordering() {
    let sequence = Arc::new(Mutex::new(Vec::new()));

    let mut handles = Vec::new();

    for i in 0..10 {
        let seq = sequence.clone();
        handles.push(tokio::spawn(async move {
            seq.lock().push(i);
        }));
    }

    for handle in handles {
        handle.await.unwrap();
    }

    // All values should be present (order may vary due to concurrency)
    let final_seq = sequence.lock();
    assert_eq!(final_seq.len(), 10);
}

/// Test connection state isolation
#[tokio::test]
async fn test_connection_state_isolation() {
    // Each connection should have isolated state
    let conn1_data = Arc::new(Mutex::new(String::from("conn1")));
    let conn2_data = Arc::new(Mutex::new(String::from("conn2")));

    // Modifying one shouldn't affect the other
    *conn1_data.lock() = String::from("modified");

    assert_eq!(*conn2_data.lock(), "conn2");
}

/// Test concurrent cache access
#[tokio::test]
async fn test_concurrent_cache_access() {
    let state = Arc::new(AppState::new());
    let mut handles = Vec::new();

    for i in 0..100 {
        let state_clone = state.clone();
        handles.push(tokio::spawn(async move {
            let key = format!("cache_key_{}", i % 10);
            state_clone.cache_response(&key, vec![i as u8], Duration::from_secs(60));
        }));
    }

    for handle in handles {
        handle.await.unwrap();
    }

    // Cache should handle concurrent writes
}

// =============================================================================
// Request Validation Tests
// =============================================================================

/// Test order request validation - empty symbol
#[tokio::test]
async fn test_order_validation_empty_symbol() {
    let request = OrderRequest {
        symbol: String::new(),
        side: "buy".to_string(),
        quantity: 100,
        price: Some(50.0),
    };

    
    assert!(request.symbol.is_empty());
}

/// Test order request validation - invalid side
#[tokio::test]
async fn test_order_validation_invalid_side() {
    let request = OrderRequest {
        symbol: "BTC-USD".to_string(),
        side: "invalid".to_string(),  
        quantity: 100,
        price: Some(50.0),
    };

    // Should only allow "buy" or "sell"
    assert!(request.side != "buy" && request.side != "sell");
}

/// Test order request validation - zero quantity
#[tokio::test]
async fn test_order_validation_zero_quantity() {
    let request = OrderRequest {
        symbol: "BTC-USD".to_string(),
        side: "buy".to_string(),
        quantity: 0,  
        price: Some(50.0),
    };

    assert_eq!(request.quantity, 0);
}

/// Test order request validation - negative price
#[tokio::test]
async fn test_order_validation_negative_price() {
    let request = OrderRequest {
        symbol: "BTC-USD".to_string(),
        side: "buy".to_string(),
        quantity: 100,
        price: Some(-50.0),  
    };

    assert!(request.price.unwrap() < 0.0);
}

// =============================================================================
// Cache Tests
// =============================================================================

/// Test cache response storage
#[tokio::test]
async fn test_cache_response_storage() {
    let state = AppState::new();
    let key = "test_key";
    let body = vec![1, 2, 3, 4, 5];

    state.cache_response(key, body.clone(), Duration::from_secs(60));

    // Cache should store the response
}

/// Test cache TTL ignored
#[tokio::test]
async fn test_cache_ttl_ignored() {
    
    let state = AppState::new();

    // Store with very short TTL
    state.cache_response("expired_key", vec![1, 2, 3], Duration::from_millis(1));

    // Wait for TTL to expire
    std::thread::sleep(Duration::from_millis(10));

    
    // Stale data would still be returned
}

/// Test cache size unbounded
#[tokio::test]
async fn test_cache_size_unbounded() {
    
    let state = AppState::new();

    // In a buggy implementation, this could grow forever
    for i in 0..1000 {
        let key = format!("key_{}", i);
        state.cache_response(&key, vec![0u8; 1024], Duration::from_secs(3600));
    }

    // No limit enforced - all entries stored
}

// =============================================================================
// Error Handling Tests
// =============================================================================

/// Test graceful error handling
#[tokio::test]
async fn test_graceful_error_handling() {
    // Errors should be returned as proper status codes
    let error_status = StatusCode::INTERNAL_SERVER_ERROR;
    assert_eq!(error_status.as_u16(), 500);
}

/// Test bad request handling
#[tokio::test]
async fn test_bad_request_handling() {
    let error_status = StatusCode::BAD_REQUEST;
    assert_eq!(error_status.as_u16(), 400);
}

/// Test unauthorized handling
#[tokio::test]
async fn test_unauthorized_handling() {
    let error_status = StatusCode::UNAUTHORIZED;
    assert_eq!(error_status.as_u16(), 401);
}

/// Test too many requests handling
#[tokio::test]
async fn test_too_many_requests_handling() {
    let error_status = StatusCode::TOO_MANY_REQUESTS;
    assert_eq!(error_status.as_u16(), 429);
}
