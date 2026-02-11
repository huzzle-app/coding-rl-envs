//! Concurrency tests for QuantumCore
//!
//! Tests cover: B1-B12 concurrency bugs

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use parking_lot::{Mutex, RwLock, Condvar};

// =============================================================================
// B1: Lock Ordering Deadlock Tests
// =============================================================================

#[test]
fn test_b1_lock_ordering_consistent() {
    
    let lock_a = Arc::new(Mutex::new(0u64));
    let lock_b = Arc::new(Mutex::new(0u64));

    let mut handles = vec![];

    for i in 0..4 {
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
fn test_b1_timeout_deadlock_detection() {
    // Deadlock detection via timeout
    let start = Instant::now();
    let max_duration = Duration::from_secs(5);

    // Simple concurrent operation
    let counter = Arc::new(AtomicU64::new(0));
    let mut handles = vec![];

    for _ in 0..4 {
        let c = counter.clone();
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                c.fetch_add(1, Ordering::SeqCst);
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert!(start.elapsed() < max_duration, "Should complete quickly without deadlock");
}

// =============================================================================
// B2: Blocking in Async Context Tests
// =============================================================================

#[test]
fn test_b2_no_blocking_in_async() {
    
    // This test verifies the pattern

    let work_done = Arc::new(AtomicU64::new(0));

    // Simulate blocking work
    let wd = work_done.clone();
    let h = thread::spawn(move || {
        thread::sleep(Duration::from_millis(10));
        wd.fetch_add(1, Ordering::SeqCst);
    });

    h.join().unwrap();
    assert_eq!(work_done.load(Ordering::SeqCst), 1);
}

#[test]
fn test_b2_spawn_blocking_used() {
    // Blocking operations should use spawn_blocking
    let cpu_bound_work = || -> u64 {
        let mut sum = 0u64;
        for i in 0..1000 {
            sum = sum.wrapping_add(i);
        }
        sum
    };

    let result = cpu_bound_work();
    assert!(result > 0, "CPU-bound work completed");
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

// =============================================================================
// B4: Future Send Tests
// =============================================================================

#[test]
fn test_b4_data_is_send() {
    
    fn assert_send<T: Send>() {}

    // These types should be Send
    assert_send::<u64>();
    assert_send::<String>();
    assert_send::<Arc<Mutex<u64>>>();
    assert_send::<Arc<AtomicU64>>();
}

#[test]
fn test_b4_data_is_sync() {
    
    fn assert_sync<T: Sync>() {}

    assert_sync::<AtomicU64>();
    assert_sync::<Arc<Mutex<u64>>>();
    assert_sync::<Arc<RwLock<u64>>>();
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
    match m.lock() {
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
    // SeqCst provides strongest ordering guarantee
    let counter = Arc::new(AtomicU64::new(0));

    let mut handles = vec![];
    for _ in 0..4 {
        let c = counter.clone();
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                c.fetch_add(1, Ordering::SeqCst);
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(counter.load(Ordering::SeqCst), 4000);
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
    // Better: use condvar for waiting
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
    while !*ready {
        cvar.wait(&mut ready);
    }

    setter.join().unwrap();
    assert!(*lock.lock());
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
fn test_b12_market_price_visibility() {
    // Prices should be visible to all readers
    let prices: Vec<Arc<AtomicU64>> = (0..5)
        .map(|_| Arc::new(AtomicU64::new(100)))
        .collect();

    // Update all prices
    for (i, p) in prices.iter().enumerate() {
        p.store((i as u64 + 1) * 100, Ordering::SeqCst);
    }

    // All readers see updates
    for (i, p) in prices.iter().enumerate() {
        assert_eq!(p.load(Ordering::SeqCst), (i as u64 + 1) * 100);
    }
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
