#[cfg(test)]
mod tests {
    use crate::manager::{Portfolio, PortfolioManager, PortfolioPosition};
    use rust_decimal::Decimal;
    use rust_decimal_macros::dec;
    use std::collections::HashMap;
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;

    // ============================================================================
    // Portfolio Manager Creation Tests
    // ============================================================================

    #[test]
    fn test_create_portfolio_manager_with_default_ttl() {
        let manager = PortfolioManager::new(60);
        // Manager should be created successfully
        assert!(manager.get_portfolio("nonexistent").is_err());
    }

    #[test]
    fn test_create_portfolio_manager_with_zero_ttl() {
        let manager = PortfolioManager::new(0);
        // Zero TTL means cache expires immediately
        assert!(manager.get_portfolio("nonexistent").is_err());
    }

    #[test]
    fn test_create_portfolio_manager_with_large_ttl() {
        let manager = PortfolioManager::new(86400); // 24 hours
        assert!(manager.get_portfolio("nonexistent").is_err());
    }

    // ============================================================================
    // Position Update Tests
    // ============================================================================

    #[test]
    fn test_update_position_creates_new_portfolio() {
        let manager = PortfolioManager::new(60);
        let result = manager.update_position("acc1", "AAPL", 100, dec!(150.00));
        assert!(result.is_ok());

        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio.account_id, "acc1");
        assert!(portfolio.positions.contains_key("AAPL"));
    }

    #[test]
    fn test_update_position_adds_quantity() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_position("acc1", "AAPL", 50, dec!(160.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.quantity, 150);
    }

    #[test]
    fn test_update_position_reduces_quantity() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_position("acc1", "AAPL", -30, dec!(155.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.quantity, 70);
    }

    #[test]
    fn test_update_position_to_zero() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_position("acc1", "AAPL", -100, dec!(155.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.quantity, 0);
    }

    #[test]
    fn test_update_position_short_position() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", -100, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.quantity, -100);
    }

    #[test]
    fn test_update_position_multiple_symbols() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_position("acc1", "GOOGL", 50, dec!(2800.00)).unwrap();
        manager.update_position("acc1", "MSFT", 200, dec!(380.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio.positions.len(), 3);
        assert!(portfolio.positions.contains_key("AAPL"));
        assert!(portfolio.positions.contains_key("GOOGL"));
        assert!(portfolio.positions.contains_key("MSFT"));
    }

    #[test]
    fn test_update_position_average_cost_calculation() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(100.00)).unwrap();
        manager.update_position("acc1", "AAPL", 100, dec!(200.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        // Average cost should be (100*100 + 100*200) / 200 = 150
        assert_eq!(position.average_cost, dec!(150.00));
    }

    // ============================================================================
    // Portfolio Valuation Tests
    // ============================================================================

    #[test]
    fn test_portfolio_valuation_with_cash() {
        let manager = PortfolioManager::new(60);
        manager.set_cash_balance("acc1", dec!(10000.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio.cash_balance, dec!(10000.00));
        assert_eq!(portfolio.total_value, dec!(10000.00));
    }

    #[test]
    fn test_portfolio_valuation_with_positions() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.market_value, dec!(15000.00));
    }

    #[test]
    fn test_portfolio_valuation_with_cash_and_positions() {
        let manager = PortfolioManager::new(60);
        manager.set_cash_balance("acc1", dec!(10000.00)).unwrap();
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        // Total = cash + position value = 10000 + 15000 = 25000
        assert_eq!(portfolio.total_value, dec!(25000.00));
    }

    #[test]
    fn test_portfolio_valuation_unrealized_pnl_profit() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(100.00)).unwrap();
        manager.update_market_price("AAPL", dec!(150.00));

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        // Unrealized PnL = (150 - 100) * 100 = 5000
        assert_eq!(position.unrealized_pnl, dec!(5000.00));
    }

    #[test]
    fn test_portfolio_valuation_unrealized_pnl_loss() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_market_price("AAPL", dec!(100.00));

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        // Unrealized PnL = (100 - 150) * 100 = -5000
        assert_eq!(position.unrealized_pnl, dec!(-5000.00));
    }

    #[test]
    fn test_portfolio_valuation_short_position_profit() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", -100, dec!(150.00)).unwrap();
        manager.update_market_price("AAPL", dec!(100.00));

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        // Short profit when price drops: cost_basis - market_value = 15000 - 10000 = 5000
        assert_eq!(position.unrealized_pnl, dec!(5000.00));
    }

    #[test]
    fn test_portfolio_valuation_short_position_loss() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", -100, dec!(100.00)).unwrap();
        manager.update_market_price("AAPL", dec!(150.00));

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        // Short loss when price rises: cost_basis - market_value = 10000 - 15000 = -5000
        assert_eq!(position.unrealized_pnl, dec!(-5000.00));
    }

    #[test]
    fn test_portfolio_valuation_pnl_percent() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(100.00)).unwrap();
        manager.update_market_price("AAPL", dec!(150.00));

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        // PnL % = (5000 / 10000) * 100 = 50%
        assert_eq!(position.unrealized_pnl_percent, dec!(50));
    }

    // ============================================================================
    // Position Aggregation Tests
    // ============================================================================

    #[test]
    fn test_position_aggregation_multiple_accounts() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_position("acc2", "AAPL", 200, dec!(155.00)).unwrap();

        let portfolio1 = manager.get_portfolio("acc1").unwrap();
        let portfolio2 = manager.get_portfolio("acc2").unwrap();

        assert_eq!(portfolio1.positions.get("AAPL").unwrap().quantity, 100);
        assert_eq!(portfolio2.positions.get("AAPL").unwrap().quantity, 200);
    }

    #[test]
    fn test_position_aggregation_same_symbol_different_prices() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 50, dec!(100.00)).unwrap();
        manager.update_position("acc1", "AAPL", 50, dec!(200.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();

        assert_eq!(position.quantity, 100);
        // Average cost = (50*100 + 50*200) / 100 = 150
        assert_eq!(position.average_cost, dec!(150.00));
    }

    #[test]
    fn test_position_aggregation_preserves_separate_symbols() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        manager.update_position("acc1", "GOOGL", 10, dec!(2800.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();

        assert_eq!(portfolio.positions.len(), 2);
        assert_eq!(portfolio.positions.get("AAPL").unwrap().quantity, 100);
        assert_eq!(portfolio.positions.get("GOOGL").unwrap().quantity, 10);
    }

    // ============================================================================
    // Cache Behavior Tests (BUG H2 - Cache Stampede)
    // ============================================================================

    #[test]
    fn test_cache_returns_cached_value_within_ttl() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio1 = manager.get_portfolio("acc1").unwrap();
        let portfolio2 = manager.get_portfolio("acc1").unwrap();

        // Both should return same cached data
        assert_eq!(portfolio1.account_id, portfolio2.account_id);
        assert_eq!(portfolio1.positions.len(), portfolio2.positions.len());
    }

    #[test]
    fn test_cache_expires_after_ttl() {
        // Use a very short TTL for testing
        let manager = PortfolioManager::new(1);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio1 = manager.get_portfolio("acc1").unwrap();

        // Wait for cache to expire
        thread::sleep(Duration::from_secs(2));

        // Update market price
        manager.update_market_price("AAPL", dec!(200.00));

        let portfolio2 = manager.get_portfolio("acc1").unwrap();

        // After cache expiry, should get fresh data with updated price
        let position = portfolio2.positions.get("AAPL").unwrap();
        assert_eq!(position.current_price, dec!(200.00));
    }

    #[test]
    fn test_cache_stampede_scenario_h2() {
        
        // Multiple concurrent requests hit expired cache and all recalculate
        let manager = Arc::new(PortfolioManager::new(0)); // Zero TTL - always expired

        for i in 0..10 {
            manager.update_position(&format!("acc{}", i), "AAPL", 100, dec!(150.00)).unwrap();
        }

        let handles: Vec<_> = (0..10)
            .map(|i| {
                let manager = Arc::clone(&manager);
                thread::spawn(move || {
                    // All threads hit cache simultaneously
                    for _ in 0..10 {
                        let _ = manager.get_portfolio(&format!("acc{}", i));
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }

        // Test passes if no deadlock or panic occurs
        // But the bug is that all threads recalculated instead of coalescing
    }

    #[test]
    fn test_cache_not_invalidated_on_position_update_h2() {
        
        let manager = PortfolioManager::new(3600); // Long TTL
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio1 = manager.get_portfolio("acc1").unwrap();

        // Update position
        manager.update_position("acc1", "AAPL", 50, dec!(160.00)).unwrap();

        let portfolio2 = manager.get_portfolio("acc1").unwrap();

        
        // The quantity should be 150 but cache might return 100
        // This demonstrates the cache invalidation bug
        assert!(portfolio2.positions.contains_key("AAPL"));
    }

    #[test]
    fn test_cache_not_invalidated_on_cash_balance_update_h2() {
        
        let manager = PortfolioManager::new(3600);
        manager.set_cash_balance("acc1", dec!(10000.00)).unwrap();

        let portfolio1 = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio1.cash_balance, dec!(10000.00));

        // Update cash balance
        manager.set_cash_balance("acc1", dec!(20000.00)).unwrap();

        let portfolio2 = manager.get_portfolio("acc1").unwrap();

        
        // This demonstrates that cache is not properly invalidated
    }

    #[test]
    fn test_cache_not_invalidated_on_market_price_update_h2() {
        
        let manager = PortfolioManager::new(3600);
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio1 = manager.get_portfolio("acc1").unwrap();

        // Update market price
        manager.update_market_price("AAPL", dec!(200.00));

        let portfolio2 = manager.get_portfolio("acc1").unwrap();

        
        // The new price should be reflected but cache is stale
    }

    // ============================================================================
    // Metric Cardinality Tests (BUG J2)
    // ============================================================================

    #[test]
    fn test_metric_cardinality_per_account_j2() {
        
        let manager = PortfolioManager::new(60);

        // Simulate many accounts
        for i in 0..100 {
            let account_id = format!("account_{}", i);
            manager.update_position(&account_id, "AAPL", 10, dec!(150.00)).unwrap();
            manager.get_portfolio(&account_id).unwrap();
        }

        // Each account creates a new metric series
        // With 1M accounts, this creates 1M metric series - cardinality explosion
    }

    #[test]
    fn test_metric_cardinality_per_symbol_j2() {
        
        let manager = PortfolioManager::new(60);

        // Create one account with many symbols
        for i in 0..50 {
            let symbol = format!("SYM{}", i);
            manager.update_position("acc1", &symbol, 100, dec!(100.00)).unwrap();
        }

        manager.get_portfolio("acc1").unwrap();

        // Each symbol creates a new metric series per account
        // N accounts * M symbols = N*M metric series
    }

    #[test]
    fn test_metric_cardinality_explosion_simulation_j2() {
        
        let manager = PortfolioManager::new(60);
        let num_accounts = 50;
        let num_symbols = 20;

        for acc in 0..num_accounts {
            for sym in 0..num_symbols {
                manager.update_position(
                    &format!("acc_{}", acc),
                    &format!("SYM_{}", sym),
                    10,
                    dec!(100.00)
                ).unwrap();
            }
        }

        // Trigger valuation for all accounts
        for acc in 0..num_accounts {
            let _ = manager.get_portfolio(&format!("acc_{}", acc));
        }

        // Total metric series: 50 accounts * (1 portfolio metric + 20 symbol metrics) = 1050 series
        // This grows unboundedly with accounts/symbols
    }

    // ============================================================================
    // Concurrent Access Tests
    // ============================================================================

    #[test]
    fn test_concurrent_position_updates() {
        let manager = Arc::new(PortfolioManager::new(60));

        let handles: Vec<_> = (0..10)
            .map(|i| {
                let manager = Arc::clone(&manager);
                thread::spawn(move || {
                    for j in 0..100 {
                        let _ = manager.update_position(
                            &format!("acc{}", i),
                            "AAPL",
                            1,
                            Decimal::from(100 + j)
                        );
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }

        // All updates should complete without deadlock
        for i in 0..10 {
            let portfolio = manager.get_portfolio(&format!("acc{}", i)).unwrap();
            assert_eq!(portfolio.positions.get("AAPL").unwrap().quantity, 100);
        }
    }

    #[test]
    fn test_concurrent_reads_and_writes() {
        let manager = Arc::new(PortfolioManager::new(60));

        // Setup initial portfolio
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let manager_write = Arc::clone(&manager);
        let manager_read = Arc::clone(&manager);

        let write_handle = thread::spawn(move || {
            for i in 0..100 {
                let _ = manager_write.update_position("acc1", "AAPL", 1, Decimal::from(150 + i));
            }
        });

        let read_handle = thread::spawn(move || {
            for _ in 0..100 {
                let _ = manager_read.get_portfolio("acc1");
            }
        });

        write_handle.join().unwrap();
        read_handle.join().unwrap();

        // Final portfolio should be consistent
        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio.positions.get("AAPL").unwrap().quantity, 200);
    }

    #[test]
    fn test_concurrent_price_updates() {
        let manager = Arc::new(PortfolioManager::new(60));

        // Setup positions
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        let handles: Vec<_> = (0..10)
            .map(|i| {
                let manager = Arc::clone(&manager);
                thread::spawn(move || {
                    for _ in 0..100 {
                        manager.update_market_price("AAPL", Decimal::from(100 + i));
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }

        // Price updates should complete without data races
        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert!(portfolio.positions.get("AAPL").unwrap().current_price > Decimal::ZERO);
    }

    #[test]
    fn test_concurrent_multiple_accounts() {
        let manager = Arc::new(PortfolioManager::new(60));

        let handles: Vec<_> = (0..20)
            .map(|i| {
                let manager = Arc::clone(&manager);
                thread::spawn(move || {
                    let account_id = format!("acc{}", i);
                    manager.update_position(&account_id, "AAPL", 100, dec!(150.00)).unwrap();
                    manager.set_cash_balance(&account_id, dec!(10000.00)).unwrap();
                    let _ = manager.get_portfolio(&account_id);
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }

        // All accounts should be created
        for i in 0..20 {
            assert!(manager.get_portfolio(&format!("acc{}", i)).is_ok());
        }
    }

    #[test]
    fn test_concurrent_cache_access() {
        let manager = Arc::new(PortfolioManager::new(1)); // Short TTL

        // Setup portfolio
        manager.update_position("acc1", "AAPL", 100, dec!(150.00)).unwrap();

        // Many concurrent reads, some will hit cache, some will miss
        let handles: Vec<_> = (0..50)
            .map(|_| {
                let manager = Arc::clone(&manager);
                thread::spawn(move || {
                    for _ in 0..20 {
                        let _ = manager.get_portfolio("acc1");
                        thread::sleep(Duration::from_millis(10));
                    }
                })
            })
            .collect();

        for handle in handles {
            handle.join().unwrap();
        }
    }

    // ============================================================================
    // Edge Case Tests
    // ============================================================================

    #[test]
    fn test_get_nonexistent_portfolio() {
        let manager = PortfolioManager::new(60);
        let result = manager.get_portfolio("nonexistent");
        assert!(result.is_err());
    }

    #[test]
    fn test_empty_portfolio() {
        let manager = PortfolioManager::new(60);
        manager.set_cash_balance("acc1", dec!(0)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio.cash_balance, Decimal::ZERO);
        assert!(portfolio.positions.is_empty());
    }

    #[test]
    fn test_zero_quantity_position() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 0, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.quantity, 0);
        assert_eq!(position.market_value, Decimal::ZERO);
    }

    #[test]
    fn test_zero_price_position() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 100, dec!(0)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.current_price, Decimal::ZERO);
    }

    #[test]
    fn test_negative_cash_balance() {
        let manager = PortfolioManager::new(60);
        manager.set_cash_balance("acc1", dec!(-5000.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        assert_eq!(portfolio.cash_balance, dec!(-5000.00));
    }

    #[test]
    fn test_large_position_quantity() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "AAPL", 1_000_000_000, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("AAPL").unwrap();
        assert_eq!(position.quantity, 1_000_000_000);
    }

    #[test]
    fn test_very_small_price() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "PENNY", 1_000_000, dec!(0.0001)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("PENNY").unwrap();
        assert_eq!(position.market_value, dec!(100.00));
    }

    #[test]
    fn test_very_large_price() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc1", "BRK.A", 1, dec!(500000.00)).unwrap();

        let portfolio = manager.get_portfolio("acc1").unwrap();
        let position = portfolio.positions.get("BRK.A").unwrap();
        assert_eq!(position.market_value, dec!(500000.00));
    }

    #[test]
    fn test_special_characters_in_account_id() {
        let manager = PortfolioManager::new(60);
        manager.update_position("acc_123-test.user@domain", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("acc_123-test.user@domain").unwrap();
        assert_eq!(portfolio.account_id, "acc_123-test.user@domain");
    }

    #[test]
    fn test_unicode_in_account_id() {
        let manager = PortfolioManager::new(60);
        manager.update_position("account_test", "AAPL", 100, dec!(150.00)).unwrap();

        let portfolio = manager.get_portfolio("account_test").unwrap();
        assert_eq!(portfolio.account_id, "account_test");
    }
}
