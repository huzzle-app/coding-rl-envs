//! Concurrency tests for QuantumCore
//!
//! Tests cover: B1-B12 concurrency bugs

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use std::path::PathBuf;
use parking_lot::{Mutex, RwLock, Condvar};

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
// B1: Lock Ordering Deadlock Tests
// =============================================================================

#[test]
fn test_b1_lock_ordering_consistent() {

    let lock_a = Arc::new(Mutex::new(0u64));
    let lock_b = Arc::new(Mutex::new(0u64));

    let mut handles = vec![];

    for _i in 0..4 {
        let la = lock_a.clone();
        let lb = lock_b.clone();

        let h = thread::spawn(move || {
            for _ in 0..100 {
                // Consistent order: always A then B
                let mut a = la.lock();
                let mut b = lb.lock();
                *a += 1;
                *b += 1;
                drop(b);
                drop(a);
            }
        });
        handles.push(h);
    }

    for h in handles {
        h.join().expect("Should complete without deadlock");
    }

    assert_eq!(*lock_a.lock(), 400);
    assert_eq!(*lock_b.lock(), 400);
}

#[test]
fn test_b1_lock_ordering_in_source() {
    // BUG B1: Matching engine acquires locks in inconsistent order
    // submit_order: order_book -> risk_state
    // update_risk_and_cancel: risk_state -> order_book
    let src = read_source("services/matching/src/engine.rs");

    // Find lock acquisition order in submit_order
    let submit_fn = src.split("fn submit_order").nth(1).unwrap_or("");
    let submit_body = submit_fn.split("\n    pub ").next().unwrap_or(submit_fn);

    // Find lock acquisition order in update_risk_and_cancel
    let cancel_fn = src.split("fn update_risk_and_cancel").nth(1).unwrap_or("");
    let cancel_body = cancel_fn.split("\n    pub ").next().unwrap_or(cancel_fn);

    // In submit_order, order_books is locked before risk_state
    let submit_books_first = submit_body.find("order_book").unwrap_or(usize::MAX)
        < submit_body.find("risk_state").unwrap_or(usize::MAX);

    // In update_risk_and_cancel, risk_state is locked before order_books
    let cancel_risk_first = cancel_body.find("risk_state").unwrap_or(usize::MAX)
        < cancel_body.find("order_book").unwrap_or(usize::MAX);

    // If both acquire in different orders, deadlock is possible
    assert!(!(submit_books_first && cancel_risk_first),
        "Lock ordering is inconsistent: submit_order locks order_book->risk, \
         but update_risk_and_cancel locks risk->order_book — DEADLOCK possible (bug B1)");
}

// =============================================================================
// B2: Blocking in Async Context Tests (source-verifying)
// =============================================================================

#[test]
fn test_b2_no_blocking_in_async() {
    // BUG B2: Async functions should not use blocking operations
    let src = read_source("services/orders/src/service.rs");
    // Check for std::thread::sleep in async functions (blocking the executor)
    let has_thread_sleep = src.contains("std::thread::sleep") || src.contains("thread::sleep");
    // Check for std::sync::Mutex in async context (should use tokio::sync::Mutex)
    let has_std_mutex_in_async = src.contains("std::sync::Mutex");
    assert!(!has_thread_sleep,
        "Async code should not use std::thread::sleep — use tokio::time::sleep instead");
    assert!(!has_std_mutex_in_async,
        "Async code should not use std::sync::Mutex — use tokio::sync::Mutex or parking_lot");
}

#[test]
fn test_b2_spawn_blocking_used() {
    // BUG B2: CPU-bound work in async should use spawn_blocking
    let matching_src = read_source("services/matching/src/engine.rs");
    // The matching engine does CPU-bound work (order matching) — check if it's properly handled
    // If running in async context, should use spawn_blocking for heavy computation
    let has_spawn_blocking = matching_src.contains("spawn_blocking")
        || matching_src.contains("block_in_place");
    // Also acceptable: the engine runs on its own runtime/thread pool
    let has_dedicated_runtime = matching_src.contains("Runtime")
        || matching_src.contains("thread_pool")
        || matching_src.contains("rayon");
    assert!(has_spawn_blocking || has_dedicated_runtime,
        "CPU-bound matching work should use spawn_blocking or dedicated thread pool");
}

// =============================================================================
// B3: Race Condition Tests
// =============================================================================

#[test]
fn test_b3_read_modify_write_atomic() {

    let counter = Arc::new(AtomicU64::new(0));
    let mut handles = vec![];

    for _ in 0..10 {
        let c = counter.clone();
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                // Atomic increment
                c.fetch_add(1, Ordering::SeqCst);
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    // With atomic operations, final value should be 10000
    assert_eq!(counter.load(Ordering::SeqCst), 10000);
}

#[test]
fn test_b3_check_then_act_atomic() {

    let value = Arc::new(AtomicU64::new(100));

    let v1 = value.clone();
    let v2 = value.clone();

    let h1 = thread::spawn(move || {
        for _ in 0..100 {
            // Atomic compare-and-swap
            let _ = v1.compare_exchange(100, 99, Ordering::SeqCst, Ordering::SeqCst);
        }
    });

    let h2 = thread::spawn(move || {
        for _ in 0..100 {
            let _ = v2.compare_exchange(99, 100, Ordering::SeqCst, Ordering::SeqCst);
        }
    });

    h1.join().unwrap();
    h2.join().unwrap();

    let final_val = value.load(Ordering::SeqCst);
    assert!(final_val == 99 || final_val == 100, "Value should be consistent");
}

#[test]
fn test_b3_race_in_order_book() {
    // BUG B3: get_best_prices drops and reacquires lock between bid and ask reads
    let src = read_source("services/matching/src/engine.rs");
    let best_prices_fn = src.split("fn get_best_prices").nth(1).unwrap_or("");
    let fn_body = best_prices_fn.split("\n    pub ").next().unwrap_or(best_prices_fn);
    // Count how many times the lock is acquired in this function
    let lock_count = fn_body.matches(".lock()").count();
    // Should hold lock for the entire operation (1 lock), not release and reacquire (2+ locks)
    assert!(lock_count <= 1,
        "get_best_prices acquires the lock {} times — should hold lock for both bid and ask reads \
         to prevent inconsistent (crossed) market data (bug B3)", lock_count);
}

// =============================================================================
// B4: Future Send Tests (source-verifying)
// =============================================================================

#[test]
fn test_b4_data_is_send() {
    // BUG E5/B4: Check that unsafe Send/Sync impls aren't used incorrectly
    let src = read_source("shared/src/discovery.rs");
    // Unsafe Send/Sync implementations are dangerous and usually indicate a bug
    let has_unsafe_send = src.contains("unsafe impl Send");
    assert!(!has_unsafe_send,
        "ServiceDiscovery has unsafe impl Send — this bypasses compiler safety checks (bug E5)");
}

#[test]
fn test_b4_data_is_sync() {
    // BUG E5/B4: Check that unsafe Sync impl isn't used
    let src = read_source("shared/src/discovery.rs");
    let has_unsafe_sync = src.contains("unsafe impl Sync");
    assert!(!has_unsafe_sync,
        "ServiceDiscovery has unsafe impl Sync — this bypasses compiler safety checks (bug E5)");
}

// =============================================================================
// B5: Mutex Poisoning Tests
// =============================================================================

#[test]
fn test_b5_mutex_poison_handled() {
    use std::sync::Mutex as StdMutex;

    let mutex = Arc::new(StdMutex::new(0u64));

    // Simulate panic that poisons mutex
    let m = mutex.clone();
    let result = thread::spawn(move || {
        let _guard = m.lock().unwrap();
        panic!("Intentional panic");
    }).join();

    assert!(result.is_err(), "Thread should have panicked");

    // Mutex is now poisoned - must handle this
    let m = mutex.clone();
    let lock_result = m.lock();
    match lock_result {
        Ok(_) => panic!("Should be poisoned"),
        Err(poisoned) => {
            // Recover from poisoning
            let guard = poisoned.into_inner();
            assert_eq!(*guard, 0);
        }
    }
}

#[test]
fn test_b5_parking_lot_no_poison() {
    // parking_lot::Mutex doesn't poison
    let mutex = Arc::new(Mutex::new(0u64));

    let m = mutex.clone();
    let result = thread::spawn(move || {
        let _guard = m.lock();
        panic!("Intentional panic");
    }).join();

    assert!(result.is_err());

    // parking_lot mutex is still usable
    let guard = mutex.lock();
    assert_eq!(*guard, 0);
}

// =============================================================================
// B6: Channel Backpressure Tests
// =============================================================================

#[test]
fn test_b6_channel_backpressure() {
    use std::sync::mpsc;


    // Bounded channel provides backpressure
    let (tx, rx) = mpsc::sync_channel::<u64>(10);

    let producer = thread::spawn(move || {
        for i in 0..100 {
            if tx.send(i).is_err() {
                break;
            }
        }
    });

    // Consumer is slower
    thread::sleep(Duration::from_millis(10));

    // Collect what we can
    let mut received = 0;
    while rx.try_recv().is_ok() {
        received += 1;
    }

    // Drop receiver so producer gets SendError and breaks
    drop(rx);
    producer.join().unwrap();

    // Should have received some messages
    assert!(received > 0, "Should receive some messages");
}

#[test]
fn test_b6_bounded_channel() {
    use crossbeam::channel;

    let (tx, rx) = channel::bounded::<u64>(5);

    // Fill the channel
    for i in 0..5 {
        tx.send(i).unwrap();
    }

    // Next send would block or fail
    assert!(tx.try_send(99).is_err(), "Channel should be full");

    // Drain one
    rx.recv().unwrap();

    // Now can send
    assert!(tx.try_send(99).is_ok(), "Channel has room");
}

// =============================================================================
// B7: Atomic Ordering Tests
// =============================================================================

#[test]
fn test_b7_atomic_ordering_correct() {

    let value = Arc::new(AtomicU64::new(0));
    let flag = Arc::new(AtomicBool::new(false));

    let v = value.clone();
    let f = flag.clone();

    let producer = thread::spawn(move || {
        v.store(42, Ordering::Release);
        f.store(true, Ordering::Release);
    });

    producer.join().unwrap();

    // Consumer with Acquire ordering sees both writes
    if flag.load(Ordering::Acquire) {
        assert_eq!(value.load(Ordering::Acquire), 42);
    }
}

#[test]
fn test_b7_seqcst_for_ordering() {
    // BUG B7: Position tracker uses Ordering::Relaxed for event counter
    let src = read_source("services/positions/src/tracker.rs");
    // Event counter should use SeqCst or at least Acquire/Release, not Relaxed
    let lines: Vec<&str> = src.lines().collect();
    let mut relaxed_in_counter = false;
    for line in &lines {
        if line.contains("event_counter") && line.contains("Relaxed") {
            relaxed_in_counter = true;
        }
    }
    assert!(!relaxed_in_counter,
        "Event counter uses Ordering::Relaxed — should use SeqCst for cross-thread visibility (bug B7)");
}

// =============================================================================
// B8: Spin Loop Tests
// =============================================================================

#[test]
fn test_b8_no_spin_loop_in_async() {

    let ready = Arc::new(AtomicBool::new(false));

    let r = ready.clone();
    let setter = thread::spawn(move || {
        thread::sleep(Duration::from_millis(10));
        r.store(true, Ordering::SeqCst);
    });

    // Use proper waiting, not spin loop
    while !ready.load(Ordering::SeqCst) {
        std::hint::spin_loop(); // Hint to CPU, better than busy-wait
    }

    setter.join().unwrap();
    assert!(ready.load(Ordering::SeqCst));
}

#[test]
fn test_b8_use_condvar() {
    // Better: use condvar for waiting (with timeout to avoid test hanging)
    use std::sync::mpsc;

    let (done_tx, done_rx) = mpsc::channel();

    thread::spawn(move || {
        let pair = Arc::new((Mutex::new(false), Condvar::new()));

        let p = pair.clone();
        let setter = thread::spawn(move || {
            thread::sleep(Duration::from_millis(10));
            let (lock, cvar) = &*p;
            let mut ready = lock.lock();
            *ready = true;
            cvar.notify_one();
        });

        let (lock, cvar) = &*pair;
        let mut ready = lock.lock();
        // Use wait_for with timeout to avoid blocking forever
        let result = cvar.wait_for(&mut ready, Duration::from_secs(2));
        let success = *ready && !result.timed_out();
        drop(ready);

        let _ = setter.join();
        let _ = done_tx.send(success);
    });

    match done_rx.recv_timeout(Duration::from_secs(5)) {
        Ok(true) => {} // Condvar properly notified
        Ok(false) => panic!("Condvar notification failed or timed out"),
        Err(_) => panic!("Test timed out — condvar deadlock detected"),
    }
}

// =============================================================================
// B9: Condvar Spurious Wakeup Tests
// =============================================================================

#[test]
fn test_b9_condvar_spurious_wakeup() {

    let pair = Arc::new((Mutex::new(0u64), Condvar::new()));

    let p = pair.clone();
    let setter = thread::spawn(move || {
        thread::sleep(Duration::from_millis(10));
        let (lock, cvar) = &*p;
        let mut value = lock.lock();
        *value = 42;
        cvar.notify_all();
    });

    let (lock, cvar) = &*pair;
    let mut value = lock.lock();

    // CORRECT: Check condition in loop
    while *value != 42 {
        cvar.wait(&mut value);
    }

    setter.join().unwrap();
    assert_eq!(*value, 42);
}

#[test]
fn test_b9_wait_while() {
    // Better: use wait_while helper
    let pair = Arc::new((Mutex::new(false), Condvar::new()));

    let p = pair.clone();
    let setter = thread::spawn(move || {
        thread::sleep(Duration::from_millis(5));
        let (lock, cvar) = &*p;
        *lock.lock() = true;
        cvar.notify_one();
    });

    let (lock, cvar) = &*pair;
    let mut guard = lock.lock();
    cvar.wait_while(&mut guard, |ready| !*ready);

    setter.join().unwrap();
    assert!(*guard);
}

// =============================================================================
// B10: Thread Pool Exhaustion Tests
// =============================================================================

#[test]
fn test_b10_thread_pool_bounded() {

    let max_threads = 4;
    let active = Arc::new(AtomicU64::new(0));
    let max_seen = Arc::new(AtomicU64::new(0));

    let mut handles = vec![];
    for _ in 0..20 {
        let a = active.clone();
        let m = max_seen.clone();

        handles.push(thread::spawn(move || {
            let current = a.fetch_add(1, Ordering::SeqCst) + 1;
            m.fetch_max(current, Ordering::SeqCst);
            thread::sleep(Duration::from_millis(1));
            a.fetch_sub(1, Ordering::SeqCst);
        }));

        // Limit concurrent threads
        if handles.len() >= max_threads {
            if let Some(h) = handles.pop() {
                h.join().unwrap();
            }
        }
    }

    for h in handles {
        h.join().unwrap();
    }

    // Some threads ran concurrently
    assert!(max_seen.load(Ordering::SeqCst) > 0);
}

// =============================================================================
// B11: Lock-free ABA Problem Tests
// =============================================================================

#[test]
fn test_b11_aba_with_tagged_pointer() {

    let counter = Arc::new(AtomicU64::new(0));

    // Tagged value: lower bits = value, upper bits = tag
    let pack = |value: u32, tag: u32| -> u64 {
        ((tag as u64) << 32) | (value as u64)
    };

    let unpack = |packed: u64| -> (u32, u32) {
        ((packed & 0xFFFFFFFF) as u32, (packed >> 32) as u32)
    };

    counter.store(pack(100, 0), Ordering::SeqCst);

    // Update with tag increment
    let old = counter.load(Ordering::SeqCst);
    let (value, tag) = unpack(old);
    let new_value = pack(value + 1, tag + 1);

    let result = counter.compare_exchange(old, new_value, Ordering::SeqCst, Ordering::SeqCst);
    assert!(result.is_ok(), "CAS should succeed");

    let (final_value, final_tag) = unpack(counter.load(Ordering::SeqCst));
    assert_eq!(final_value, 101);
    assert_eq!(final_tag, 1);
}

// =============================================================================
// B12: Memory Ordering in Price Updates Tests
// =============================================================================

#[test]
fn test_b12_memory_ordering_prices() {

    let price = Arc::new(AtomicU64::new(0));
    let sequence = Arc::new(AtomicU64::new(0));

    let p = price.clone();
    let s = sequence.clone();

    let producer = thread::spawn(move || {
        for i in 1..=100 {
            p.store(i * 100, Ordering::Release);
            s.store(i, Ordering::Release);
        }
    });

    producer.join().unwrap();

    // Consumer should see consistent price and sequence
    let seq = sequence.load(Ordering::Acquire);
    let prc = price.load(Ordering::Acquire);

    assert!(seq == 0 || prc == seq * 100, "Price and sequence should be consistent");
}

#[test]
fn test_b12_memory_ordering_in_source() {
    // BUG B12: Matching engine uses Relaxed ordering for price updates
    let src = read_source("services/matching/src/engine.rs");
    // Find the update_last_price function
    let update_fn = src.split("fn update_last_price").nth(1).unwrap_or("");
    let fn_body = update_fn.split("\n    fn ").next().unwrap_or(update_fn);
    // Price stores should use Release (or stronger), not Relaxed
    let uses_relaxed = fn_body.contains("Ordering::Relaxed");
    assert!(!uses_relaxed,
        "update_last_price uses Ordering::Relaxed — price updates must use Release/SeqCst \
         for cross-thread visibility (bug B12)");
}

// =============================================================================
// Additional Concurrency Tests
// =============================================================================

#[test]
fn test_concurrent_hashmap_access() {
    use dashmap::DashMap;

    let map: Arc<DashMap<String, u64>> = Arc::new(DashMap::new());

    let mut handles = vec![];
    for i in 0..10 {
        let m = map.clone();
        handles.push(thread::spawn(move || {
            for j in 0..100 {
                let key = format!("key_{}_{}", i, j);
                m.insert(key, i * 100 + j);
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(map.len(), 1000);
}

#[test]
fn test_rwlock_readers() {
    let data = Arc::new(RwLock::new(vec![1, 2, 3, 4, 5]));

    let mut handles = vec![];
    for _ in 0..10 {
        let d = data.clone();
        handles.push(thread::spawn(move || {
            for _ in 0..100 {
                let guard = d.read();
                let _sum: i32 = guard.iter().sum();
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    // Should complete without contention issues
}

#[test]
fn test_rwlock_writer_priority() {
    let data = Arc::new(RwLock::new(0u64));

    let d = data.clone();
    let writer = thread::spawn(move || {
        for i in 0..100 {
            *d.write() = i;
        }
    });

    let readers: Vec<_> = (0..4).map(|_| {
        let d = data.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                let _ = *d.read();
            }
        })
    }).collect();

    writer.join().unwrap();
    for r in readers {
        r.join().unwrap();
    }

    assert_eq!(*data.read(), 99);
}
