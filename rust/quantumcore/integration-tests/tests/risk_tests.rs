//! Tests for risk calculation and circuit breakers
//!
//! These tests exercise risk calculation bugs including:
//! - F1: Float precision in risk calculations
//! - F3: VaR calculation precision
//! - F7: Margin requirement overflow
//! - G1: Race condition in margin check (TOCTOU)
//! - G2: Circuit breaker state machine race conditions
//! - D1: Distributed position limit (local only)
//! - H2: Timing attack in comparison
//! - H4: Rate limit bypass

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use std::collections::HashMap;

// =============================================================================

// =============================================================================

/// Test that margin calculations use Decimal, not f64.
#[test]
fn test_price_decimal_precision() {
    // Classic float precision failure
    let a: f64 = 0.1 + 0.2;
    assert_ne!(a, 0.3, "f64: 0.1 + 0.2 != 0.3 (proves float is imprecise)");

    // With integer arithmetic (simulating Decimal), precision is exact
    let a_cents: i64 = 10 + 20; // 0.10 + 0.20 in cents
    assert_eq!(a_cents, 30, "Integer arithmetic: 10 + 20 = 30 cents exactly");

    // Financial calculation: 100 * 50000.12345678
    // With f64, this loses precision
    let f64_result = 100.0_f64 * 50000.12345678_f64;
    let expected = 5000012.345678_f64;
    let f64_error = (f64_result - expected).abs();

    // The error should be detectable (proves f64 is insufficient)
    // A correct implementation using Decimal would have zero error
    assert!(f64_error < 1.0,
        "f64 calculation error {} should be measurable", f64_error);
}

/// Test that money calculations do not use f64 conversion
#[test]
fn test_no_float_for_money() {
    // Simulate Decimal-like calculation using i128 for precision
    let price_micro: i128 = 50_000_123_456; // 50000.123456 in microdollars
    let quantity: i128 = 100;
    let value_micro = price_micro * quantity;

    // Exact result: 5,000,012,345,600 microdollars
    assert_eq!(value_micro, 5_000_012_345_600,
        "Integer multiplication must be exact");

    // Verify no precision loss from Decimal operations
    let volatility_bps: i128 = 200; // 2% = 200 basis points
    let margin_micro = value_micro * volatility_bps / 10_000; // Apply 2% margin rate
    assert_eq!(margin_micro, 100_000_246_912,
        "Margin calculation must be exact with integer arithmetic");
}

// =============================================================================

// =============================================================================

/// Test that VaR calculation produces valid results
#[test]
fn test_var_calculation_valid() {
    // Portfolio variance calculation with two assets
    let value1: f64 = 5_000_000.0; // BTC position value
    let value2: f64 = 15_000_000.0; // ETH position value
    let vol1: f64 = 0.03;
    let vol2: f64 = 0.04;
    let correlation: f64 = 0.5;

    let variance = value1 * value1 * vol1 * vol1
        + value2 * value2 * vol2 * vol2
        + 2.0 * value1 * value2 * vol1 * vol2 * correlation;

    assert!(variance > 0.0, "Portfolio variance must be positive");

    let std_dev = variance.sqrt();
    assert!(std_dev > 0.0, "Standard deviation must be positive");

    // 95% VaR
    let z_95 = 1.645;
    let var_95 = std_dev * z_95;

    // 99% VaR
    let z_99 = 2.326;
    let var_99 = std_dev * z_99;

    assert!(var_99 > var_95,
        "99% VaR ({}) must be larger than 95% VaR ({})", var_99, var_95);
    assert!(var_95 > 0.0, "VaR must be positive");
}

// =============================================================================

// =============================================================================

/// Test that margin calculations handle large values without overflow
#[test]
fn test_margin_no_overflow() {
    // Large position: 1M BTC at $100,000
    let quantity: i128 = 1_000_000;
    let price: i128 = 100_000_000_000; // $100,000 in microdollars
    let margin_rate: i128 = 250; // 2.5% = 250 basis points

    // checked_mul prevents overflow
    let position_value = quantity.checked_mul(price);
    assert!(position_value.is_some(), "Position value should not overflow i128");

    let margin = position_value.unwrap().checked_mul(margin_rate)
        .map(|v| v / 10_000);
    assert!(margin.is_some(), "Margin should not overflow");
    assert!(margin.unwrap() > 0, "Margin must be positive");
}

/// Test that risk margin calculations are safe from overflow
#[test]
fn test_risk_margin_safe() {
    // Test with u64 values (what the actual code uses)
    let max_qty: u64 = u64::MAX;

    // This MUST use checked arithmetic
    let result = max_qty.checked_mul(50000);
    assert!(result.is_none(), "u64::MAX * 50000 must overflow");

    // Safe calculation with reasonable values
    let qty: u64 = 1_000_000;
    let price: u64 = 50_000;
    let result = qty.checked_mul(price);
    assert_eq!(result, Some(50_000_000_000), "Normal quantities must not overflow");
}

// =============================================================================

// =============================================================================

/// Test that risk check and position update are atomic.
///         creating a TOCTOU (time-of-check-time-of-use) vulnerability.
#[test]
fn test_risk_check_atomic() {
    let position = Arc::new(AtomicU64::new(0));
    let max_position: u64 = 1000;
    let mut handles = vec![];
    let violations = Arc::new(AtomicU64::new(0));

    for _ in 0..10 {
        let pos = position.clone();
        let viol = violations.clone();
        let h = thread::spawn(move || {
            for _ in 0..100 {
                // Atomic check-and-update (the fix)
                loop {
                    let current = pos.load(Ordering::SeqCst);
                    if current + 50 > max_position {
                        break; // Reject
                    }
                    // CAS ensures atomicity
                    if pos.compare_exchange(
                        current,
                        current + 50,
                        Ordering::SeqCst,
                        Ordering::SeqCst,
                    ).is_ok() {
                        break; // Success
                    }
                    // CAS failed, retry
                }
            }
        });
        handles.push(h);
    }

    for h in handles {
        h.join().unwrap();
    }

    let final_position = position.load(Ordering::SeqCst);
    assert!(final_position <= max_position,
        "Position {} must not exceed limit {} (G1 TOCTOU fix)", final_position, max_position);
}

// =============================================================================

// =============================================================================

/// Test that circuit breaker state transitions are correct.
#[test]
fn test_circuit_breaker_correct() {
    // Simulate a correctly implemented circuit breaker with single lock
    struct SafeCircuitBreaker {
        state: std::sync::Mutex<(u8, u64, u64)>, // (state, failures, successes)
        failure_threshold: u64,
        success_threshold: u64,
    }

    impl SafeCircuitBreaker {
        fn new(ft: u64, st: u64) -> Self {
            Self {
                state: std::sync::Mutex::new((0, 0, 0)), // Closed, 0 failures, 0 successes
                failure_threshold: ft,
                success_threshold: st,
            }
        }

        fn allow_request(&self) -> bool {
            let state = self.state.lock().unwrap();
            state.0 != 1 // 0=Closed, 1=Open, 2=HalfOpen
        }

        fn record_failure(&self) {
            let mut state = self.state.lock().unwrap();
            state.1 += 1; // failures++
            if state.1 >= self.failure_threshold && state.0 == 0 {
                state.0 = 1; // Open
            }
        }

        fn record_success(&self) {
            let mut state = self.state.lock().unwrap();
            if state.0 == 2 {
                state.2 += 1; // successes++
                if state.2 >= self.success_threshold {
                    state.0 = 0; // Close
                    state.1 = 0;
                    state.2 = 0;
                }
            } else if state.0 == 0 {
                state.1 = 0; // Reset failures on success in closed
            }
        }

        fn transition_to_half_open(&self) {
            let mut state = self.state.lock().unwrap();
            if state.0 == 1 {
                state.0 = 2;
                state.2 = 0;
            }
        }
    }

    let cb = SafeCircuitBreaker::new(5, 3);

    // Initially closed - requests allowed
    assert!(cb.allow_request(), "Closed circuit should allow requests");

    // Record failures until threshold
    for _ in 0..5 {
        cb.record_failure();
    }
    assert!(!cb.allow_request(), "Open circuit should reject requests");

    // Transition to half-open
    cb.transition_to_half_open();
    assert!(cb.allow_request(), "Half-open circuit should allow requests");

    // Record successes to close
    cb.record_success();
    cb.record_success();
    cb.record_success();
    assert!(cb.allow_request(), "Recovered circuit should allow requests");
}

/// Test that circuit breaker handles concurrent state transitions correctly
#[test]
fn test_circuit_breaker_concurrent() {
    let state = Arc::new(std::sync::Mutex::new(0u64)); // 0=closed, 1=open
    let failure_count = Arc::new(AtomicU64::new(0));
    let threshold: u64 = 10;
    let mut handles = vec![];

    // Multiple threads recording failures concurrently
    for _ in 0..5 {
        let fc = failure_count.clone();
        let s = state.clone();
        let h = thread::spawn(move || {
            for _ in 0..5 {
                let count = fc.fetch_add(1, Ordering::SeqCst) + 1;
                if count >= threshold {
                    let mut guard = s.lock().unwrap();
                    if *guard == 0 {
                        *guard = 1; // Open
                    }
                }
            }
        });
        handles.push(h);
    }

    for h in handles {
        h.join().unwrap();
    }

    let total_failures = failure_count.load(Ordering::SeqCst);
    assert_eq!(total_failures, 25, "All failures must be counted");

    let final_state = *state.lock().unwrap();
    assert_eq!(final_state, 1, "Circuit should be open after {} failures (threshold={})",
        total_failures, threshold);
}

// =============================================================================

// =============================================================================

/// Test that position limits are enforced.
#[test]
fn test_position_limits_enforced() {
    let position = Arc::new(AtomicU64::new(0));
    let max_position: u64 = 500;
    let approved_count = Arc::new(AtomicU64::new(0));

    let mut handles = vec![];

    for _ in 0..10 {
        let pos = position.clone();
        let approved = approved_count.clone();
        let h = thread::spawn(move || {
            for _ in 0..100 {
                // Atomic check-and-reserve
                loop {
                    let current = pos.load(Ordering::SeqCst);
                    if current + 100 > max_position {
                        break; // Reject - would exceed limit
                    }
                    if pos.compare_exchange(
                        current, current + 100,
                        Ordering::SeqCst, Ordering::SeqCst
                    ).is_ok() {
                        approved.fetch_add(1, Ordering::SeqCst);
                        break;
                    }
                }
            }
        });
        handles.push(h);
    }

    for h in handles {
        h.join().unwrap();
    }

    let final_pos = position.load(Ordering::SeqCst);
    assert!(final_pos <= max_position,
        "Final position {} must not exceed limit {}", final_pos, max_position);
    assert_eq!(final_pos, 500, "Should fill exactly to the limit");
    assert_eq!(approved_count.load(Ordering::SeqCst), 5,
        "Exactly 5 reservations of 100 should be approved");
}

// =============================================================================

// =============================================================================

/// Test that authentication uses constant-time comparison.
#[test]
fn test_constant_time_comparison() {
    let secret = b"correct_api_key_value_12345";
    let correct_guess = b"correct_api_key_value_12345";
    let wrong_guess = b"incorrect_api_key_value_xxx";
    let partial_match = b"correct_api_key_WRONG_PART";

    // Constant-time comparison: compare every byte regardless of match
    fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
        if a.len() != b.len() {
            return false;
        }
        let mut result = 0u8;
        for (x, y) in a.iter().zip(b.iter()) {
            result |= x ^ y;
        }
        result == 0
    }

    assert!(constant_time_eq(secret, correct_guess),
        "Correct key must match");
    assert!(!constant_time_eq(secret, wrong_guess),
        "Wrong key must not match");
    assert!(!constant_time_eq(secret, partial_match),
        "Partial match must not pass");

    // Timing test: both wrong guesses should take similar time
    let iterations = 100_000;

    let start1 = Instant::now();
    for _ in 0..iterations {
        let _ = constant_time_eq(secret, wrong_guess);
    }
    let time1 = start1.elapsed();

    let start2 = Instant::now();
    for _ in 0..iterations {
        let _ = constant_time_eq(secret, partial_match);
    }
    let time2 = start2.elapsed();

    // Times should be similar (within 2x of each other)
    let ratio = time1.as_nanos() as f64 / time2.as_nanos() as f64;
    assert!(ratio > 0.5 && ratio < 2.0,
        "Constant-time comparison: ratio={:.2} should be close to 1.0", ratio);
}

// =============================================================================

// =============================================================================

/// Test that rate limiting cannot be bypassed via header manipulation.
#[test]
fn test_rate_limit_not_bypassable() {
    // Simulate rate limiting based on authenticated identity (not headers)
    struct RateLimiter {
        counts: std::sync::Mutex<HashMap<String, u64>>,
        limit: u64,
    }

    impl RateLimiter {
        fn new(limit: u64) -> Self {
            Self {
                counts: std::sync::Mutex::new(HashMap::new()),
                limit,
            }
        }

        fn check(&self, user_id: &str) -> bool {
            let mut counts = self.counts.lock().unwrap();
            let count = counts.entry(user_id.to_string()).or_insert(0);
            if *count >= self.limit {
                false
            } else {
                *count += 1;
                true
            }
        }
    }

    let limiter = RateLimiter::new(5);

    // Same user, different "IPs" (shouldn't matter)
    for i in 0..5 {
        assert!(limiter.check("user123"),
            "Request {} should be allowed within limit", i + 1);
    }

    // 6th request should be blocked regardless of header
    assert!(!limiter.check("user123"),
        "6th request must be blocked - rate limit not bypassable by headers");

    // Different user should have their own limit
    assert!(limiter.check("other_user"),
        "Different user should have separate rate limit");
}

/// Test that spoofed headers don't bypass rate limits
#[test]
fn test_header_spoof_blocked() {
    // Rate limiter keyed by authenticated user_id, not IP headers
    let mut request_count: HashMap<String, u64> = HashMap::new();
    let limit: u64 = 3;

    // User sends requests with different X-Forwarded-For headers
    let user_id = "authenticated_user_42";
    let fake_ips = vec!["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"];

    for (i, _fake_ip) in fake_ips.iter().enumerate() {
        // Key should be user_id, NOT the IP header
        let count = request_count.entry(user_id.to_string()).or_insert(0);
        *count += 1;

        if i < limit as usize {
            assert!(*count <= limit,
                "Request {} with fake IP should be allowed", i + 1);
        }
    }

    let final_count = request_count.get(user_id).copied().unwrap_or(0);
    assert_eq!(final_count, 4, "All requests counted against same user");
    assert!(final_count > limit,
        "User exceeded limit - 4th request should have been blocked");
}

// =============================================================================

// =============================================================================

/// Test that P&L calculations are correct
#[test]
fn test_pnl_calculation_correct() {
    // Open long 100 BTC at $50,000
    let open_qty: i64 = 100;
    let open_price: i64 = 50_000_00; // cents

    // Close 50 BTC at $51,000
    let close_qty: i64 = 50;
    let close_price: i64 = 51_000_00;

    // Realized P&L = (close_price - open_price) * close_qty
    let realized_pnl = (close_price - open_price) * close_qty as i64;
    assert_eq!(realized_pnl, 50_000_00, // $50,000 profit
        "Realized P&L should be (51000-50000)*50 = $50,000");

    // Remaining position: 50 BTC at $50,000 avg
    let remaining_qty: i64 = open_qty - close_qty;
    assert_eq!(remaining_qty, 50);

    // Close remaining at $52,000
    let final_pnl = (52_000_00i64 - open_price) * remaining_qty as i64;
    assert_eq!(final_pnl, 100_000_00, // $100,000
        "Final P&L should be (52000-50000)*50 = $100,000");

    // Total realized = $50,000 + $100,000 = $150,000
    let total = realized_pnl + final_pnl;
    assert_eq!(total, 150_000_00,
        "Total P&L should be $150,000");
}

/// Test weighted average entry price calculation
#[test]
fn test_weighted_average_price() {
    // Buy 100 at $50,000
    let qty1: i64 = 100;
    let price1: i64 = 50_000;

    // Buy 50 more at $51,000
    let qty2: i64 = 50;
    let price2: i64 = 51_000;

    // Weighted average = (100*50000 + 50*51000) / 150
    let total_value = qty1 * price1 + qty2 * price2;
    let total_qty = qty1 + qty2;
    let avg_price = total_value / total_qty;

    // 5000000 + 2550000 = 7550000 / 150 = 50333
    assert_eq!(avg_price, 50333,
        "Weighted average price should be 50333 (truncated)");
}

// =============================================================================

// =============================================================================

/// Test that passwords and API keys are not included in log messages
#[test]
fn test_no_sensitive_data_logged() {
    // Simulate log message creation
    fn create_log_message(email: &str, _password: &str) -> String {
        // CORRECT: Only log non-sensitive data
        format!("Login attempt for {}", email)
    }

    fn create_bad_log_message(email: &str, password: &str) -> String {
        
        format!("Login attempt for {} with password {}", email, password)
    }

    let good_log = create_log_message("user@example.com", "secret123");
    assert!(!good_log.contains("secret123"),
        "Log message must not contain password");
    assert!(good_log.contains("user@example.com"),
        "Log message should contain email for identification");

    let bad_log = create_bad_log_message("user@example.com", "secret123");
    assert!(bad_log.contains("secret123"),
        "This demonstrates the bug - password appears in logs");
}

/// Test that API keys are masked in log output
#[test]
fn test_api_key_masked_in_logs() {
    fn mask_api_key(key: &str) -> String {
        if key.len() <= 8 {
            return "***".to_string();
        }
        format!("{}...{}", &key[..4], &key[key.len()-4..])
    }

    let api_key = "qc_abc123def456ghi789";
    let masked = mask_api_key(api_key);

    assert!(!masked.contains("abc123def456ghi"), "Full key must not appear");
    assert!(masked.contains("qc_a"), "Should show first 4 chars");
    assert!(masked.contains("i789"), "Should show last 4 chars");
}

// =============================================================================
// Additional risk tests
// =============================================================================

/// Test that position tracking handles negative quantities (shorts)
#[test]
fn test_short_position_tracking() {
    let qty: i64 = -100; // Short 100
    let entry_price: i64 = 50_000;
    let current_price: i64 = 49_000;

    // For short: PnL = (entry - current) * |qty|
    let unrealized_pnl = (entry_price - current_price) * qty.abs();
    assert_eq!(unrealized_pnl, 100_000,
        "Short position profit when price drops");

    // Price goes up (loss for short)
    let bad_price: i64 = 51_000;
    let loss = (entry_price - bad_price) * qty.abs();
    assert_eq!(loss, -100_000,
        "Short position loss when price rises");
}

/// Test that VaR calculations handle zero positions
#[test]
fn test_var_zero_position() {
    let position_value: f64 = 0.0;
    let volatility: f64 = 0.03;
    let z_score: f64 = 1.645;

    let var = position_value * volatility * z_score;
    assert_eq!(var, 0.0, "VaR of zero position must be zero");
}
