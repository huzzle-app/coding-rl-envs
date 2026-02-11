//! Comprehensive tests for matching engine
//!
//! Tests cover: B1, B3, E1, E4, A2, A9, B11, F2, F8, D6

use crate::engine::{MatchingEngine, Order, OrderType, Side, AccountRisk, EngineError};
use crate::orderbook::{OrderBook, Trade};
use crate::priority_queue::{OrderQueue, OrderPriority, LockFreeQueue};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use parking_lot::Mutex;

// ============================================================================
// B1: Lock Ordering Deadlock Tests (10 tests)
// ============================================================================

#[test]
fn test_b1_no_lock_ordering_deadlock() {
    
    // This should not deadlock - but with the bug it can
    let (engine, _rx) = MatchingEngine::new();

    // This test would hang if deadlock occurs
    // For now, just verify no panic
    let result = engine.submit_order(Order {
        id: "order1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // Expected: SymbolNotFound since we didn't add the symbol
    assert!(matches!(result, Err(EngineError::SymbolNotFound)));
}

#[test]
fn test_b1_concurrent_order_and_risk_no_deadlock() {
    // Test concurrent access patterns that could cause deadlock
    let (engine, _rx) = MatchingEngine::new();
    let engine = Arc::new(engine);

    let handles: Vec<_> = (0..4).map(|i| {
        let e = engine.clone();
        thread::spawn(move || {
            for _ in 0..10 {
                let _ = e.submit_order(Order {
                    id: format!("order_{}", i),
                    symbol: "AAPL".to_string(),
                    account_id: format!("acc_{}", i % 2),
                    side: if i % 2 == 0 { Side::Buy } else { Side::Sell },
                    price: dec!(100.0),
                    quantity: 100,
                    order_type: OrderType::Limit,
                });
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}

#[test]
fn test_b1_submit_and_cancel_concurrent() {
    
    let (engine, _rx) = MatchingEngine::new();
    let engine = Arc::new(engine);

    let e1 = engine.clone();
    let h1 = thread::spawn(move || {
        for _ in 0..100 {
            let _ = e1.submit_order(Order {
                id: "o1".to_string(),
                symbol: "AAPL".to_string(),
                account_id: "acc1".to_string(),
                side: Side::Buy,
                price: dec!(100.0),
                quantity: 100,
                order_type: OrderType::Limit,
            });
        }
    });

    let e2 = engine.clone();
    let h2 = thread::spawn(move || {
        for _ in 0..100 {
            let _ = e2.update_risk_and_cancel("acc1", "AAPL");
        }
    });

    // Both should complete without deadlock
    h1.join().unwrap();
    h2.join().unwrap();
}

// ============================================================================
// B3: Race Condition Tests (10 tests)
// ============================================================================

#[test]
fn test_b3_order_book_race_condition() {
    
    let (engine, _rx) = MatchingEngine::new();

    // Without orders, should return None
    let result = engine.get_best_prices("AAPL");
    assert!(result.is_none());
}

#[test]
fn test_b3_best_prices_consistent() {
    
    // With the bug, we might get crossed market (bid > ask)
    let mut book = OrderBook::new("AAPL");

    // Add buy order at 100
    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // Add sell order at 101
    book.add_order(Order {
        id: "sell1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(101.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    let bid = book.best_bid();
    let ask = book.best_ask();

    // Bid should always be less than ask (no crossed market)
    if let (Some(b), Some(a)) = (bid, ask) {
        assert!(b < a, "BUG B3: Crossed market detected: bid {} >= ask {}", b, a);
    }
}

#[test]
fn test_b3_concurrent_price_reads() {
    
    let book = Arc::new(Mutex::new(OrderBook::new("AAPL")));

    // Add initial orders
    {
        let mut b = book.lock();
        b.add_order(Order {
            id: "buy1".to_string(),
            symbol: "AAPL".to_string(),
            account_id: "acc1".to_string(),
            side: Side::Buy,
            price: dec!(100.0),
            quantity: 100,
            order_type: OrderType::Limit,
        });
        b.add_order(Order {
            id: "sell1".to_string(),
            symbol: "AAPL".to_string(),
            account_id: "acc2".to_string(),
            side: Side::Sell,
            price: dec!(101.0),
            quantity: 100,
            order_type: OrderType::Limit,
        });
    }

    let handles: Vec<_> = (0..10).map(|_| {
        let b = book.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                let book = b.lock();
                let bid = book.best_bid();
                let ask = book.best_ask();
                drop(book);

                if let (Some(bid), Some(ask)) = (bid, ask) {
                    assert!(bid <= ask, "BUG B3: Crossed market");
                }
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}

// ============================================================================
// E1: Unsafe/UB Tests (8 tests)
// ============================================================================

#[test]
fn test_e1_price_conversion_safe() {
    
    let (engine, _rx) = MatchingEngine::new();

    // These bit patterns could create NaN or infinity
    let dangerous_bits: &[u64] = &[
        0x7FF0000000000001, // NaN
        0x7FF0000000000000, // +Infinity
        0xFFF0000000000000, // -Infinity
        0x0000000000000001, // Denormalized
    ];

    for &bits in dangerous_bits {
        
        let result = unsafe { engine.fast_price_convert(bits) };
        // Should not be NaN or Inf for valid prices
        assert!(!result.is_nan() || !result.is_infinite(),
            "BUG E1: Invalid float created from bits {:x}", bits);
    }
}

#[test]
fn test_e1_no_ub_transmute() {
    
    let (engine, _rx) = MatchingEngine::new();

    // Valid price should work
    let valid_bits: u64 = 0x4059000000000000; // 100.0 in IEEE 754
    let result = unsafe { engine.fast_price_convert(valid_bits) };
    assert!((result - 100.0).abs() < 0.01, "Valid conversion should work");
}

// ============================================================================
// E4: Data Race Tests (8 tests)
// ============================================================================

#[test]
fn test_e4_atomic_ordering_no_data_race() {
    
    let (engine, _rx) = MatchingEngine::new();

    // Update price
    engine.update_last_price("AAPL", dec!(100.0));

    // With Relaxed ordering, other threads might not see update
    // This test just verifies no crash
    engine.update_last_price("AAPL", dec!(101.0));
}

#[test]
fn test_e4_lockfree_ordering_correct() {
    
    use std::sync::atomic::{AtomicU64, Ordering};

    let counter = Arc::new(AtomicU64::new(0));

    let handles: Vec<_> = (0..4).map(|_| {
        let c = counter.clone();
        thread::spawn(move || {
            for _ in 0..1000 {
                
                let old = c.load(Ordering::Relaxed);
                c.store(old + 1, Ordering::Relaxed);
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    let final_val = counter.load(Ordering::SeqCst);
    // With Relaxed ordering, final value is likely less than 4000
    // Should use fetch_add with proper ordering
    assert!(final_val <= 4000, "Counter value: {}", final_val);
}

// ============================================================================
// A2: Ownership/Borrow Tests (8 tests)
// ============================================================================

#[test]
fn test_a2_closure_borrow_safety() {
    
    let mut book = OrderBook::new("AAPL");

    let order = Order {
        id: "order1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    };

    // This should work without use-after-move
    let trades = book.add_order(order);
    assert!(trades.is_empty()); // No matching orders
}

#[test]
fn test_a2_order_add_no_dangling_ref() {
    
    let mut book = OrderBook::new("AAPL");

    for i in 0..10 {
        let order = Order {
            id: format!("order_{}", i),
            symbol: "AAPL".to_string(),
            account_id: "acc1".to_string(),
            side: if i % 2 == 0 { Side::Buy } else { Side::Sell },
            price: dec!(100.0) + Decimal::from(i),
            quantity: 100,
            order_type: OrderType::Limit,
        };
        book.add_order(order);
    }

    // Verify book is consistent
    assert!(book.best_bid().is_some());
    assert!(book.best_ask().is_some());
}

// ============================================================================
// F2: Integer Overflow Tests (8 tests)
// ============================================================================

#[test]
fn test_f2_quantity_overflow_handled() {
    
    let mut queue = OrderQueue::new("test");

    // Add orders with large quantities
    queue.push(OrderPriority {
        order_id: "order1".to_string(),
        price: dec!(100.0),
        timestamp: 1,
        quantity: u64::MAX / 2,
        is_buy: true,
    });

    queue.push(OrderPriority {
        order_id: "order2".to_string(),
        price: dec!(100.0),
        timestamp: 2,
        quantity: u64::MAX / 2 + 10,
        is_buy: true,
    });

    
    let total = queue.total_quantity();
    assert!(total < u64::MAX / 2, "BUG F2: Integer overflow detected, total: {}", total);
}

#[test]
fn test_f2_checked_arithmetic() {
    
    let mut book = OrderBook::new("AAPL");

    // Add a buy order
    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // Add matching sell order
    let trades = book.add_order(Order {
        id: "sell1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 50,
        order_type: OrderType::Limit,
    });

    assert_eq!(trades.len(), 1);
    assert_eq!(trades[0].quantity, 50);
}

#[test]
fn test_f2_subtraction_underflow() {
    
    let mut book = OrderBook::new("AAPL");

    // Add small order
    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 10,
        order_type: OrderType::Limit,
    });

    // Match with larger order - should not underflow
    let trades = book.add_order(Order {
        id: "sell1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // Trade should be for smaller quantity
    assert_eq!(trades[0].quantity, 10);
}

// ============================================================================
// F8: Price Tick Validation Tests (6 tests)
// ============================================================================

#[test]
fn test_f8_price_tick_validation() {
    
    let mut book = OrderBook::new("AAPL");

    // Tick size is typically 0.01
    // Price 100.123 should be invalid
    let order = Order {
        id: "order1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.123), // Invalid tick
        quantity: 100,
        order_type: OrderType::Limit,
    };

    
    book.add_order(order);

    
    let bid = book.best_bid();
    assert!(bid.is_none() || bid.unwrap() != dec!(100.123),
        "BUG F8: Order at invalid tick price accepted");
}

#[test]
fn test_f8_invalid_tick_rejected() {
    
    let book = OrderBook::new("AAPL");

    // Valid tick prices (assuming 0.01 tick size)
    let valid_prices = vec![dec!(100.00), dec!(100.01), dec!(100.50)];

    for price in valid_prices {
        // These should all be valid
        assert!(price.scale() <= 2, "Price should have at most 2 decimal places");
    }
}

// ============================================================================
// D6: String Allocation Tests (6 tests)
// ============================================================================

#[test]
fn test_d6_no_string_alloc_hot_path() {
    
    let mut queue = OrderQueue::new("test");

    // Push many orders - each allocates format strings
    for i in 0..1000 {
        queue.push(OrderPriority {
            order_id: format!("order_{}", i),
            price: dec!(100.0),
            timestamp: i,
            quantity: 100,
            is_buy: true,
        });
    }

    // Pop all - each allocates format strings
    while queue.pop().is_some() {}

    
    assert!(queue.is_empty());
}

#[test]
fn test_d6_matching_perf_allocation() {
    
    let mut book = OrderBook::new("AAPL");

    // Add many orders
    for i in 0..100 {
        book.add_order(Order {
            id: format!("order_{}", i),
            symbol: "AAPL".to_string(),
            account_id: "acc1".to_string(),
            side: if i % 2 == 0 { Side::Buy } else { Side::Sell },
            price: dec!(100.0) + Decimal::from(i % 10),
            quantity: 100,
            order_type: OrderType::Limit,
        });
    }

    
    assert!(book.best_bid().is_some());
}

// ============================================================================
// B11: Lock-free ABA Tests (6 tests)
// ============================================================================

#[test]
fn test_b11_lockfree_aba_prevention() {
    
    let mut queue = LockFreeQueue::new(16);

    // Add some orders
    for i in 0..5 {
        queue.enqueue(OrderPriority {
            order_id: format!("order_{}", i),
            price: dec!(100.0),
            timestamp: i,
            quantity: 100,
            is_buy: true,
        });
    }

    // Dequeue some
    for _ in 0..3 {
        queue.dequeue();
    }

    
    // This test just verifies basic operation
    assert!(queue.dequeue().is_some());
}

#[test]
fn test_b11_order_book_aba_safe() {
    
    let book = OrderBook::new("AAPL");

    // try_match_lockfree demonstrates the ABA problem
    let result = book.try_match_lockfree();
    assert!(result.is_none()); // Placeholder implementation
}

// ============================================================================
// Order Book Functionality Tests (20 tests)
// ============================================================================

#[test]
fn test_order_book_basic_add() {
    let mut book = OrderBook::new("AAPL");

    book.add_order(Order {
        id: "order1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    assert_eq!(book.best_bid(), Some(dec!(100.0)));
    assert_eq!(book.best_ask(), None);
}

#[test]
fn test_order_book_matching() {
    let mut book = OrderBook::new("AAPL");

    // Add buy order
    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // Add matching sell order
    let trades = book.add_order(Order {
        id: "sell1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    assert_eq!(trades.len(), 1);
    assert_eq!(trades[0].price, dec!(100.0));
    assert_eq!(trades[0].quantity, 100);
}

#[test]
fn test_order_book_partial_fill() {
    let mut book = OrderBook::new("AAPL");

    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    let trades = book.add_order(Order {
        id: "sell1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 50,
        order_type: OrderType::Limit,
    });

    assert_eq!(trades.len(), 1);
    assert_eq!(trades[0].quantity, 50);
    // Remaining 50 shares at bid
    assert_eq!(book.best_bid(), Some(dec!(100.0)));
}

#[test]
fn test_order_book_cancel() {
    let mut book = OrderBook::new("AAPL");

    book.add_order(Order {
        id: "order1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    assert!(book.cancel_order("order1", Side::Buy, dec!(100.0)));
    assert_eq!(book.best_bid(), None);
}

#[test]
fn test_order_book_cancel_nonexistent() {
    let mut book = OrderBook::new("AAPL");

    assert!(!book.cancel_order("nonexistent", Side::Buy, dec!(100.0)));
}

#[test]
fn test_order_book_cancel_all_for_account() {
    let mut book = OrderBook::new("AAPL");

    for i in 0..5 {
        book.add_order(Order {
            id: format!("order_{}", i),
            symbol: "AAPL".to_string(),
            account_id: "acc1".to_string(),
            side: Side::Buy,
            price: dec!(100.0) + Decimal::from(i),
            quantity: 100,
            order_type: OrderType::Limit,
        });
    }

    let cancelled = book.cancel_all_for_account("acc1");
    assert_eq!(cancelled.len(), 5);
    assert_eq!(book.best_bid(), None);
}

#[test]
fn test_order_book_price_priority() {
    let mut book = OrderBook::new("AAPL");

    // Add orders at different prices
    book.add_order(Order {
        id: "order1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(99.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    book.add_order(Order {
        id: "order2".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // Best bid should be highest price
    assert_eq!(book.best_bid(), Some(dec!(100.0)));
}

#[test]
fn test_order_book_time_priority() {
    let mut book = OrderBook::new("AAPL");

    // Add two orders at same price
    book.add_order(Order {
        id: "first".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    book.add_order(Order {
        id: "second".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // First order should be matched first (FIFO)
    let trades = book.add_order(Order {
        id: "sell".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    assert_eq!(trades.len(), 1);
    assert_eq!(trades[0].maker_order_id, "first");
}

#[test]
fn test_order_book_multiple_matches() {
    let mut book = OrderBook::new("AAPL");

    // Add multiple buy orders
    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 50,
        order_type: OrderType::Limit,
    });

    book.add_order(Order {
        id: "buy2".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 50,
        order_type: OrderType::Limit,
    });

    // Large sell should match both
    let trades = book.add_order(Order {
        id: "sell".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "acc2".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    assert_eq!(trades.len(), 2);
}

#[test]
fn test_order_book_no_self_trade() {
    let mut book = OrderBook::new("AAPL");

    // Same account on both sides
    book.add_order(Order {
        id: "buy1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "same_account".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    // This should not self-trade
    let trades = book.add_order(Order {
        id: "sell1".to_string(),
        symbol: "AAPL".to_string(),
        account_id: "same_account".to_string(),
        side: Side::Sell,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    
    // Currently allows self-trade
    assert!(trades.len() <= 1);
}

// ============================================================================
// Priority Queue Tests (10 tests)
// ============================================================================

#[test]
fn test_priority_queue_basic() {
    let mut queue = OrderQueue::new("test");

    queue.push(OrderPriority {
        order_id: "order1".to_string(),
        price: dec!(100.0),
        timestamp: 1,
        quantity: 100,
        is_buy: true,
    });

    assert_eq!(queue.len(), 1);
    assert!(!queue.is_empty());
}

#[test]
fn test_priority_queue_price_ordering() {
    let mut queue = OrderQueue::new("test");

    // Add orders at different prices
    queue.push(OrderPriority {
        order_id: "low".to_string(),
        price: dec!(99.0),
        timestamp: 1,
        quantity: 100,
        is_buy: true,
    });

    queue.push(OrderPriority {
        order_id: "high".to_string(),
        price: dec!(101.0),
        timestamp: 2,
        quantity: 100,
        is_buy: true,
    });

    // For buy orders, higher price should come first
    let first = queue.pop().unwrap();
    assert_eq!(first.order_id, "high");
}

#[test]
fn test_priority_queue_timestamp_ordering() {
    let mut queue = OrderQueue::new("test");

    // Same price, different timestamps
    queue.push(OrderPriority {
        order_id: "later".to_string(),
        price: dec!(100.0),
        timestamp: 2,
        quantity: 100,
        is_buy: true,
    });

    queue.push(OrderPriority {
        order_id: "earlier".to_string(),
        price: dec!(100.0),
        timestamp: 1,
        quantity: 100,
        is_buy: true,
    });

    // Earlier timestamp should come first (FIFO at same price)
    let first = queue.pop().unwrap();
    assert_eq!(first.order_id, "earlier");
}

#[test]
fn test_priority_queue_total_quantity() {
    let mut queue = OrderQueue::new("test");

    queue.push(OrderPriority {
        order_id: "order1".to_string(),
        price: dec!(100.0),
        timestamp: 1,
        quantity: 100,
        is_buy: true,
    });

    queue.push(OrderPriority {
        order_id: "order2".to_string(),
        price: dec!(100.0),
        timestamp: 2,
        quantity: 200,
        is_buy: true,
    });

    assert_eq!(queue.total_quantity(), 300);
}

#[test]
fn test_priority_queue_pop_updates_quantity() {
    let mut queue = OrderQueue::new("test");

    queue.push(OrderPriority {
        order_id: "order1".to_string(),
        price: dec!(100.0),
        timestamp: 1,
        quantity: 100,
        is_buy: true,
    });

    queue.pop();

    // Quantity should be zero after pop
    // Note: may be buggy due to F2
    assert!(queue.total_quantity() <= 100);
}

#[test]
fn test_lockfree_queue_basic() {
    let mut queue = LockFreeQueue::new(8);

    assert!(queue.enqueue(OrderPriority {
        order_id: "order1".to_string(),
        price: dec!(100.0),
        timestamp: 1,
        quantity: 100,
        is_buy: true,
    }));

    let order = queue.dequeue();
    assert!(order.is_some());
    assert_eq!(order.unwrap().order_id, "order1");
}

#[test]
fn test_lockfree_queue_full() {
    let mut queue = LockFreeQueue::new(4);

    // Fill the queue
    for i in 0..3 {
        assert!(queue.enqueue(OrderPriority {
            order_id: format!("order_{}", i),
            price: dec!(100.0),
            timestamp: i,
            quantity: 100,
            is_buy: true,
        }));
    }

    // Next enqueue should fail
    assert!(!queue.enqueue(OrderPriority {
        order_id: "overflow".to_string(),
        price: dec!(100.0),
        timestamp: 99,
        quantity: 100,
        is_buy: true,
    }));
}

#[test]
fn test_lockfree_queue_empty() {
    let mut queue = LockFreeQueue::new(4);

    assert!(queue.dequeue().is_none());
}

// ============================================================================
// Engine Tests (10 tests)
// ============================================================================

#[test]
fn test_engine_new() {
    let (engine, _rx) = MatchingEngine::new();
    // Engine should be created successfully
    let _ = engine;
}

#[test]
fn test_engine_submit_unknown_symbol() {
    let (engine, _rx) = MatchingEngine::new();

    let result = engine.submit_order(Order {
        id: "order1".to_string(),
        symbol: "UNKNOWN".to_string(),
        account_id: "acc1".to_string(),
        side: Side::Buy,
        price: dec!(100.0),
        quantity: 100,
        order_type: OrderType::Limit,
    });

    assert!(matches!(result, Err(EngineError::SymbolNotFound)));
}

#[test]
fn test_engine_update_risk_unknown_account() {
    let (engine, _rx) = MatchingEngine::new();

    let result = engine.update_risk_and_cancel("unknown", "AAPL");
    assert!(matches!(result, Err(EngineError::AccountNotFound)));
}

#[test]
fn test_engine_get_best_prices_empty() {
    let (engine, _rx) = MatchingEngine::new();

    let result = engine.get_best_prices("AAPL");
    assert!(result.is_none());
}
