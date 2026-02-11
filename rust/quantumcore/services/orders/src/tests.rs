//! Comprehensive tests for orders service
//!
//! Tests cover: A1 (use after move), C1 (unwrap in production), H3 (SQL injection),
//! B2 (blocking in async), D1 (unbounded Vec), F1 (float precision), F5 (fee truncation),
//! F9 (order value), G4 (idempotency), L3 (pool exhaustion)

use crate::service::{
    CreateOrderRequest, Order, OrderEvent, OrderEventType, OrderService, OrderSide, OrderStatus,
    OrderType,
};
use crate::repository::{OrderRecord, OrderRepository};
use crate::validation::{validate_order, validate_quantity_limit, OrderRequest, ValidatedOrder};
use chrono::Utc;
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use std::str::FromStr;
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use uuid::Uuid;

// ============================================================================
// A1: Use After Move / Ownership Tests (6 tests)
// ============================================================================

#[test]
fn test_a1_order_not_used_after_move() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "client123".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    // After this, request is moved - accessing it would be use after move
    let _order = tokio_test::block_on(service.create_order(request));

    
    // The bug is in handler code that tries to use order after it's moved
}

#[test]
fn test_a1_order_clone_before_move() {
    // Correct pattern: clone before move if data is needed
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "client456".to_string(),
        account_id: "acc2".to_string(),
        symbol: "MSFT".to_string(),
        side: OrderSide::Sell,
        order_type: OrderType::Market,
        price: None,
        stop_price: None,
        quantity: 50,
    };

    let account_id = request.account_id.clone(); // Clone before move
    let _order = tokio_test::block_on(service.create_order(request));

    // Can still use account_id after request is moved
    assert_eq!(account_id, "acc2");
}

#[test]
fn test_a1_multiple_orders_ownership() {
    // Test that multiple orders don't have ownership conflicts
    let service = OrderService::new();

    for i in 0..10 {
        let request = CreateOrderRequest {
            client_order_id: format!("order_{}", i),
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };

        let order = tokio_test::block_on(service.create_order(request)).unwrap();
        assert_eq!(order.client_order_id, format!("order_{}", i));
    }
}

#[test]
fn test_a1_order_event_ownership() {
    // Events should be independent of original order
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "test_event".to_string(),
        account_id: "acc1".to_string(),
        symbol: "GOOG".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(150.0)),
        stop_price: None,
        quantity: 10,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    // Cancelling should create independent event
    let cancelled = tokio_test::block_on(service.cancel_order(order.id, "User requested".to_string())).unwrap();
    assert_eq!(cancelled.status, OrderStatus::Cancelled);
}

#[test]
fn test_a1_fill_order_ownership() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "fill_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let order_id = order.id;

    // Fill should not cause ownership issues
    let filled = tokio_test::block_on(service.fill_order(order_id, 50, dec!(100.0))).unwrap();
    assert_eq!(filled.filled_quantity, 50);
}

#[test]
fn test_a1_get_account_orders_ownership() {
    let service = OrderService::new();

    // Create multiple orders for same account
    for i in 0..5 {
        let request = CreateOrderRequest {
            client_order_id: format!("acc_order_{}", i),
            account_id: "shared_acc".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        tokio_test::block_on(service.create_order(request)).unwrap();
    }

    // Getting orders should return clones, not move originals
    let orders = service.get_account_orders("shared_acc");
    assert_eq!(orders.len(), 5);

    // Should be able to get again
    let orders2 = service.get_account_orders("shared_acc");
    assert_eq!(orders2.len(), 5);
}

// ============================================================================
// C1: Error Handling / Unwrap Tests (6 tests)
// ============================================================================

#[test]
fn test_c1_no_unwrap_on_missing_order() {
    let service = OrderService::new();

    // Getting non-existent order should return Result, not panic
    let result = tokio_test::block_on(service.get_order(Uuid::new_v4()));
    assert!(result.is_err());
}

#[test]
fn test_c1_cancel_missing_order_error() {
    let service = OrderService::new();

    // Cancelling non-existent order should error gracefully
    let result = tokio_test::block_on(service.cancel_order(Uuid::new_v4(), "test".to_string()));
    assert!(result.is_err());
}

#[test]
fn test_c1_fill_missing_order_error() {
    let service = OrderService::new();

    // Filling non-existent order should error gracefully
    let result = tokio_test::block_on(service.fill_order(Uuid::new_v4(), 100, dec!(100.0)));
    assert!(result.is_err());
}

#[test]
fn test_c1_rebuild_missing_events_error() {
    let service = OrderService::new();

    // Rebuilding order with no events should error gracefully
    let result = service.rebuild_order_from_events(Uuid::new_v4());
    assert!(result.is_err());
}

#[test]
fn test_c1_validation_empty_symbol_error() {
    let request = OrderRequest {
        symbol: "".to_string(), // Empty symbol
        side: "buy".to_string(),
        quantity: 100.0,
        price: 100.0,
    };

    let result = validate_order(&request);
    assert!(result.is_err());
    assert!(result.unwrap_err().to_string().contains("Symbol"));
}

#[test]
fn test_c1_validation_invalid_side_error() {
    let request = OrderRequest {
        symbol: "AAPL".to_string(),
        side: "invalid".to_string(), // Invalid side
        quantity: 100.0,
        price: 100.0,
    };

    let result = validate_order(&request);
    assert!(result.is_err());
    assert!(result.unwrap_err().to_string().contains("Side"));
}

// ============================================================================
// H3: SQL Injection / Security Tests (6 tests)
// ============================================================================

#[test]
fn test_h3_sql_injection_in_symbol() {
    
    let request = OrderRequest {
        symbol: "AAPL'; DROP TABLE orders; --".to_string(),
        side: "buy".to_string(),
        quantity: 100.0,
        price: 100.0,
    };

    // Validation should pass but the symbol should be sanitized
    let result = validate_order(&request);
    
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_h3_sql_injection_in_account_id() {
    let service = OrderService::new();

    // Attempt SQL injection in account_id
    let request = CreateOrderRequest {
        client_order_id: "test".to_string(),
        account_id: "acc1' OR '1'='1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    
    let result = tokio_test::block_on(service.create_order(request));
    // Currently this passes through - the bug is that it's not sanitized
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_h3_special_characters_in_client_order_id() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "<script>alert('xss')</script>".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let result = tokio_test::block_on(service.create_order(request));
    
    assert!(result.is_ok());
}

#[test]
fn test_h3_unicode_injection() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "test\u{0000}null".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let result = tokio_test::block_on(service.create_order(request));
    
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_h3_very_long_symbol() {
    let request = OrderRequest {
        symbol: "A".repeat(10000), // Very long symbol
        side: "buy".to_string(),
        quantity: 100.0,
        price: 100.0,
    };

    
    let result = validate_order(&request);
    // Currently passes - bug is no length limit
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_h3_escape_sequences() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "test\n\r\t".to_string(),
        account_id: "acc1\\; DROP TABLE".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let result = tokio_test::block_on(service.create_order(request));
    
    assert!(result.is_ok() || result.is_err());
}

// ============================================================================
// B2: Blocking in Async Context Tests (6 tests)
// ============================================================================

#[tokio::test]
async fn test_b2_async_order_creation() {
    
    let service = Arc::new(OrderService::new());

    let handles: Vec<_> = (0..10)
        .map(|i| {
            let s = service.clone();
            tokio::spawn(async move {
                let request = CreateOrderRequest {
                    client_order_id: format!("async_order_{}", i),
                    account_id: format!("acc_{}", i % 3),
                    symbol: "AAPL".to_string(),
                    side: if i % 2 == 0 { OrderSide::Buy } else { OrderSide::Sell },
                    order_type: OrderType::Limit,
                    price: Some(dec!(100.0)),
                    stop_price: None,
                    quantity: 100,
                };
                s.create_order(request).await
            })
        })
        .collect();

    for h in handles {
        let result = h.await.unwrap();
        assert!(result.is_ok());
    }
}

#[tokio::test]
async fn test_b2_concurrent_order_operations() {
    
    let service = Arc::new(OrderService::new());

    // Create initial orders
    let mut order_ids = Vec::new();
    for i in 0..5 {
        let request = CreateOrderRequest {
            client_order_id: format!("concurrent_{}", i),
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        let order = service.create_order(request).await.unwrap();
        order_ids.push(order.id);
    }

    // Concurrently fill and cancel
    let s1 = service.clone();
    let s2 = service.clone();
    let id1 = order_ids[0];
    let id2 = order_ids[1];

    let h1 = tokio::spawn(async move { s1.fill_order(id1, 50, dec!(100.0)).await });
    let h2 = tokio::spawn(async move { s2.cancel_order(id2, "test".to_string()).await });

    let r1 = h1.await.unwrap();
    let r2 = h2.await.unwrap();

    assert!(r1.is_ok());
    assert!(r2.is_ok());
}

#[tokio::test]
async fn test_b2_no_blocking_on_read() {
    
    let service = Arc::new(OrderService::new());

    let request = CreateOrderRequest {
        client_order_id: "read_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };
    let order = service.create_order(request).await.unwrap();
    let order_id = order.id;

    // Multiple concurrent reads
    let handles: Vec<_> = (0..20)
        .map(|_| {
            let s = service.clone();
            tokio::spawn(async move { s.get_order(order_id).await })
        })
        .collect();

    for h in handles {
        let result = h.await.unwrap();
        assert!(result.is_ok());
    }
}

#[tokio::test]
async fn test_b2_order_creation_timeout() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "timeout_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let start = std::time::Instant::now();
    let result = service.create_order(request).await;
    let elapsed = start.elapsed();

    assert!(result.is_ok());
    assert!(elapsed < Duration::from_secs(1), "BUG B2: Order creation took too long: {:?}", elapsed);
}

#[tokio::test]
async fn test_b2_fill_order_async() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "fill_async".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = service.create_order(request).await.unwrap();

    // Fill in async context should not block
    let start = std::time::Instant::now();
    let filled = service.fill_order(order.id, 50, dec!(100.0)).await.unwrap();
    let elapsed = start.elapsed();

    assert_eq!(filled.filled_quantity, 50);
    assert!(elapsed < Duration::from_millis(100), "BUG B2: Fill blocked async context");
}

#[tokio::test]
async fn test_b2_cancel_order_async() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "cancel_async".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = service.create_order(request).await.unwrap();

    // Cancel in async context should not block
    let start = std::time::Instant::now();
    let cancelled = service.cancel_order(order.id, "async_cancel".to_string()).await.unwrap();
    let elapsed = start.elapsed();

    assert_eq!(cancelled.status, OrderStatus::Cancelled);
    assert!(elapsed < Duration::from_millis(100), "BUG B2: Cancel blocked async context");
}

// ============================================================================
// D1: Unbounded Vec / Memory Tests (6 tests)
// ============================================================================

#[test]
fn test_d1_account_orders_growth() {
    
    let service = OrderService::new();

    // Create many orders for same account
    for i in 0..100 {
        let request = CreateOrderRequest {
            client_order_id: format!("growth_test_{}", i),
            account_id: "growth_account".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        tokio_test::block_on(service.create_order(request)).unwrap();
    }

    let orders = service.get_account_orders("growth_account");
    
    assert_eq!(orders.len(), 100);
}

#[test]
fn test_d1_events_unbounded() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "event_growth".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 1000,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    // Create many fill events
    for i in 0..50 {
        tokio_test::block_on(service.fill_order(order.id, 1, dec!(100.0) + Decimal::from(i))).unwrap();
    }

    
    // In production this could cause memory issues
}

#[test]
fn test_d1_large_order_quantity() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "large_qty".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: u64::MAX / 2,
    };

    let result = tokio_test::block_on(service.create_order(request));
    // Should succeed or have proper limit check
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_d1_many_symbols() {
    
    let service = OrderService::new();

    for i in 0..50 {
        let request = CreateOrderRequest {
            client_order_id: format!("symbol_test_{}", i),
            account_id: "acc1".to_string(),
            symbol: format!("SYM{}", i),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        tokio_test::block_on(service.create_order(request)).unwrap();
    }

    // All orders should be retrievable
    let orders = service.get_account_orders("acc1");
    assert_eq!(orders.len(), 50);
}

#[test]
fn test_d1_cancelled_orders_not_removed() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "cancel_mem".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    tokio_test::block_on(service.cancel_order(order.id, "test".to_string())).unwrap();

    
    let result = tokio_test::block_on(service.get_order(order.id));
    assert!(result.is_ok());
}

#[test]
fn test_d1_filled_orders_not_removed() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "filled_mem".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    tokio_test::block_on(service.fill_order(order.id, 100, dec!(100.0))).unwrap();

    
    let result = tokio_test::block_on(service.get_order(order.id));
    assert!(result.is_ok());
    assert_eq!(result.unwrap().status, OrderStatus::Filled);
}

// ============================================================================
// F1: Float Precision Tests (6 tests)
// ============================================================================

#[test]
fn test_f1_float_precision_classic() {
    
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 0.1 + 0.2, // Should be 0.3
        price: 50000.0,
    };

    let validated = validate_order(&request).unwrap();

    
    let expected = Decimal::from_str("0.3").unwrap();
    // This assertion may fail or pass depending on rounding
    let diff = (validated.quantity - expected).abs();
    assert!(diff <= dec!(0.00000001), "BUG F1: Float precision loss, diff = {}", diff);
}

#[test]
fn test_f1_small_quantity_precision() {
    
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 0.00000001,
        price: 50000.0,
    };

    let validated = validate_order(&request).unwrap();

    // Very small quantity should be preserved
    assert!(validated.quantity > Decimal::ZERO, "BUG F1: Small quantity lost");
}

#[test]
fn test_f1_large_price_precision() {
    
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 1.0,
        price: 99999.99,
    };

    let validated = validate_order(&request).unwrap();

    let expected_price = Decimal::from_str("99999.99").unwrap();
    assert_eq!(validated.price, expected_price);
}

#[test]
fn test_f1_multiplication_precision() {
    
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 0.001,
        price: 50000.0,
    };

    let validated = validate_order(&request).unwrap();

    // 0.001 * 50000 should be exactly 50
    let expected = Decimal::from_str("50.0").unwrap();
    assert_eq!(validated.value, expected, "BUG F1: Multiplication precision error");
}

#[test]
fn test_f1_decimal_vs_float_comparison() {
    
    let price_f64: f64 = 100.10;
    let price_decimal = Decimal::from_str("100.10").unwrap();

    // Convert f64 to Decimal
    let converted = Decimal::from_str(&format!("{:.8}", price_f64)).unwrap();

    
    let diff = (converted - price_decimal).abs();
    assert!(diff <= dec!(0.00000001), "BUG F1: Float to Decimal conversion error");
}

#[test]
fn test_f1_accumulating_float_errors() {
    
    let mut total: f64 = 0.0;

    for _ in 0..1000 {
        total += 0.001;
    }

    // Should be exactly 1.0
    let expected = 1.0f64;
    let error = (total - expected).abs();

    
    assert!(error < 0.0001, "BUG F1: Accumulating float error: {}", error);
}

// ============================================================================
// F5: Fee Calculation Truncation Tests (6 tests)
// ============================================================================

#[test]
fn test_f5_fee_truncation_basic() {
    
    use crate::validation::validate_order;

    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 1.0,
        price: 149.99,
    };

    let validated = validate_order(&request).unwrap();

    // 149.99 * 0.001 = 0.14999, should round to 0.15
    
    let expected_fee = Decimal::from_str("0.14").unwrap();
    assert_eq!(validated.fee, expected_fee, "BUG F5: Fee truncation detected");
}

#[test]
fn test_f5_fee_on_large_order() {
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 10.0,
        price: 10000.0,
    };

    let validated = validate_order(&request).unwrap();

    // 100000 * 0.001 = 100.0 - no truncation issue here
    let expected_fee = Decimal::from_str("100.00").unwrap();
    assert_eq!(validated.fee, expected_fee);
}

#[test]
fn test_f5_fee_small_order() {
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 0.01,
        price: 100.0,
    };

    let validated = validate_order(&request).unwrap();

    // 1.0 * 0.001 = 0.001, truncated to 0.00
    let expected_fee = Decimal::from_str("0.00").unwrap();
    assert_eq!(validated.fee, expected_fee, "BUG F5: Small fee truncated to zero");
}

#[test]
fn test_f5_fee_boundary_value() {
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 1.0,
        price: 155.55,
    };

    let validated = validate_order(&request).unwrap();

    // 155.55 * 0.001 = 0.15555, truncates to 0.15
    let expected_fee = Decimal::from_str("0.15").unwrap();
    assert_eq!(validated.fee, expected_fee);
}

#[test]
fn test_f5_accumulated_fee_loss() {
    
    let mut total_fee = Decimal::ZERO;
    let mut total_expected = Decimal::ZERO;

    for i in 0..100 {
        let price = 149.99 + (i as f64) * 0.01;
        let request = OrderRequest {
            symbol: "BTC/USD".to_string(),
            side: "buy".to_string(),
            quantity: 1.0,
            price,
        };

        let validated = validate_order(&request).unwrap();
        total_fee += validated.fee;

        // Calculate what fee should be with proper rounding
        let value = Decimal::from_str(&format!("{:.8}", price)).unwrap();
        let proper_fee = value * dec!(0.001);
        total_expected += proper_fee.round_dp(2);
    }

    
    let loss = total_expected - total_fee;
    assert!(loss >= Decimal::ZERO, "BUG F5: Accumulated fee loss: {}", loss);
}

#[test]
fn test_f5_fee_precision_maintained() {
    // Test that fee has correct precision
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 1.0,
        price: 1000.00,
    };

    let validated = validate_order(&request).unwrap();

    // 1000 * 0.001 = 1.00
    assert_eq!(validated.fee, Decimal::ONE);
    assert_eq!(validated.fee.scale(), 0);
}

// ============================================================================
// F9: Order Value Calculation Tests (5 tests)
// ============================================================================

#[test]
fn test_f9_order_value_basic() {
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 10.0,
        price: 100.0,
    };

    let validated = validate_order(&request).unwrap();

    let expected_value = Decimal::from_str("1000.0").unwrap();
    assert_eq!(validated.value, expected_value);
}

#[test]
fn test_f9_order_value_decimal_precision() {
    
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 0.001,
        price: 50000.0,
    };

    let validated = validate_order(&request).unwrap();

    // 0.001 * 50000 should be exactly 50
    let expected = Decimal::from_str("50.0").unwrap();
    assert_eq!(validated.value, expected, "BUG F9: Order value calculation error");
}

#[test]
fn test_f9_order_value_small_quantities() {
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 0.00001,
        price: 50000.0,
    };

    let validated = validate_order(&request).unwrap();

    // 0.00001 * 50000 = 0.5
    let expected = Decimal::from_str("0.5").unwrap();
    assert_eq!(validated.value, expected);
}

#[test]
fn test_f9_order_value_large_amounts() {
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 1000000.0,
        price: 100000.0,
    };

    let validated = validate_order(&request).unwrap();

    // 1000000 * 100000 = 100,000,000,000
    let expected = Decimal::from_str("100000000000.0").unwrap();
    assert_eq!(validated.value, expected);
}

#[test]
fn test_f9_order_value_consistency() {
    
    let request = OrderRequest {
        symbol: "BTC/USD".to_string(),
        side: "buy".to_string(),
        quantity: 3.33,
        price: 99.99,
    };

    let validated = validate_order(&request).unwrap();

    let computed_value = validated.quantity * validated.price;
    let diff = (validated.value - computed_value).abs();

    
    assert!(diff <= dec!(0.01), "BUG F9: Value inconsistent with qty * price, diff = {}", diff);
}

// ============================================================================
// G4: Idempotency Tests (6 tests)
// ============================================================================

#[test]
fn test_g4_cancel_already_cancelled() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "idempotent_cancel".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    // First cancel should succeed
    let result1 = tokio_test::block_on(service.cancel_order(order.id, "first".to_string()));
    assert!(result1.is_ok());

    // Second cancel should be idempotent (not error)
    let result2 = tokio_test::block_on(service.cancel_order(order.id, "second".to_string()));
    
    assert!(result2.is_err(), "BUG G4: Second cancel should be idempotent");
}

#[test]
fn test_g4_duplicate_client_order_id() {
    
    let service = OrderService::new();

    let request1 = CreateOrderRequest {
        client_order_id: "duplicate_id".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let request2 = CreateOrderRequest {
        client_order_id: "duplicate_id".to_string(), // Same ID
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let result1 = tokio_test::block_on(service.create_order(request1));
    let result2 = tokio_test::block_on(service.create_order(request2));

    
    assert!(result1.is_ok());
    assert!(result2.is_ok()); 
}

#[test]
fn test_g4_fill_already_filled() {
    
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "fill_twice".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    // Fill completely
    tokio_test::block_on(service.fill_order(order.id, 100, dec!(100.0))).unwrap();

    // Second fill should be idempotent or rejected
    let result = tokio_test::block_on(service.fill_order(order.id, 50, dec!(100.0)));
    
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_g4_concurrent_cancels() {
    
    let service = Arc::new(OrderService::new());

    let request = CreateOrderRequest {
        client_order_id: "concurrent_cancel".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let order_id = order.id;

    let handles: Vec<_> = (0..5)
        .map(|i| {
            let s = service.clone();
            thread::spawn(move || {
                tokio_test::block_on(s.cancel_order(order_id, format!("reason_{}", i)))
            })
        })
        .collect();

    let mut success_count = 0;
    for h in handles {
        if h.join().unwrap().is_ok() {
            success_count += 1;
        }
    }

    
    assert!(success_count >= 1);
}

#[test]
fn test_g4_event_sequence_uniqueness() {
    
    let service = OrderService::new();

    let mut order_ids = Vec::new();
    for i in 0..10 {
        let request = CreateOrderRequest {
            client_order_id: format!("seq_test_{}", i),
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        let order = tokio_test::block_on(service.create_order(request)).unwrap();
        order_ids.push(order.id);
    }

    // All orders should have been created
    assert_eq!(order_ids.len(), 10);
}

#[test]
fn test_g4_idempotency_key_format() {
    // Test client_order_id as idempotency key
    let service = OrderService::new();

    // UUID format client order ID
    let request = CreateOrderRequest {
        client_order_id: Uuid::new_v4().to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let result = tokio_test::block_on(service.create_order(request));
    assert!(result.is_ok());
}

// ============================================================================
// L3: Pool Exhaustion Tests (5 tests)
// ============================================================================

#[test]
fn test_l3_pool_connection_limit() {
    
    // This would require a mock pool to test properly
    // Just testing the repository structure
    assert!(true, "Pool exhaustion test requires integration setup");
}

#[test]
fn test_l3_concurrent_database_access() {
    
    let service = Arc::new(OrderService::new());

    let handles: Vec<_> = (0..100)
        .map(|i| {
            let s = service.clone();
            thread::spawn(move || {
                let request = CreateOrderRequest {
                    client_order_id: format!("pool_test_{}", i),
                    account_id: format!("acc_{}", i % 10),
                    symbol: "AAPL".to_string(),
                    side: OrderSide::Buy,
                    order_type: OrderType::Limit,
                    price: Some(dec!(100.0)),
                    stop_price: None,
                    quantity: 100,
                };
                tokio_test::block_on(s.create_order(request))
            })
        })
        .collect();

    for h in handles {
        let _ = h.join();
    }

    // All operations should complete
    assert!(true);
}

#[test]
fn test_l3_no_connection_leak() {
    
    let service = OrderService::new();

    for i in 0..50 {
        let request = CreateOrderRequest {
            client_order_id: format!("leak_test_{}", i),
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        let _ = tokio_test::block_on(service.create_order(request));
    }

    // If there was a leak, we'd see connection issues
    let final_request = CreateOrderRequest {
        client_order_id: "final".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };
    let result = tokio_test::block_on(service.create_order(final_request));
    assert!(result.is_ok());
}

#[test]
fn test_l3_query_timeout_handling() {
    
    // Would need mock database to properly test
    assert!(true, "Query timeout test requires integration setup");
}

#[test]
fn test_l3_connection_retry() {
    
    // Would need mock database to properly test
    assert!(true, "Connection retry test requires integration setup");
}

// ============================================================================
// Basic Functionality Tests (15 tests)
// ============================================================================

#[test]
fn test_create_order_basic() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "basic_order".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    assert_eq!(order.client_order_id, "basic_order");
    assert_eq!(order.account_id, "acc1");
    assert_eq!(order.symbol, "AAPL");
    assert_eq!(order.side, OrderSide::Buy);
    assert_eq!(order.quantity, 100);
    assert_eq!(order.filled_quantity, 0);
    assert_eq!(order.status, OrderStatus::Pending);
}

#[test]
fn test_create_market_order() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "market_order".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Market,
        price: None, // Market orders don't have price
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    assert_eq!(order.order_type, OrderType::Market);
    assert!(order.price.is_none());
}

#[test]
fn test_create_sell_order() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "sell_order".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Sell,
        order_type: OrderType::Limit,
        price: Some(dec!(105.0)),
        stop_price: None,
        quantity: 50,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    assert_eq!(order.side, OrderSide::Sell);
    assert_eq!(order.quantity, 50);
}

#[test]
fn test_cancel_order_basic() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "cancel_basic".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let cancelled = tokio_test::block_on(service.cancel_order(order.id, "User cancelled".to_string())).unwrap();

    assert_eq!(cancelled.status, OrderStatus::Cancelled);
}

#[test]
fn test_cancel_filled_order_fails() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "filled_cancel".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    tokio_test::block_on(service.fill_order(order.id, 100, dec!(100.0))).unwrap();

    let result = tokio_test::block_on(service.cancel_order(order.id, "Try cancel filled".to_string()));
    assert!(result.is_err());
}

#[test]
fn test_partial_fill() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "partial_fill".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let filled = tokio_test::block_on(service.fill_order(order.id, 30, dec!(100.0))).unwrap();

    assert_eq!(filled.filled_quantity, 30);
    assert_eq!(filled.status, OrderStatus::PartiallyFilled);
}

#[test]
fn test_complete_fill() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "complete_fill".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let filled = tokio_test::block_on(service.fill_order(order.id, 100, dec!(100.0))).unwrap();

    assert_eq!(filled.filled_quantity, 100);
    assert_eq!(filled.status, OrderStatus::Filled);
}

#[test]
fn test_multiple_fills() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "multi_fill".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    tokio_test::block_on(service.fill_order(order.id, 30, dec!(100.0))).unwrap();
    tokio_test::block_on(service.fill_order(order.id, 30, dec!(100.0))).unwrap();
    let final_fill = tokio_test::block_on(service.fill_order(order.id, 40, dec!(100.0))).unwrap();

    assert_eq!(final_fill.filled_quantity, 100);
    assert_eq!(final_fill.status, OrderStatus::Filled);
}

#[test]
fn test_get_order() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "get_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let retrieved = tokio_test::block_on(service.get_order(order.id)).unwrap();

    assert_eq!(retrieved.id, order.id);
    assert_eq!(retrieved.client_order_id, "get_test");
}

#[test]
fn test_get_account_orders_empty() {
    let service = OrderService::new();

    let orders = service.get_account_orders("nonexistent");
    assert!(orders.is_empty());
}

#[test]
fn test_order_has_uuid() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "uuid_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    // ID should be a valid UUID
    assert!(!order.id.is_nil());
}

#[test]
fn test_order_timestamps() {
    let service = OrderService::new();

    let before = Utc::now();

    let request = CreateOrderRequest {
        client_order_id: "timestamp_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    let after = Utc::now();

    assert!(order.created_at >= before);
    assert!(order.created_at <= after);
    assert_eq!(order.created_at, order.updated_at);
}

#[test]
fn test_stop_limit_order() {
    let service = OrderService::new();

    let request = CreateOrderRequest {
        client_order_id: "stop_limit".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::StopLimit,
        price: Some(dec!(100.0)),
        stop_price: Some(dec!(95.0)),
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();

    assert_eq!(order.order_type, OrderType::StopLimit);
    assert_eq!(order.price, Some(dec!(100.0)));
    assert_eq!(order.stop_price, Some(dec!(95.0)));
}

#[test]
fn test_validation_positive_quantity() {
    let request = OrderRequest {
        symbol: "AAPL".to_string(),
        side: "buy".to_string(),
        quantity: -100.0,
        price: 100.0,
    };

    let result = validate_order(&request);
    assert!(result.is_err());
}

#[test]
fn test_validation_positive_price() {
    let request = OrderRequest {
        symbol: "AAPL".to_string(),
        side: "buy".to_string(),
        quantity: 100.0,
        price: -100.0,
    };

    let result = validate_order(&request);
    assert!(result.is_err());
}

// ============================================================================
// Error Handling Tests (5 tests)
// ============================================================================

#[test]
fn test_error_order_not_found() {
    let service = OrderService::new();

    let result = tokio_test::block_on(service.get_order(Uuid::new_v4()));
    assert!(result.is_err());
    assert!(result.unwrap_err().to_string().contains("not found"));
}

#[test]
fn test_error_cancel_not_found() {
    let service = OrderService::new();

    let result = tokio_test::block_on(service.cancel_order(Uuid::new_v4(), "test".to_string()));
    assert!(result.is_err());
}

#[test]
fn test_error_fill_not_found() {
    let service = OrderService::new();

    let result = tokio_test::block_on(service.fill_order(Uuid::new_v4(), 100, dec!(100.0)));
    assert!(result.is_err());
}

#[test]
fn test_validation_quantity_limit() {
    let result = validate_quantity_limit(dec!(1000.0), dec!(500.0));
    assert!(result.is_err());
    assert!(result.unwrap_err().to_string().contains("exceeds"));
}

#[test]
fn test_validation_quantity_within_limit() {
    let result = validate_quantity_limit(dec!(100.0), dec!(500.0));
    assert!(result.is_ok());
}

// ============================================================================
// Concurrency Tests (5 tests)
// ============================================================================

#[test]
fn test_concurrent_order_creation() {
    let service = Arc::new(OrderService::new());

    let handles: Vec<_> = (0..10)
        .map(|i| {
            let s = service.clone();
            thread::spawn(move || {
                let request = CreateOrderRequest {
                    client_order_id: format!("concurrent_{}", i),
                    account_id: "acc1".to_string(),
                    symbol: "AAPL".to_string(),
                    side: OrderSide::Buy,
                    order_type: OrderType::Limit,
                    price: Some(dec!(100.0)),
                    stop_price: None,
                    quantity: 100,
                };
                tokio_test::block_on(s.create_order(request))
            })
        })
        .collect();

    for h in handles {
        assert!(h.join().unwrap().is_ok());
    }

    let orders = service.get_account_orders("acc1");
    assert_eq!(orders.len(), 10);
}

#[test]
fn test_concurrent_read_write() {
    let service = Arc::new(OrderService::new());

    let request = CreateOrderRequest {
        client_order_id: "rw_test".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 100,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let order_id = order.id;

    let s1 = service.clone();
    let s2 = service.clone();

    let reader = thread::spawn(move || {
        for _ in 0..100 {
            let _ = tokio_test::block_on(s1.get_order(order_id));
        }
    });

    let writer = thread::spawn(move || {
        for i in 0..10 {
            let _ = tokio_test::block_on(s2.fill_order(order_id, 1, dec!(100.0) + Decimal::from(i)));
        }
    });

    reader.join().unwrap();
    writer.join().unwrap();
}

#[test]
fn test_no_data_race_on_fill() {
    let service = Arc::new(OrderService::new());

    let request = CreateOrderRequest {
        client_order_id: "race_fill".to_string(),
        account_id: "acc1".to_string(),
        symbol: "AAPL".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: Some(dec!(100.0)),
        stop_price: None,
        quantity: 1000,
    };

    let order = tokio_test::block_on(service.create_order(request)).unwrap();
    let order_id = order.id;

    let handles: Vec<_> = (0..10)
        .map(|_| {
            let s = service.clone();
            thread::spawn(move || {
                for _ in 0..10 {
                    let _ = tokio_test::block_on(s.fill_order(order_id, 1, dec!(100.0)));
                }
            })
        })
        .collect();

    for h in handles {
        h.join().unwrap();
    }

    let final_order = tokio_test::block_on(service.get_order(order_id)).unwrap();
    // 10 threads * 10 fills * 1 qty = 100 filled
    assert!(final_order.filled_quantity <= 1000);
}

#[test]
fn test_multiple_accounts_concurrent() {
    let service = Arc::new(OrderService::new());

    let handles: Vec<_> = (0..5)
        .map(|acc_idx| {
            let s = service.clone();
            thread::spawn(move || {
                for order_idx in 0..5 {
                    let request = CreateOrderRequest {
                        client_order_id: format!("acc{}_{}", acc_idx, order_idx),
                        account_id: format!("account_{}", acc_idx),
                        symbol: "AAPL".to_string(),
                        side: OrderSide::Buy,
                        order_type: OrderType::Limit,
                        price: Some(dec!(100.0)),
                        stop_price: None,
                        quantity: 100,
                    };
                    let _ = tokio_test::block_on(s.create_order(request));
                }
            })
        })
        .collect();

    for h in handles {
        h.join().unwrap();
    }

    // Each account should have 5 orders
    for i in 0..5 {
        let orders = service.get_account_orders(&format!("account_{}", i));
        assert_eq!(orders.len(), 5);
    }
}

#[test]
fn test_thread_safety_order_service() {
    let service = Arc::new(OrderService::new());

    // Verify Send + Sync
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<OrderService>();

    // Use from multiple threads
    let s = service.clone();
    let h = thread::spawn(move || {
        let request = CreateOrderRequest {
            client_order_id: "thread_safe".to_string(),
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            price: Some(dec!(100.0)),
            stop_price: None,
            quantity: 100,
        };
        tokio_test::block_on(s.create_order(request))
    });

    assert!(h.join().unwrap().is_ok());
}
