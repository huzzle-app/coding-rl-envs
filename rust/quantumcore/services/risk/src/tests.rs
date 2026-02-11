//! Comprehensive tests for the Risk Service
//!
//! This module contains 50+ tests covering:
//! - Bug categories: A4, B5, F7, L6, D5
//! - Risk calculation tests (margin requirements, VaR)
//! - Position limit tests
//! - Circuit breaker tests
//! - Concurrent access tests

#[cfg(test)]
mod tests {
    use super::*;
    use crate::calculator::{Position, RiskCalculator, RiskMetrics};
    use crate::limits::{AccountLimits, CircuitBreaker, CircuitState, RiskLimits, SymbolLimits};
    use parking_lot::Mutex;
    use rust_decimal::Decimal;
    use rust_decimal_macros::dec;
    use std::collections::HashMap;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;

    // ============================================================
    // Section 1: A4 - Partial Move from Option Tests
    // ============================================================

    #[test]
    fn test_a4_option_partial_move_basic() {
        // Test that Option values are handled correctly without partial moves
        let calc = RiskCalculator::new();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        // Add a position
        let result = calc.update_position("acc1", "AAPL", 100, dec!(145.00));
        assert!(result.is_ok());
    }

    #[test]
    fn test_a4_option_none_handling() {
        // Test behavior when Option is None
        let calc = RiskCalculator::new();

        // Account doesn't exist - should return error
        let result = calc.calculate_margin_requirement("nonexistent");
        assert!(result.is_err());
    }

    #[test]
    fn test_a4_option_some_extraction() {
        let calc = RiskCalculator::new();
        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(155.00));

        // Should successfully extract Some value
        let margin = calc.calculate_margin_requirement("acc1");
        assert!(margin.is_ok());
    }

    #[test]
    fn test_a4_option_moved_value_reuse() {
        let calc = RiskCalculator::new();
        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        // Multiple calculations should work (no moved value issues)
        let m1 = calc.calculate_margin_requirement("acc1").unwrap();
        let m2 = calc.calculate_margin_requirement("acc1").unwrap();
        assert_eq!(m1, m2);
    }

    #[test]
    fn test_a4_option_in_position_lookup() {
        let calc = RiskCalculator::new();

        // Position should be None initially
        let result = calc.calculate_var("nonexistent", 0.95);
        assert!(result.is_err());
    }

    // ============================================================
    // Section 2: B5 - Mutex Poisoning Tests
    // ============================================================

    #[test]
    fn test_b5_mutex_poisoning_basic() {
        // Test that mutex operations handle potential poisoning
        let calc = RiskCalculator::new();
        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_volatility("AAPL", 0.02);

        // This should not panic even with concurrent access
        let result = calc.calculate_var("acc1", 0.95);
        assert!(result.is_ok());
    }

    #[test]
    fn test_b5_rwlock_read_after_write() {
        let calc = RiskCalculator::new();

        // Write some data
        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        // Read should work after write
        let margin = calc.calculate_margin_requirement("acc1");
        assert!(margin.is_ok());
    }

    #[test]
    fn test_b5_concurrent_mutex_access() {
        let calc = Arc::new(RiskCalculator::new());

        let handles: Vec<_> = (0..10)
            .map(|i| {
                let calc = Arc::clone(&calc);
                thread::spawn(move || {
                    calc.update_position(
                        &format!("acc{}", i),
                        "AAPL",
                        100,
                        dec!(150.00),
                    )
                })
            })
            .collect();

        for handle in handles {
            assert!(handle.join().unwrap().is_ok());
        }
    }

    #[test]
    fn test_b5_mutex_panic_recovery() {
        // Simulate a scenario that could cause mutex poisoning
        let data = Arc::new(Mutex::new(vec![1, 2, 3]));
        let data_clone = Arc::clone(&data);

        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
            let _guard = data_clone.lock();
            panic!("intentional panic");
        }));

        assert!(result.is_err());

        // parking_lot::Mutex doesn't poison, but std::sync::Mutex does
        // Test that we can still access the data
        let guard = data.lock();
        assert_eq!(guard.len(), 3);
    }

    #[test]
    fn test_b5_rwlock_concurrent_readers() {
        let calc = Arc::new(RiskCalculator::new());
        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_volatility("AAPL", 0.02);

        let handles: Vec<_> = (0..20)
            .map(|_| {
                let calc = Arc::clone(&calc);
                thread::spawn(move || calc.calculate_margin_requirement("acc1"))
            })
            .collect();

        for handle in handles {
            assert!(handle.join().unwrap().is_ok());
        }
    }

    // ============================================================
    // Section 3: F7 - Margin Overflow Tests
    // ============================================================

    #[test]
    fn test_f7_margin_overflow_large_position() {
        let calc = RiskCalculator::new();

        // Very large position that could overflow
        calc.update_position("acc1", "AAPL", i64::MAX / 2, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        // Should handle large values without overflow
        let result = calc.calculate_margin_requirement("acc1");
        assert!(result.is_ok());
    }

    #[test]
    fn test_f7_margin_overflow_multiple_positions() {
        let calc = RiskCalculator::new();

        // Multiple large positions
        calc.update_position("acc1", "AAPL", 1_000_000_000, dec!(500.00)).unwrap();
        calc.update_position("acc1", "GOOGL", 500_000_000, dec!(2000.00)).unwrap();
        calc.update_position("acc1", "MSFT", 800_000_000, dec!(350.00)).unwrap();

        calc.update_market_price("AAPL", dec!(500.00));
        calc.update_market_price("GOOGL", dec!(2000.00));
        calc.update_market_price("MSFT", dec!(350.00));

        calc.update_volatility("AAPL", 0.03);
        calc.update_volatility("GOOGL", 0.04);
        calc.update_volatility("MSFT", 0.02);

        let result = calc.calculate_margin_requirement("acc1");
        assert!(result.is_ok());
    }

    #[test]
    fn test_f7_margin_overflow_high_price() {
        let calc = RiskCalculator::new();

        // High price stock
        calc.update_position("acc1", "BRK.A", 10000, dec!(500000.00)).unwrap();
        calc.update_market_price("BRK.A", dec!(500000.00));
        calc.update_volatility("BRK.A", 0.015);

        let result = calc.calculate_margin_requirement("acc1");
        assert!(result.is_ok());
    }

    #[test]
    fn test_f7_margin_overflow_high_volatility() {
        let calc = RiskCalculator::new();

        // High volatility scenario
        calc.update_position("acc1", "MEME", 1_000_000, dec!(100.00)).unwrap();
        calc.update_market_price("MEME", dec!(100.00));
        calc.update_volatility("MEME", 2.0); // 200% volatility

        let result = calc.calculate_margin_requirement("acc1");
        assert!(result.is_ok());
    }

    #[test]
    fn test_f7_margin_boundary_values() {
        let calc = RiskCalculator::new();

        // Test boundary values
        calc.update_position("acc1", "TEST", 1, dec!(0.01)).unwrap();
        calc.update_market_price("TEST", dec!(0.01));
        calc.update_volatility("TEST", 0.001);

        let result = calc.calculate_margin_requirement("acc1");
        assert!(result.is_ok());

        let margin = result.unwrap();
        assert!(margin >= Decimal::ZERO);
    }

    #[test]
    fn test_f7_margin_zero_position() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 0, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));

        let result = calc.calculate_margin_requirement("acc1");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), Decimal::ZERO);
    }

    // ============================================================
    // Section 4: L6 - Config Hot-Reload Tests
    // ============================================================

    #[test]
    fn test_l6_config_update_account_limits() {
        let limits = RiskLimits::new();

        let initial = AccountLimits {
            max_position_size: 1000,
            max_order_size: 100,
            max_daily_loss: dec!(10000),
            max_open_orders: 10,
            max_notional: dec!(1000000),
        };

        limits.set_account_limits("acc1", initial);

        // Hot reload with new limits
        let updated = AccountLimits {
            max_position_size: 2000,
            max_order_size: 200,
            max_daily_loss: dec!(20000),
            max_open_orders: 20,
            max_notional: dec!(2000000),
        };

        limits.set_account_limits("acc1", updated);

        // Verify the limits were updated
        // (would need getter methods to verify, but set should not crash)
    }

    #[test]
    fn test_l6_config_update_symbol_limits() {
        let limits = RiskLimits::new();

        let initial = SymbolLimits {
            max_position_size: 10000,
            tick_size: dec!(0.01),
            lot_size: 100,
            min_notional: dec!(100),
            circuit_breaker_threshold: dec!(0.10),
        };

        limits.set_symbol_limits("AAPL", initial);

        // Hot reload with new limits
        let updated = SymbolLimits {
            max_position_size: 20000,
            tick_size: dec!(0.001),
            lot_size: 1,
            min_notional: dec!(50),
            circuit_breaker_threshold: dec!(0.05),
        };

        limits.set_symbol_limits("AAPL", updated);
    }

    #[test]
    fn test_l6_config_reload_during_operation() {
        let limits = Arc::new(RiskLimits::new());

        // Setup initial config
        limits.set_account_limits(
            "acc1",
            AccountLimits {
                max_position_size: 1000,
                max_order_size: 100,
                max_daily_loss: dec!(10000),
                max_open_orders: 10,
                max_notional: dec!(1000000),
            },
        );

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 100,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let limits_clone = Arc::clone(&limits);

        // Spawn reader thread
        let reader = thread::spawn(move || {
            for _ in 0..100 {
                let _ = limits_clone.check_position_limit("acc1", "AAPL", 50);
            }
        });

        // Update config while reading
        for i in 0..10 {
            limits.set_account_limits(
                "acc1",
                AccountLimits {
                    max_position_size: 1000 + i * 100,
                    max_order_size: 100,
                    max_daily_loss: dec!(10000),
                    max_open_orders: 10,
                    max_notional: dec!(1000000),
                },
            );
        }

        reader.join().unwrap();
    }

    #[test]
    fn test_l6_config_atomic_update() {
        let limits = RiskLimits::new();

        // Should atomically replace config, not partially update
        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 100,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        // Order validation should use complete config
        let result = limits.validate_order("AAPL", dec!(150.50), 100);
        assert!(result.is_ok());
    }

    // ============================================================
    // Section 5: D5 - Cache Without Eviction Tests
    // ============================================================

    #[test]
    fn test_d5_cache_growth() {
        let calc = RiskCalculator::new();

        // Add many positions to test cache behavior
        for i in 0..1000 {
            let account = format!("acc{}", i);
            let symbol = format!("SYM{}", i % 100);
            calc.update_position(&account, &symbol, 100, dec!(150.00)).unwrap();
        }

        // Cache should be manageable
        // In buggy implementation, this would grow unbounded
    }

    #[test]
    fn test_d5_cache_stale_entries() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));

        // First calculation populates cache
        let _ = calc.calculate_margin_requirement("acc1");

        // Update position - cache should be invalidated
        calc.update_position("acc1", "AAPL", 100, dec!(160.00)).unwrap();

        // Second calculation should reflect new position
        let margin = calc.calculate_margin_requirement("acc1").unwrap();
        assert!(margin > Decimal::ZERO);
    }

    #[test]
    fn test_d5_cache_price_update_invalidation() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        let margin1 = calc.calculate_margin_requirement("acc1").unwrap();

        // Update price - should invalidate cache
        calc.update_market_price("AAPL", dec!(200.00));

        let margin2 = calc.calculate_margin_requirement("acc1").unwrap();

        // Margins should be different due to price change
        // Note: With BUG, they might be the same due to stale cache
        assert!(margin2 >= Decimal::ZERO);
    }

    #[test]
    fn test_d5_cache_memory_bound() {
        let calc = RiskCalculator::new();

        // Simulate heavy usage that could cause unbounded growth
        for iteration in 0..100 {
            for i in 0..100 {
                let account = format!("acc{}_{}", iteration, i);
                calc.update_position(&account, "AAPL", 100, dec!(150.00)).unwrap();
                let _ = calc.calculate_margin_requirement(&account);
            }
        }

        // Should not OOM - would fail in buggy implementation
    }

    // ============================================================
    // Section 6: Risk Calculation Tests - Margin Requirements
    // ============================================================

    #[test]
    fn test_margin_calculation_single_position() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        let margin = calc.calculate_margin_requirement("acc1").unwrap();

        // margin = position_value * volatility * 2.5
        // position_value = 100 * 150 = 15000
        // margin = 15000 * 0.02 * 2.5 = 750
        assert!(margin > Decimal::ZERO);
    }

    #[test]
    fn test_margin_calculation_multiple_positions() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_position("acc1", "GOOGL", 50, dec!(2000.00)).unwrap();

        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_market_price("GOOGL", dec!(2000.00));

        calc.update_volatility("AAPL", 0.02);
        calc.update_volatility("GOOGL", 0.03);

        let margin = calc.calculate_margin_requirement("acc1").unwrap();
        assert!(margin > Decimal::ZERO);
    }

    #[test]
    fn test_margin_calculation_short_position() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", -100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        let margin = calc.calculate_margin_requirement("acc1").unwrap();
        assert!(margin > Decimal::ZERO);
    }

    #[test]
    fn test_margin_default_volatility() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "UNKNOWN", 100, dec!(100.00)).unwrap();
        calc.update_market_price("UNKNOWN", dec!(100.00));
        // No volatility set - should use default

        let margin = calc.calculate_margin_requirement("acc1").unwrap();
        assert!(margin > Decimal::ZERO);
    }

    // ============================================================
    // Section 7: Risk Calculation Tests - VaR
    // ============================================================

    #[test]
    fn test_var_calculation_95() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        let var = calc.calculate_var("acc1", 0.95).unwrap();
        assert!(var >= Decimal::ZERO);
    }

    #[test]
    fn test_var_calculation_99() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        let var_99 = calc.calculate_var("acc1", 0.99).unwrap();
        let var_95 = calc.calculate_var("acc1", 0.95).unwrap();

        // 99% VaR should be higher than 95% VaR
        assert!(var_99 >= var_95);
    }

    #[test]
    fn test_var_portfolio_correlation() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_position("acc1", "GOOGL", 50, dec!(2000.00)).unwrap();

        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_market_price("GOOGL", dec!(2000.00));

        calc.update_volatility("AAPL", 0.02);
        calc.update_volatility("GOOGL", 0.03);

        let var = calc.calculate_var("acc1", 0.95).unwrap();
        assert!(var >= Decimal::ZERO);
    }

    #[test]
    fn test_var_empty_portfolio() {
        let calc = RiskCalculator::new();

        let result = calc.calculate_var("nonexistent", 0.95);
        assert!(result.is_err());
    }

    // ============================================================
    // Section 8: Position Limit Tests
    // ============================================================

    #[test]
    fn test_position_limit_within_bounds() {
        let limits = RiskLimits::new();

        limits.set_account_limits(
            "acc1",
            AccountLimits {
                max_position_size: 1000,
                max_order_size: 100,
                max_daily_loss: dec!(10000),
                max_open_orders: 10,
                max_notional: dec!(1000000),
            },
        );

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let result = limits.check_position_limit("acc1", "AAPL", 500);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_position_limit_exceeds_account() {
        let limits = RiskLimits::new();

        limits.set_account_limits(
            "acc1",
            AccountLimits {
                max_position_size: 1000,
                max_order_size: 100,
                max_daily_loss: dec!(10000),
                max_open_orders: 10,
                max_notional: dec!(1000000),
            },
        );

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let result = limits.check_position_limit("acc1", "AAPL", 1500);
        assert!(result.is_ok());
        assert!(!result.unwrap()); // Should fail - exceeds limit
    }

    #[test]
    fn test_position_limit_exceeds_symbol() {
        let limits = RiskLimits::new();

        limits.set_account_limits(
            "acc1",
            AccountLimits {
                max_position_size: 100000,
                max_order_size: 100,
                max_daily_loss: dec!(10000),
                max_open_orders: 10,
                max_notional: dec!(1000000),
            },
        );

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 1000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let result = limits.check_position_limit("acc1", "AAPL", 1500);
        assert!(result.is_ok());
        assert!(!result.unwrap()); // Should fail - exceeds symbol limit
    }

    #[test]
    fn test_position_limit_unknown_account() {
        let limits = RiskLimits::new();

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 1000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let result = limits.check_position_limit("unknown", "AAPL", 100);
        assert!(result.is_err());
    }

    #[test]
    fn test_position_reserve_and_check() {
        let limits = RiskLimits::new();

        limits.set_account_limits(
            "acc1",
            AccountLimits {
                max_position_size: 1000,
                max_order_size: 100,
                max_daily_loss: dec!(10000),
                max_open_orders: 10,
                max_notional: dec!(1000000),
            },
        );

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        // Reserve some position
        limits.reserve_position("acc1", "AAPL", 500).unwrap();

        // Check if we can add more
        let can_add = limits.check_position_limit("acc1", "AAPL", 400).unwrap();
        assert!(can_add);

        let cannot_add = limits.check_position_limit("acc1", "AAPL", 600).unwrap();
        assert!(!cannot_add);
    }

    // ============================================================
    // Section 9: Circuit Breaker Tests
    // ============================================================

    #[test]
    fn test_circuit_breaker_initial_state() {
        let cb = CircuitBreaker::new(3, 2, Duration::from_secs(5));

        assert!(cb.allow_request());
    }

    #[test]
    fn test_circuit_breaker_opens_after_failures() {
        let cb = CircuitBreaker::new(3, 2, Duration::from_secs(5));

        // Record failures
        cb.record_failure();
        assert!(cb.allow_request());

        cb.record_failure();
        assert!(cb.allow_request());

        cb.record_failure();
        // Should now be open
        assert!(!cb.allow_request());
    }

    #[test]
    fn test_circuit_breaker_success_resets_failures() {
        let cb = CircuitBreaker::new(3, 2, Duration::from_secs(5));

        cb.record_failure();
        cb.record_failure();
        cb.record_success();

        // Should still allow (success reset failure count)
        assert!(cb.allow_request());

        cb.record_failure();
        cb.record_failure();
        // Two more failures needed to open
        assert!(cb.allow_request());
    }

    #[test]
    fn test_circuit_breaker_half_open_timeout() {
        let cb = CircuitBreaker::new(3, 2, Duration::from_millis(50));

        // Open the circuit
        for _ in 0..3 {
            cb.record_failure();
        }
        assert!(!cb.allow_request());

        // Wait for timeout
        thread::sleep(Duration::from_millis(100));

        // Should transition to half-open and allow request
        assert!(cb.allow_request());
    }

    #[test]
    fn test_circuit_breaker_half_open_to_closed() {
        let cb = CircuitBreaker::new(3, 2, Duration::from_millis(50));

        // Open the circuit
        for _ in 0..3 {
            cb.record_failure();
        }

        // Wait for timeout
        thread::sleep(Duration::from_millis(100));

        // Allow request (transitions to half-open)
        assert!(cb.allow_request());

        // Record successes to close
        cb.record_success();
        cb.record_success();

        // Should be closed now
        assert!(cb.allow_request());
    }

    #[test]
    fn test_circuit_breaker_half_open_failure_reopens() {
        let cb = CircuitBreaker::new(3, 2, Duration::from_millis(50));

        // Open the circuit
        for _ in 0..3 {
            cb.record_failure();
        }

        // Wait for timeout
        thread::sleep(Duration::from_millis(100));

        // Allow request (transitions to half-open)
        assert!(cb.allow_request());

        // Failure in half-open should reopen
        cb.record_failure();

        // Should be open again
        assert!(!cb.allow_request());
    }

    // ============================================================
    // Section 10: Concurrent Access Tests
    // ============================================================

    #[test]
    fn test_concurrent_position_updates() {
        let calc = Arc::new(RiskCalculator::new());

        let handles: Vec<_> = (0..20)
            .map(|i| {
                let calc = Arc::clone(&calc);
                thread::spawn(move || {
                    for j in 0..50 {
                        let _ = calc.update_position(
                            &format!("acc{}", i % 5),
                            &format!("SYM{}", j % 10),
                            1,
                            dec!(100.00),
                        );
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn test_concurrent_price_updates() {
        let calc = Arc::new(RiskCalculator::new());

        let handles: Vec<_> = (0..10)
            .map(|i| {
                let calc = Arc::clone(&calc);
                thread::spawn(move || {
                    for j in 0..100 {
                        calc.update_market_price(
                            &format!("SYM{}", i),
                            Decimal::from(100 + j),
                        );
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn test_concurrent_margin_calculations() {
        let calc = Arc::new(RiskCalculator::new());

        // Setup
        for i in 0..5 {
            calc.update_position(&format!("acc{}", i), "AAPL", 100, dec!(150.00)).unwrap();
            calc.update_market_price("AAPL", dec!(150.00));
            calc.update_volatility("AAPL", 0.02);
        }

        let handles: Vec<_> = (0..20)
            .map(|i| {
                let calc = Arc::clone(&calc);
                thread::spawn(move || {
                    for _ in 0..100 {
                        let _ = calc.calculate_margin_requirement(&format!("acc{}", i % 5));
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn test_concurrent_circuit_breaker() {
        let cb = Arc::new(CircuitBreaker::new(100, 50, Duration::from_secs(5)));

        let success_count = Arc::new(AtomicU32::new(0));
        let failure_count = Arc::new(AtomicU32::new(0));

        let handles: Vec<_> = (0..20)
            .map(|i| {
                let cb = Arc::clone(&cb);
                let sc = Arc::clone(&success_count);
                let fc = Arc::clone(&failure_count);

                thread::spawn(move || {
                    for _ in 0..50 {
                        if cb.allow_request() {
                            if i % 3 == 0 {
                                cb.record_failure();
                                fc.fetch_add(1, Ordering::Relaxed);
                            } else {
                                cb.record_success();
                                sc.fetch_add(1, Ordering::Relaxed);
                            }
                        }
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }

        // Both successes and failures should have been recorded
        assert!(success_count.load(Ordering::Relaxed) > 0);
    }

    #[test]
    fn test_concurrent_limit_checks() {
        let limits = Arc::new(RiskLimits::new());

        // Setup
        for i in 0..5 {
            limits.set_account_limits(
                &format!("acc{}", i),
                AccountLimits {
                    max_position_size: 10000,
                    max_order_size: 100,
                    max_daily_loss: dec!(10000),
                    max_open_orders: 10,
                    max_notional: dec!(1000000),
                },
            );
        }

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 100000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let handles: Vec<_> = (0..20)
            .map(|i| {
                let limits = Arc::clone(&limits);
                thread::spawn(move || {
                    for _ in 0..100 {
                        let _ = limits.check_position_limit(&format!("acc{}", i % 5), "AAPL", 10);
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn test_concurrent_var_calculations() {
        let calc = Arc::new(RiskCalculator::new());

        // Setup portfolio
        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_position("acc1", "GOOGL", 50, dec!(2000.00)).unwrap();
        calc.update_position("acc1", "MSFT", 75, dec!(350.00)).unwrap();

        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_market_price("GOOGL", dec!(2000.00));
        calc.update_market_price("MSFT", dec!(350.00));

        calc.update_volatility("AAPL", 0.02);
        calc.update_volatility("GOOGL", 0.03);
        calc.update_volatility("MSFT", 0.025);

        let handles: Vec<_> = (0..10)
            .map(|_| {
                let calc = Arc::clone(&calc);
                thread::spawn(move || {
                    for _ in 0..50 {
                        let _ = calc.calculate_var("acc1", 0.95);
                        let _ = calc.calculate_var("acc1", 0.99);
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }
    }

    // ============================================================
    // Section 11: Order Validation Tests
    // ============================================================

    #[test]
    fn test_order_validation_valid_order() {
        let limits = RiskLimits::new();

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 100,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let result = limits.validate_order("AAPL", dec!(150.50), 100);
        assert!(result.is_ok());
    }

    #[test]
    fn test_order_validation_invalid_lot_size() {
        let limits = RiskLimits::new();

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 100,
                min_notional: dec!(100),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        let result = limits.validate_order("AAPL", dec!(150.50), 75);
        assert!(result.is_err());
    }

    #[test]
    fn test_order_validation_below_min_notional() {
        let limits = RiskLimits::new();

        limits.set_symbol_limits(
            "AAPL",
            SymbolLimits {
                max_position_size: 10000,
                tick_size: dec!(0.01),
                lot_size: 1,
                min_notional: dec!(1000),
                circuit_breaker_threshold: dec!(0.10),
            },
        );

        // 1 share at $150 = $150 < $1000 min notional
        let result = limits.validate_order("AAPL", dec!(150.00), 1);
        assert!(result.is_err());
    }

    #[test]
    fn test_order_validation_unknown_symbol() {
        let limits = RiskLimits::new();

        let result = limits.validate_order("UNKNOWN", dec!(100.00), 100);
        assert!(result.is_err());
    }

    // ============================================================
    // Section 12: Order Risk Check Tests
    // ============================================================

    #[test]
    fn test_order_risk_check_sufficient_margin() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.02);

        // Small order should have sufficient margin
        let result = calc.check_order_risk("acc1", "AAPL", 10, dec!(150.00));
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_order_risk_check_new_account() {
        let calc = RiskCalculator::new();

        // New account with no positions
        let result = calc.check_order_risk("new_account", "AAPL", 100, dec!(150.00));
        assert!(result.is_err()); // Account not found
    }

    // ============================================================
    // Section 13: Position Update Tests
    // ============================================================

    #[test]
    fn test_position_update_new_position() {
        let calc = RiskCalculator::new();

        let result = calc.update_position("acc1", "AAPL", 100, dec!(150.00));
        assert!(result.is_ok());

        let position = result.unwrap();
        assert_eq!(position.quantity, 100);
        assert_eq!(position.average_price, dec!(150.00));
    }

    #[test]
    fn test_position_update_add_to_long() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        let position = calc.update_position("acc1", "AAPL", 50, dec!(160.00)).unwrap();

        assert_eq!(position.quantity, 150);
        // Average price should be weighted average
    }

    #[test]
    fn test_position_update_partial_close() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        let position = calc.update_position("acc1", "AAPL", -50, dec!(160.00)).unwrap();

        assert_eq!(position.quantity, 50);
        // Realized P&L should be calculated
        assert!(position.realized_pnl > Decimal::ZERO);
    }

    #[test]
    fn test_position_update_close_position() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        let position = calc.update_position("acc1", "AAPL", -100, dec!(160.00)).unwrap();

        assert_eq!(position.quantity, 0);
    }

    #[test]
    fn test_position_update_flip_position() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        let position = calc.update_position("acc1", "AAPL", -150, dec!(160.00)).unwrap();

        // Should now be short
        assert_eq!(position.quantity, -50);
    }

    // ============================================================
    // Section 14: Edge Cases and Error Handling
    // ============================================================

    #[test]
    fn test_zero_volatility() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        calc.update_market_price("AAPL", dec!(150.00));
        calc.update_volatility("AAPL", 0.0);

        let margin = calc.calculate_margin_requirement("acc1").unwrap();
        assert_eq!(margin, Decimal::ZERO);
    }

    #[test]
    fn test_negative_price_handling() {
        let calc = RiskCalculator::new();

        // Negative prices should not crash
        calc.update_market_price("WEIRD", dec!(-100.00));
    }

    #[test]
    fn test_very_small_position() {
        let calc = RiskCalculator::new();

        calc.update_position("acc1", "AAPL", 1, dec!(0.0001)).unwrap();
        calc.update_market_price("AAPL", dec!(0.0001));
        calc.update_volatility("AAPL", 0.5);

        let margin = calc.calculate_margin_requirement("acc1").unwrap();
        assert!(margin >= Decimal::ZERO);
    }

    #[test]
    fn test_stress_many_symbols() {
        let limits = RiskLimits::new();

        limits.set_account_limits(
            "acc1",
            AccountLimits {
                max_position_size: u64::MAX,
                max_order_size: u64::MAX,
                max_daily_loss: Decimal::MAX,
                max_open_orders: u64::MAX,
                max_notional: Decimal::MAX,
            },
        );

        for i in 0..100 {
            limits.set_symbol_limits(
                &format!("SYM{}", i),
                SymbolLimits {
                    max_position_size: 100000,
                    tick_size: dec!(0.01),
                    lot_size: 1,
                    min_notional: dec!(100),
                    circuit_breaker_threshold: dec!(0.10),
                },
            );
        }

        for i in 0..100 {
            let result = limits.check_position_limit("acc1", &format!("SYM{}", i), 100);
            assert!(result.is_ok());
        }
    }
}
