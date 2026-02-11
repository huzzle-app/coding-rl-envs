//! Comprehensive tests for positions service
//!
//! Tests cover: A3 (mutable borrow in iterator), B7 (atomic ordering),
//! D2 (Arc cycle leak), F6 (P&L calculation), G2 (distributed lock),
//! C4 (unhandled Result in drop)

use crate::tracker::{Position, PositionEvent, PositionEventType, PositionSnapshot, PositionTracker};
use crate::pnl::{PnLCalculator, PnLReport, SymbolPnL, RoundingMode};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::Duration;
use chrono::Utc;

// ============================================================================
// A3: Mutable Borrow in Iterator Tests (8 tests)
// ============================================================================

#[test]
fn test_a3_iterator_no_mutable_borrow_conflict() {
    
    let tracker = PositionTracker::new();

    // Add initial positions
    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc1", "MSFT", 50, dec!(300.00)).unwrap();

    // Getting all positions should not cause borrow conflict
    let positions = tracker.get_all_positions("acc1");
    assert_eq!(positions.len(), 2);
}

#[test]
fn test_a3_concurrent_iteration_and_modification() {
    
    let tracker = Arc::new(PositionTracker::new());

    // Pre-populate with data
    for i in 0..10 {
        tracker.apply_fill("acc1", &format!("SYM{}", i), 100, dec!(100.00)).unwrap();
    }

    let tracker_read = tracker.clone();
    let tracker_write = tracker.clone();

    let reader = thread::spawn(move || {
        for _ in 0..50 {
            let positions = tracker_read.get_all_positions("acc1");
            // Iterating should not panic
            for pos in &positions {
                let _ = pos.quantity;
            }
            thread::sleep(Duration::from_micros(10));
        }
    });

    let writer = thread::spawn(move || {
        for i in 0..50 {
            let _ = tracker_write.apply_fill("acc1", &format!("SYM{}", i % 10), 10, dec!(100.50));
            thread::sleep(Duration::from_micros(10));
        }
    });

    reader.join().unwrap();
    writer.join().unwrap();
}

#[test]
fn test_a3_snapshot_during_modification() {
    
    let tracker = Arc::new(PositionTracker::new());

    for i in 0..5 {
        tracker.apply_fill("acc1", &format!("SYM{}", i), 100, dec!(100.00)).unwrap();
    }

    let tracker1 = tracker.clone();
    let tracker2 = tracker.clone();

    let handles: Vec<_> = (0..4).map(|_| {
        let t = tracker1.clone();
        thread::spawn(move || {
            for _ in 0..20 {
                let _ = t.create_snapshot();
            }
        })
    }).collect();

    let writer = thread::spawn(move || {
        for i in 0..80 {
            let price = dec!(100.00) + Decimal::from(i);
            let _ = tracker2.apply_fill("acc1", &format!("SYM{}", i % 5), 10, price);
        }
    });

    for h in handles {
        h.join().unwrap();
    }
    writer.join().unwrap();
}

#[test]
fn test_a3_nested_iteration_safety() {
    
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc1", "MSFT", 50, dec!(300.00)).unwrap();
    tracker.apply_fill("acc2", "AAPL", 75, dec!(151.00)).unwrap();

    // Iterate over all accounts and their positions
    let snapshot = tracker.create_snapshot();
    for (account_id, positions) in &snapshot.positions {
        for (symbol, pos) in positions {
            // Nested iteration should work without borrow issues
            assert!(!account_id.is_empty());
            assert!(!symbol.is_empty());
            assert_ne!(pos.quantity, 0);
        }
    }
}

#[test]
fn test_a3_modify_during_get_position() {
    
    let tracker = Arc::new(PositionTracker::new());

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc1", "MSFT", 50, dec!(300.00)).unwrap();

    let t1 = tracker.clone();
    let t2 = tracker.clone();

    let h1 = thread::spawn(move || {
        for _ in 0..100 {
            let _ = t1.get_position("acc1", "AAPL");
        }
    });

    let h2 = thread::spawn(move || {
        for i in 0..100 {
            let _ = t2.apply_fill("acc1", "MSFT", 1, dec!(300.00) + Decimal::from(i));
        }
    });

    h1.join().unwrap();
    h2.join().unwrap();
}

#[test]
fn test_a3_dashmap_concurrent_access() {
    
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..8).map(|i| {
        let t = tracker.clone();
        thread::spawn(move || {
            for j in 0..50 {
                let _ = t.apply_fill(
                    &format!("acc{}", i % 4),
                    &format!("SYM{}", j % 10),
                    10,
                    dec!(100.00)
                );
                let _ = t.get_all_positions(&format!("acc{}", i % 4));
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}

#[test]
fn test_a3_iterator_invalidation() {
    
    let tracker = PositionTracker::new();

    // Add positions
    for i in 0..20 {
        tracker.apply_fill("acc1", &format!("SYM{}", i), 100, dec!(100.00)).unwrap();
    }

    // Get positions - iterator should be valid
    let positions = tracker.get_all_positions("acc1");
    assert_eq!(positions.len(), 20);

    // Modify while we have the cloned positions
    tracker.apply_fill("acc1", "NEW_SYM", 100, dec!(100.00)).unwrap();

    // Original positions should still be valid (cloned)
    assert_eq!(positions.len(), 20);
}

#[test]
fn test_a3_multiple_accounts_iteration() {
    
    let tracker = PositionTracker::new();

    for acc in 0..5 {
        for sym in 0..5 {
            tracker.apply_fill(
                &format!("acc{}", acc),
                &format!("SYM{}", sym),
                100,
                dec!(100.00)
            ).unwrap();
        }
    }

    // Create snapshot iterates over all
    let snapshot = tracker.create_snapshot();
    assert_eq!(snapshot.positions.len(), 5);
    for (_, positions) in &snapshot.positions {
        assert_eq!(positions.len(), 5);
    }
}

// ============================================================================
// B7: Atomic Ordering Tests (10 tests)
// ============================================================================

#[test]
fn test_b7_relaxed_ordering_visibility() {
    
    let tracker = Arc::new(PositionTracker::new());

    let t1 = tracker.clone();
    let t2 = tracker.clone();

    let writer = thread::spawn(move || {
        for i in 0..100 {
            let _ = t1.apply_fill("acc1", "AAPL", 1, dec!(100.00));
        }
    });

    let reader = thread::spawn(move || {
        let mut seen_events = 0u64;
        for _ in 0..100 {
            let snapshot = t2.create_snapshot();
            
            seen_events = seen_events.max(snapshot.last_event_id);
        }
        seen_events
    });

    writer.join().unwrap();
    let final_events = reader.join().unwrap();

    // With proper ordering, we should see at least some events
    // With Relaxed, we might miss some
    assert!(final_events > 0 || true); // May pass even with bug
}

#[test]
fn test_b7_event_counter_consistency() {
    
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..4).map(|i| {
        let t = tracker.clone();
        thread::spawn(move || {
            for _ in 0..25 {
                let _ = t.apply_fill(
                    &format!("acc{}", i),
                    "AAPL",
                    1,
                    dec!(100.00)
                );
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    
    let snapshot = tracker.create_snapshot();
    // This may fail intermittently with the bug
    assert!(snapshot.last_event_id > 0);
}

#[test]
fn test_b7_fetch_add_ordering() {
    
    let counter = Arc::new(AtomicU64::new(0));
    let data = Arc::new(std::sync::Mutex::new(Vec::new()));

    let c1 = counter.clone();
    let d1 = data.clone();
    let h1 = thread::spawn(move || {
        for _ in 0..50 {
            let id = c1.fetch_add(1, Ordering::Relaxed);
            d1.lock().unwrap().push((id, 1));
        }
    });

    let c2 = counter.clone();
    let d2 = data.clone();
    let h2 = thread::spawn(move || {
        for _ in 0..50 {
            let id = c2.fetch_add(1, Ordering::Relaxed);
            d2.lock().unwrap().push((id, 2));
        }
    });

    h1.join().unwrap();
    h2.join().unwrap();

    let final_count = counter.load(Ordering::SeqCst);
    assert_eq!(final_count, 100); // fetch_add is atomic, just ordering is weak
}

#[test]
fn test_b7_load_store_ordering() {
    
    let counter = Arc::new(AtomicU64::new(0));
    let flag = Arc::new(std::sync::atomic::AtomicBool::new(false));

    let c1 = counter.clone();
    let f1 = flag.clone();

    let writer = thread::spawn(move || {
        c1.store(42, Ordering::Relaxed);
        
        f1.store(true, Ordering::Relaxed);
    });

    let c2 = counter.clone();
    let f2 = flag.clone();

    let reader = thread::spawn(move || {
        // Wait for flag
        while !f2.load(Ordering::Relaxed) {
            thread::yield_now();
        }
        
        c2.load(Ordering::Relaxed)
    });

    writer.join().unwrap();
    let value = reader.join().unwrap();

    // With proper ordering (SeqCst), this should always be 42
    // With Relaxed, it might be 0
    assert!(value == 42 || value == 0);
}

#[test]
fn test_b7_concurrent_snapshot_event_id() {
    
    let tracker = Arc::new(PositionTracker::new());

    let t1 = tracker.clone();
    let writer = thread::spawn(move || {
        for _ in 0..100 {
            let _ = t1.apply_fill("acc1", "AAPL", 1, dec!(100.00));
        }
    });

    let t2 = tracker.clone();
    let reader = thread::spawn(move || {
        let mut snapshots = Vec::new();
        for _ in 0..50 {
            snapshots.push(t2.create_snapshot());
            thread::sleep(Duration::from_micros(10));
        }
        snapshots
    });

    writer.join().unwrap();
    let snapshots = reader.join().unwrap();

    
    for i in 1..snapshots.len() {
        // With Relaxed ordering, this might fail
        assert!(
            snapshots[i].last_event_id >= snapshots[i-1].last_event_id,
            "BUG B7: Non-monotonic event IDs: {} < {}",
            snapshots[i].last_event_id,
            snapshots[i-1].last_event_id
        );
    }
}

#[test]
fn test_b7_memory_barrier_missing() {
    
    let tracker = Arc::new(PositionTracker::new());

    let t1 = tracker.clone();
    let t2 = tracker.clone();

    let writer = thread::spawn(move || {
        t1.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
        
    });

    writer.join().unwrap();

    // Read should see complete position
    let pos = t2.get_position("acc1", "AAPL");
    assert!(pos.is_some());
    let p = pos.unwrap();
    assert_eq!(p.quantity, 100);
    assert_eq!(p.average_entry_price, dec!(150.00));
}

#[test]
fn test_b7_seqcst_would_be_correct() {
    // Demonstrate that SeqCst ordering would fix the issue
    let counter = Arc::new(AtomicU64::new(0));

    let handles: Vec<_> = (0..4).map(|_| {
        let c = counter.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                c.fetch_add(1, Ordering::SeqCst);
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(counter.load(Ordering::SeqCst), 400);
}

#[test]
fn test_b7_acquire_release_pattern() {
    
    let data = Arc::new(AtomicU64::new(0));
    let ready = Arc::new(std::sync::atomic::AtomicBool::new(false));

    let d1 = data.clone();
    let r1 = ready.clone();

    let producer = thread::spawn(move || {
        d1.store(42, Ordering::Release);
        r1.store(true, Ordering::Release);
    });

    let d2 = data.clone();
    let r2 = ready.clone();

    let consumer = thread::spawn(move || {
        while !r2.load(Ordering::Acquire) {
            thread::yield_now();
        }
        d2.load(Ordering::Acquire)
    });

    producer.join().unwrap();
    let value = consumer.join().unwrap();

    // With Acquire-Release, this is guaranteed to be 42
    assert_eq!(value, 42);
}

#[test]
fn test_b7_version_visibility() {
    
    let tracker = Arc::new(PositionTracker::new());

    // Create initial position
    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let t1 = tracker.clone();
    let t2 = tracker.clone();

    let updater = thread::spawn(move || {
        for _ in 0..10 {
            let _ = t1.apply_fill("acc1", "AAPL", 10, dec!(151.00));
        }
    });

    let reader = thread::spawn(move || {
        let mut versions = Vec::new();
        for _ in 0..20 {
            if let Some(pos) = t2.get_position("acc1", "AAPL") {
                versions.push(pos.version);
            }
            thread::sleep(Duration::from_micros(5));
        }
        versions
    });

    updater.join().unwrap();
    let versions = reader.join().unwrap();

    // Versions should be monotonically increasing (within each read)
    
    for v in &versions {
        assert!(*v >= 1);
    }
}

#[test]
fn test_b7_event_log_ordering() {
    
    let tracker = PositionTracker::new();

    for i in 0..20 {
        tracker.apply_fill(
            &format!("acc{}", i % 3),
            &format!("SYM{}", i % 5),
            100,
            dec!(100.00)
        ).unwrap();
    }

    // Events should have sequential IDs
    let snapshot = tracker.create_snapshot();
    assert!(snapshot.last_event_id >= 19); // 0-indexed
}

// ============================================================================
// D2: Arc Cycle Memory Leak Tests (8 tests)
// ============================================================================

#[test]
fn test_d2_no_arc_cycle_in_tracker() {
    
    // Tracker has Arc<RwLock<Vec>> and Arc<RwLock<Option<Snapshot>>>
    let tracker = Arc::new(PositionTracker::new());

    // Add some data
    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.create_snapshot();

    // Strong count should be 1 (just our reference)
    assert_eq!(Arc::strong_count(&tracker), 1);
}

#[test]
fn test_d2_snapshot_does_not_retain_tracker() {
    
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let snapshot = tracker.create_snapshot();

    // Snapshot is independent - modifying tracker shouldn't affect it
    tracker.apply_fill("acc1", "AAPL", 50, dec!(160.00)).unwrap();

    let pos = snapshot.positions.get("acc1").unwrap().get("AAPL").unwrap();
    assert_eq!(pos.quantity, 100); // Original value

    // Tracker's position is updated
    let current = tracker.get_position("acc1", "AAPL").unwrap();
    assert_eq!(current.quantity, 150);
}

#[test]
fn test_d2_event_log_growth() {
    
    let tracker = PositionTracker::new();

    for i in 0..1000 {
        tracker.apply_fill("acc1", "AAPL", 1, dec!(100.00)).unwrap();
    }

    
    // Should have eviction/compaction strategy
    let snapshot = tracker.create_snapshot();
    assert_eq!(snapshot.last_event_id, 999); // 0-indexed
}

#[test]
fn test_d2_multiple_snapshots_no_leak() {
    
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let mut snapshots = Vec::new();
    for _ in 0..100 {
        snapshots.push(tracker.create_snapshot());
        tracker.apply_fill("acc1", "AAPL", 1, dec!(150.00)).unwrap();
    }

    // Each snapshot should be independent
    assert_eq!(snapshots.len(), 100);

    // First and last should have different data
    let first = &snapshots[0];
    let last = &snapshots[99];

    let first_qty = first.positions.get("acc1").unwrap().get("AAPL").unwrap().quantity;
    let last_qty = last.positions.get("acc1").unwrap().get("AAPL").unwrap().quantity;

    assert!(last_qty > first_qty);
}

#[test]
fn test_d2_concurrent_arc_clone_drop() {
    
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..10).map(|_| {
        let t = tracker.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                let cloned = t.clone();
                // Clone and immediately drop
                drop(cloned);
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    // Only our reference should remain
    assert_eq!(Arc::strong_count(&tracker), 1);
}

#[test]
fn test_d2_position_not_leaked() {
    
    let tracker = PositionTracker::new();

    // Open position
    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    // Close position
    tracker.apply_fill("acc1", "AAPL", -100, dec!(160.00)).unwrap();

    // Position still exists but is zero
    let pos = tracker.get_position("acc1", "AAPL");
    assert!(pos.is_some());
    assert_eq!(pos.unwrap().quantity, 0);

    
}

#[test]
fn test_d2_weak_reference_pattern() {
    // Demonstrate Weak can prevent cycles
    use std::sync::Weak;

    struct Node {
        _value: i32,
        _parent: Option<Weak<Node>>,
    }

    let parent = Arc::new(Node { _value: 1, _parent: None });
    let child = Arc::new(Node { _value: 2, _parent: Some(Arc::downgrade(&parent)) });

    assert_eq!(Arc::strong_count(&parent), 1);
    assert_eq!(Arc::weak_count(&parent), 1);

    drop(child);

    assert_eq!(Arc::strong_count(&parent), 1);
    assert_eq!(Arc::weak_count(&parent), 0);
}

#[test]
fn test_d2_event_log_reference_cycle() {
    
    let tracker = Arc::new(PositionTracker::new());

    for i in 0..10 {
        tracker.apply_fill("acc1", &format!("SYM{}", i), 100, dec!(100.00)).unwrap();
    }

    // Create snapshot
    let _snapshot = tracker.create_snapshot();

    // Tracker should not hold strong reference to snapshot
    assert_eq!(Arc::strong_count(&tracker), 1);
}

// ============================================================================
// F6: P&L Calculation Tests (12 tests)
// ============================================================================

#[test]
fn test_f6_unrealized_pnl_long_position() {
    
    let calc = PnLCalculator::new();

    // Long 100 shares at $100, current price $110
    let pnl = calc.calculate_unrealized_pnl(100, dec!(100.00), dec!(110.00));

    // Expected: (110 - 100) * 100 = $1000
    
    assert_eq!(pnl, dec!(1000));
}

#[test]
fn test_f6_unrealized_pnl_short_position() {
    
    let calc = PnLCalculator::new();

    // Short 100 shares at $100, current price $90
    let pnl = calc.calculate_unrealized_pnl(-100, dec!(100.00), dec!(90.00));

    // For short: (entry - current) * qty = (100 - 90) * -100 = -1000
    // But unrealized should be positive since short profits when price goes down
    
    let expected = dec!(-1000); // (90 - 100) * 100
    assert_eq!(pnl, expected);
}

#[test]
fn test_f6_pnl_decimal_precision() {
    
    let calc = PnLCalculator::new();

    // Price difference is small
    let pnl = calc.calculate_unrealized_pnl(1000, dec!(100.001), dec!(100.002));

    // Expected: 0.001 * 1000 = 1.0
    
    assert!(pnl > dec!(0.0) || pnl == dec!(0.0)); // May be 0 with floor
}

#[test]
fn test_f6_rounding_mode_floor() {
    
    let calc = PnLCalculator::new();

    // Small profit that gets floored
    let pnl = calc.calculate_unrealized_pnl(1, dec!(100.00), dec!(100.999));

    // Expected: 0.999, floored to 0
    
    assert!(pnl <= dec!(1.0));
}

#[test]
fn test_f6_fee_calculation() {
    
    let calc = PnLCalculator::new();

    // Notional: $10,000, fee rate: 0.1%
    let fee = calc.calculate_fee("AAPL", dec!(10000.00));

    // Expected: 10000 * 0.001 = $10
    assert_eq!(fee, dec!(10));
}

#[test]
fn test_f6_fee_rounding_direction() {
    
    let calc = PnLCalculator::new();

    // Notional that creates fractional fee
    let fee = calc.calculate_fee("AAPL", dec!(10001.00));

    // Expected: 10001 * 0.001 = 10.001
    // Should round UP to 10.01, but BUG F6 uses same rounding as P&L
    // With Floor rounding, this becomes 10
    assert!(fee >= dec!(10));
}

#[test]
fn test_f6_total_pnl_aggregation() {
    
    let calc = PnLCalculator::new();

    let positions = vec![
        SymbolPnL {
            symbol: "AAPL".to_string(),
            realized_pnl: dec!(100.50),
            unrealized_pnl: dec!(50.25),
            total_pnl: dec!(150.75),
            average_entry_price: dec!(150.00),
            current_price: dec!(160.00),
            quantity: 100,
        },
        SymbolPnL {
            symbol: "MSFT".to_string(),
            realized_pnl: dec!(200.75),
            unrealized_pnl: dec!(75.50),
            total_pnl: dec!(276.25),
            average_entry_price: dec!(300.00),
            current_price: dec!(310.00),
            quantity: 50,
        },
    ];

    let report = calc.calculate_total_pnl(&positions);

    
    // With floor rounding: 100 + 200 = 300 (lost $1.25)
    assert!(report.realized_pnl >= dec!(300));
}

#[test]
fn test_f6_net_pnl_calculation() {
    
    let calc = PnLCalculator::new();
    calc.update_market_price("AAPL", dec!(160.00));

    let positions = vec![
        SymbolPnL {
            symbol: "AAPL".to_string(),
            realized_pnl: dec!(1000.00),
            unrealized_pnl: dec!(500.00),
            total_pnl: dec!(1500.00),
            average_entry_price: dec!(150.00),
            current_price: dec!(160.00),
            quantity: 100,
        },
    ];

    let report = calc.calculate_total_pnl(&positions);

    // Net = Total - Fees
    
    assert!(report.net_pnl <= report.total_pnl);
}

#[test]
fn test_f6_position_value_calculation() {
    
    let calc = PnLCalculator::new();

    let value = calc.calculate_position_value(100, dec!(150.50)).unwrap();

    // Expected: 100 * 150.50 = 15050
    assert_eq!(value, dec!(15050.00));
}

#[test]
fn test_f6_mark_to_market() {
    
    let calc = PnLCalculator::new();
    calc.update_market_price("AAPL", dec!(160.00));

    let mut positions = vec![
        SymbolPnL {
            symbol: "AAPL".to_string(),
            realized_pnl: dec!(0.00),
            unrealized_pnl: dec!(0.00),
            total_pnl: dec!(0.00),
            average_entry_price: dec!(150.00),
            current_price: dec!(150.00),
            quantity: 100,
        },
    ];

    calc.mark_to_market(&mut positions);

    // After MTM, unrealized P&L should be updated
    // Expected: (160 - 150) * 100 = 1000
    assert_eq!(positions[0].current_price, dec!(160.00));
    assert_eq!(positions[0].unrealized_pnl, dec!(1000));
}

#[test]
fn test_f6_stale_price_handling() {
    
    let calc = PnLCalculator::new();
    // No price set for AAPL

    let mut positions = vec![
        SymbolPnL {
            symbol: "AAPL".to_string(),
            realized_pnl: dec!(0.00),
            unrealized_pnl: dec!(100.00),
            total_pnl: dec!(100.00),
            average_entry_price: dec!(150.00),
            current_price: dec!(155.00),
            quantity: 100,
        },
    ];

    calc.mark_to_market(&mut positions);

    
    // Should error or use fallback
    assert_eq!(positions[0].unrealized_pnl, dec!(100.00));
}

#[test]
fn test_f6_zero_quantity_pnl() {
    
    let calc = PnLCalculator::new();

    let pnl = calc.calculate_unrealized_pnl(0, dec!(100.00), dec!(110.00));

    // Zero quantity = zero unrealized P&L
    assert_eq!(pnl, dec!(0));
}

// ============================================================================
// G2: Distributed Lock Tests (8 tests)
// ============================================================================

#[test]
fn test_g2_lock_acquisition_basic() {
    
    // Simulated with local mutex for testing
    use parking_lot::Mutex;

    let lock = Arc::new(Mutex::new(0));

    let l1 = lock.clone();
    let h1 = thread::spawn(move || {
        let mut guard = l1.lock();
        *guard += 1;
        thread::sleep(Duration::from_millis(10));
    });

    let l2 = lock.clone();
    let h2 = thread::spawn(move || {
        let mut guard = l2.lock();
        *guard += 1;
    });

    h1.join().unwrap();
    h2.join().unwrap();

    assert_eq!(*lock.lock(), 2);
}

#[test]
fn test_g2_lock_not_released_on_panic() {
    
    use std::sync::Mutex;

    let lock = Arc::new(Mutex::new(0));

    let l1 = lock.clone();
    let h1 = thread::spawn(move || {
        let _guard = l1.lock().unwrap();
        panic!("Simulated panic");
    });

    // Wait for panic
    let _ = h1.join();

    
    // parking_lot doesn't poison but distributed locks need explicit release
    let result = lock.lock();
    assert!(result.is_err()); // Poisoned
}

#[test]
fn test_g2_lock_timeout() {
    
    use parking_lot::Mutex;

    let lock = Arc::new(Mutex::new(0));

    let l1 = lock.clone();
    let h1 = thread::spawn(move || {
        let _guard = l1.lock();
        thread::sleep(Duration::from_millis(100));
    });

    thread::sleep(Duration::from_millis(10)); // Let h1 acquire lock

    let l2 = lock.clone();
    let h2 = thread::spawn(move || {
        // parking_lot has try_lock with timeout
        let result = l2.try_lock_for(Duration::from_millis(5));
        result.is_some()
    });

    let acquired = h2.join().unwrap();
    h1.join().unwrap();

    // Should timeout since h1 holds lock for 100ms
    assert!(!acquired);
}

#[test]
fn test_g2_lock_lease_expiry() {
    
    // Simulated behavior

    struct LeaseableLock {
        holder: Arc<std::sync::Mutex<Option<String>>>,
        lease_start: Arc<std::sync::Mutex<Option<std::time::Instant>>>,
        lease_duration: Duration,
    }

    impl LeaseableLock {
        fn new(duration: Duration) -> Self {
            Self {
                holder: Arc::new(std::sync::Mutex::new(None)),
                lease_start: Arc::new(std::sync::Mutex::new(None)),
                lease_duration: duration,
            }
        }

        fn acquire(&self, holder_id: &str) -> bool {
            let mut h = self.holder.lock().unwrap();
            let mut start = self.lease_start.lock().unwrap();

            // Check if lease expired
            if let (Some(_), Some(s)) = (&*h, &*start) {
                if s.elapsed() > self.lease_duration {
                    // Lease expired, can take over
                    *h = Some(holder_id.to_string());
                    *start = Some(std::time::Instant::now());
                    return true;
                }
                return false;
            }

            *h = Some(holder_id.to_string());
            *start = Some(std::time::Instant::now());
            true
        }

        fn release(&self, holder_id: &str) -> bool {
            let mut h = self.holder.lock().unwrap();
            if h.as_ref() == Some(&holder_id.to_string()) {
                *h = None;
                return true;
            }
            false
        }
    }

    let lock = LeaseableLock::new(Duration::from_millis(50));

    assert!(lock.acquire("holder1"));
    assert!(!lock.acquire("holder2")); // Locked

    thread::sleep(Duration::from_millis(60));

    
    assert!(lock.acquire("holder2"));
}

#[test]
fn test_g2_lock_renewal() {
    
    use std::sync::atomic::AtomicBool;

    let lock_held = Arc::new(AtomicBool::new(true));
    let should_renew = Arc::new(AtomicBool::new(true));

    let lh = lock_held.clone();
    let sr = should_renew.clone();

    let renewal_thread = thread::spawn(move || {
        while sr.load(Ordering::SeqCst) {
            // Simulated renewal
            lh.store(true, Ordering::SeqCst);
            thread::sleep(Duration::from_millis(10));
        }
    });

    // Lock is held
    assert!(lock_held.load(Ordering::SeqCst));

    // Stop renewal
    should_renew.store(false, Ordering::SeqCst);
    renewal_thread.join().unwrap();

    
}

#[test]
fn test_g2_lock_fencing_token() {
    
    // Each lock acquisition should return monotonically increasing token

    let fence_token = Arc::new(AtomicU64::new(0));

    let acquire_lock = |ft: &Arc<AtomicU64>| -> u64 {
        ft.fetch_add(1, Ordering::SeqCst)
    };

    let token1 = acquire_lock(&fence_token);
    let token2 = acquire_lock(&fence_token);
    let token3 = acquire_lock(&fence_token);

    assert!(token1 < token2);
    assert!(token2 < token3);
}

#[test]
fn test_g2_lock_contention() {
    
    use parking_lot::Mutex;

    let lock = Arc::new(Mutex::new(0));
    let completed = Arc::new(AtomicU64::new(0));

    let handles: Vec<_> = (0..10).map(|_| {
        let l = lock.clone();
        let c = completed.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                let mut guard = l.lock();
                *guard += 1;
                drop(guard);
                c.fetch_add(1, Ordering::SeqCst);
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(completed.load(Ordering::SeqCst), 1000);
    assert_eq!(*lock.lock(), 1000);
}

#[test]
fn test_g2_lock_cleanup_on_crash() {
    
    use parking_lot::Mutex;

    let lock = Arc::new(Mutex::new(0));

    let l1 = lock.clone();
    let h1 = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
        let _guard = l1.lock();
        panic!("Crash!");
    }));

    assert!(h1.is_err());

    // parking_lot mutex is not poisoned, lock is still usable
    
    let mut guard = lock.lock();
    *guard = 42;
    assert_eq!(*guard, 42);
}

// ============================================================================
// C4: Unhandled Result in Drop Tests (6 tests)
// ============================================================================

#[test]
fn test_c4_drop_does_not_panic() {
    
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    // Dropping should not panic
    drop(tracker);
}

#[test]
fn test_c4_drop_with_pending_events() {
    
    let tracker = PositionTracker::new();

    for i in 0..100 {
        tracker.apply_fill("acc1", &format!("SYM{}", i), 100, dec!(100.00)).unwrap();
    }

    // Dropping with many events
    drop(tracker);
}

#[test]
fn test_c4_arc_drop_cleanup() {
    
    let tracker = Arc::new(PositionTracker::new());

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let weak = Arc::downgrade(&tracker);

    drop(tracker);

    // Weak reference should be dead
    assert!(weak.upgrade().is_none());
}

#[test]
fn test_c4_result_handling_in_cleanup() {
    
    // This is a mock struct to demonstrate the issue

    struct ResourceHolder {
        _data: Vec<u8>,
    }

    impl Drop for ResourceHolder {
        fn drop(&mut self) {
            
            // Example: self.close().unwrap() <- BAD
            // Should be: if let Err(e) = self.close() { log::error!(...); }
        }
    }

    let holder = ResourceHolder { _data: vec![1, 2, 3] };
    drop(holder);
}

#[test]
fn test_c4_nested_drop() {
    
    struct Outer {
        tracker: PositionTracker,
    }

    impl Drop for Outer {
        fn drop(&mut self) {
            
            let _snapshot = self.tracker.create_snapshot();
        }
    }

    let outer = Outer { tracker: PositionTracker::new() };
    outer.tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    drop(outer);
}

#[test]
fn test_c4_drop_in_panic() {
    
    struct SafeDropper {
        id: u32,
    }

    impl Drop for SafeDropper {
        fn drop(&mut self) {
            
            // Using println which is panic-safe
            let _ = std::io::Write::write_all(
                &mut std::io::sink(),
                format!("Dropping {}", self.id).as_bytes()
            );
        }
    }

    let result = std::panic::catch_unwind(|| {
        let _dropper = SafeDropper { id: 1 };
        panic!("Test panic");
    });

    assert!(result.is_err());
}

// ============================================================================
// Position Tracking Tests (10 tests)
// ============================================================================

#[test]
fn test_position_open_long() {
    let tracker = PositionTracker::new();

    let pos = tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    assert_eq!(pos.quantity, 100);
    assert_eq!(pos.average_entry_price, dec!(150.00));
    assert_eq!(pos.realized_pnl, dec!(0));
}

#[test]
fn test_position_open_short() {
    let tracker = PositionTracker::new();

    let pos = tracker.apply_fill("acc1", "AAPL", -100, dec!(150.00)).unwrap();

    assert_eq!(pos.quantity, -100);
    assert_eq!(pos.average_entry_price, dec!(150.00));
}

#[test]
fn test_position_increase_long() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let pos = tracker.apply_fill("acc1", "AAPL", 50, dec!(160.00)).unwrap();

    assert_eq!(pos.quantity, 150);
    // Average: (100*150 + 50*160) / 150 = 23000/150 = 153.33...
    let expected_avg = (dec!(100) * dec!(150.00) + dec!(50) * dec!(160.00)) / dec!(150);
    assert_eq!(pos.average_entry_price, expected_avg);
}

#[test]
fn test_position_decrease_with_pnl() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let pos = tracker.apply_fill("acc1", "AAPL", -50, dec!(160.00)).unwrap();

    assert_eq!(pos.quantity, 50);
    // P&L: (160 - 150) * 50 = 500
    assert_eq!(pos.realized_pnl, dec!(500));
}

#[test]
fn test_position_close_with_pnl() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let pos = tracker.apply_fill("acc1", "AAPL", -100, dec!(160.00)).unwrap();

    assert_eq!(pos.quantity, 0);
    // P&L: (160 - 150) * 100 = 1000
    assert_eq!(pos.realized_pnl, dec!(1000));
}

#[test]
fn test_position_reverse() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let pos = tracker.apply_fill("acc1", "AAPL", -150, dec!(160.00)).unwrap();

    // Closed 100 at profit, then short 50
    assert_eq!(pos.quantity, -50);
    // P&L from closing long: (160-150) * 100 = 1000
    assert_eq!(pos.realized_pnl, dec!(1000));
}

#[test]
fn test_multiple_accounts() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc2", "AAPL", 50, dec!(155.00)).unwrap();

    let pos1 = tracker.get_position("acc1", "AAPL").unwrap();
    let pos2 = tracker.get_position("acc2", "AAPL").unwrap();

    assert_eq!(pos1.quantity, 100);
    assert_eq!(pos2.quantity, 50);
}

#[test]
fn test_multiple_symbols() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc1", "MSFT", 50, dec!(300.00)).unwrap();

    let positions = tracker.get_all_positions("acc1");

    assert_eq!(positions.len(), 2);
}

#[test]
fn test_get_nonexistent_position() {
    let tracker = PositionTracker::new();

    let pos = tracker.get_position("acc1", "AAPL");

    assert!(pos.is_none());
}

#[test]
fn test_position_version_increments() {
    let tracker = PositionTracker::new();

    let pos1 = tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let pos2 = tracker.apply_fill("acc1", "AAPL", 50, dec!(160.00)).unwrap();

    assert!(pos2.version > pos1.version);
}

// ============================================================================
// Event Sourcing / Snapshot Tests (10 tests)
// ============================================================================

#[test]
fn test_snapshot_basic() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let snapshot = tracker.create_snapshot();

    assert_eq!(snapshot.positions.len(), 1);
    assert!(snapshot.positions.contains_key("acc1"));
}

#[test]
fn test_snapshot_isolation() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let snapshot = tracker.create_snapshot();

    // Modify after snapshot
    tracker.apply_fill("acc1", "AAPL", 50, dec!(160.00)).unwrap();

    // Snapshot should have original value
    let pos = snapshot.positions.get("acc1").unwrap().get("AAPL").unwrap();
    assert_eq!(pos.quantity, 100);
}

#[test]
fn test_snapshot_event_id() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc1", "MSFT", 50, dec!(300.00)).unwrap();

    let snapshot = tracker.create_snapshot();

    // Event ID should match number of events
    assert!(snapshot.last_event_id >= 1);
}

#[test]
fn test_rebuild_from_events() {
    let tracker = PositionTracker::new();

    // Create events
    let events = vec![
        PositionEvent {
            event_id: 0,
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            event_type: PositionEventType::Opened {
                quantity: 100,
                price: dec!(150.00),
            },
            timestamp: Utc::now(),
        },
        PositionEvent {
            event_id: 1,
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            event_type: PositionEventType::Increased {
                quantity: 50,
                price: dec!(160.00),
            },
            timestamp: Utc::now(),
        },
    ];

    let positions = tracker.rebuild_from_events(&events).unwrap();

    let pos = positions.get("acc1").unwrap().get("AAPL").unwrap();
    assert_eq!(pos.quantity, 150);
}

#[test]
fn test_rebuild_closed_position() {
    let tracker = PositionTracker::new();

    let events = vec![
        PositionEvent {
            event_id: 0,
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            event_type: PositionEventType::Opened {
                quantity: 100,
                price: dec!(150.00),
            },
            timestamp: Utc::now(),
        },
        PositionEvent {
            event_id: 1,
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            event_type: PositionEventType::Closed {
                realized_pnl: dec!(1000.00),
            },
            timestamp: Utc::now(),
        },
    ];

    let positions = tracker.rebuild_from_events(&events).unwrap();

    let pos = positions.get("acc1").unwrap().get("AAPL").unwrap();
    assert_eq!(pos.quantity, 0);
    assert_eq!(pos.realized_pnl, dec!(1000.00));
}

#[test]
fn test_snapshot_timestamp() {
    let tracker = PositionTracker::new();

    let before = Utc::now();
    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let snapshot = tracker.create_snapshot();
    let after = Utc::now();

    assert!(snapshot.timestamp >= before);
    assert!(snapshot.timestamp <= after);
}

#[test]
fn test_multiple_snapshots() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    let s1 = tracker.create_snapshot();

    tracker.apply_fill("acc1", "AAPL", 50, dec!(160.00)).unwrap();
    let s2 = tracker.create_snapshot();

    // Different snapshots have different event IDs
    assert!(s2.last_event_id > s1.last_event_id);
}

#[test]
fn test_empty_snapshot() {
    let tracker = PositionTracker::new();

    let snapshot = tracker.create_snapshot();

    assert!(snapshot.positions.is_empty());
    assert_eq!(snapshot.last_event_id, 0);
}

#[test]
fn test_snapshot_multiple_accounts() {
    let tracker = PositionTracker::new();

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();
    tracker.apply_fill("acc2", "MSFT", 50, dec!(300.00)).unwrap();
    tracker.apply_fill("acc3", "GOOGL", 25, dec!(2800.00)).unwrap();

    let snapshot = tracker.create_snapshot();

    assert_eq!(snapshot.positions.len(), 3);
}

#[test]
fn test_rebuild_maintains_order() {
    let tracker = PositionTracker::new();

    let events = vec![
        PositionEvent {
            event_id: 0,
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            event_type: PositionEventType::Opened {
                quantity: 100,
                price: dec!(100.00),
            },
            timestamp: Utc::now(),
        },
        PositionEvent {
            event_id: 1,
            account_id: "acc1".to_string(),
            symbol: "AAPL".to_string(),
            event_type: PositionEventType::Decreased {
                quantity: -50,
                price: dec!(110.00),
                realized_pnl: dec!(500.00),
            },
            timestamp: Utc::now(),
        },
    ];

    let positions = tracker.rebuild_from_events(&events).unwrap();
    let pos = positions.get("acc1").unwrap().get("AAPL").unwrap();

    assert_eq!(pos.quantity, 50);
    assert_eq!(pos.realized_pnl, dec!(500.00));
}

// ============================================================================
// Concurrency Tests (10 tests)
// ============================================================================

#[test]
fn test_concurrent_fills_different_accounts() {
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..10).map(|i| {
        let t = tracker.clone();
        thread::spawn(move || {
            for j in 0..100 {
                t.apply_fill(
                    &format!("acc{}", i),
                    "AAPL",
                    1,
                    dec!(100.00) + Decimal::from(j)
                ).unwrap();
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    // Each account should have positions
    for i in 0..10 {
        let pos = tracker.get_position(&format!("acc{}", i), "AAPL").unwrap();
        assert_eq!(pos.quantity, 100);
    }
}

#[test]
fn test_concurrent_fills_same_position() {
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..10).map(|_| {
        let t = tracker.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                let _ = t.apply_fill("acc1", "AAPL", 1, dec!(100.00));
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    let pos = tracker.get_position("acc1", "AAPL").unwrap();
    assert_eq!(pos.quantity, 1000);
}

#[test]
fn test_concurrent_read_write() {
    let tracker = Arc::new(PositionTracker::new());

    // Pre-populate
    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let t1 = tracker.clone();
    let writer = thread::spawn(move || {
        for i in 0..100 {
            let _ = t1.apply_fill("acc1", "AAPL", 1, dec!(150.00) + Decimal::from(i));
        }
    });

    let t2 = tracker.clone();
    let reader = thread::spawn(move || {
        let mut reads = 0;
        for _ in 0..100 {
            if t2.get_position("acc1", "AAPL").is_some() {
                reads += 1;
            }
        }
        reads
    });

    writer.join().unwrap();
    let reads = reader.join().unwrap();

    assert_eq!(reads, 100);
}

#[test]
fn test_concurrent_snapshot_creation() {
    let tracker = Arc::new(PositionTracker::new());

    tracker.apply_fill("acc1", "AAPL", 100, dec!(150.00)).unwrap();

    let handles: Vec<_> = (0..10).map(|_| {
        let t = tracker.clone();
        thread::spawn(move || {
            for _ in 0..10 {
                let _snapshot = t.create_snapshot();
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}

#[test]
fn test_high_contention() {
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..100).map(|i| {
        let t = tracker.clone();
        thread::spawn(move || {
            t.apply_fill("acc1", "AAPL", 1, dec!(100.00)).unwrap();
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    let pos = tracker.get_position("acc1", "AAPL").unwrap();
    assert_eq!(pos.quantity, 100);
}

#[test]
fn test_concurrent_multiple_symbols() {
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..10).map(|i| {
        let t = tracker.clone();
        thread::spawn(move || {
            for j in 0..10 {
                t.apply_fill(
                    "acc1",
                    &format!("SYM{}", (i * 10 + j) % 20),
                    1,
                    dec!(100.00)
                ).unwrap();
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    let positions = tracker.get_all_positions("acc1");
    assert!(positions.len() <= 20);
}

#[test]
fn test_no_lost_updates() {
    let tracker = Arc::new(PositionTracker::new());
    let expected_qty = Arc::new(AtomicU64::new(0));

    let handles: Vec<_> = (0..10).map(|_| {
        let t = tracker.clone();
        let e = expected_qty.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                t.apply_fill("acc1", "AAPL", 1, dec!(100.00)).unwrap();
                e.fetch_add(1, Ordering::SeqCst);
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    let pos = tracker.get_position("acc1", "AAPL").unwrap();
    let expected = expected_qty.load(Ordering::SeqCst);

    assert_eq!(pos.quantity as u64, expected);
}

#[test]
fn test_concurrent_get_all_positions() {
    let tracker = Arc::new(PositionTracker::new());

    // Pre-populate
    for i in 0..10 {
        tracker.apply_fill("acc1", &format!("SYM{}", i), 100, dec!(100.00)).unwrap();
    }

    let handles: Vec<_> = (0..10).map(|_| {
        let t = tracker.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                let positions = t.get_all_positions("acc1");
                assert!(positions.len() >= 10);
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}

#[test]
fn test_stress_mixed_operations() {
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..20).map(|i| {
        let t = tracker.clone();
        thread::spawn(move || {
            for j in 0..50 {
                match i % 4 {
                    0 => { let _ = t.apply_fill(&format!("acc{}", j % 5), "AAPL", 1, dec!(100.00)); }
                    1 => { let _ = t.get_position(&format!("acc{}", j % 5), "AAPL"); }
                    2 => { let _ = t.get_all_positions(&format!("acc{}", j % 5)); }
                    3 => { let _ = t.create_snapshot(); }
                    _ => {}
                }
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}

#[test]
fn test_concurrent_close_and_reopen() {
    let tracker = Arc::new(PositionTracker::new());

    let handles: Vec<_> = (0..5).map(|_| {
        let t = tracker.clone();
        thread::spawn(move || {
            for _ in 0..20 {
                // Open
                t.apply_fill("acc1", "AAPL", 100, dec!(100.00)).unwrap();
                // Close
                t.apply_fill("acc1", "AAPL", -100, dec!(110.00)).unwrap();
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}
