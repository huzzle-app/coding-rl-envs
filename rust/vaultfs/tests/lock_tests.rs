//! Tests for lock manager
//!
//! These tests verify that concurrency bugs are FIXED.
//! Each test asserts correct (safe) behavior after the fix is applied.
//!
//! Bug coverage:
//! - C1: Deadlock from inconsistent lock ordering - must complete without timeout

use vaultfs::services::lock_manager::LockManager;
use std::sync::Arc;
use std::time::Duration;

#[tokio::test]
async fn test_file_lock_acquire_release() {
    let manager = LockManager::new();

    let result = manager.acquire_file_lock("user1", "file1").await;
    assert!(result.is_ok(), "Acquiring a file lock must succeed");

    let release = manager.release_file_lock("user1", "file1").await;
    assert!(release.is_ok(), "Releasing a file lock must succeed");
}

#[tokio::test]
async fn test_lock_exclusion() {
    let manager = Arc::new(LockManager::new());

    // First lock
    manager.acquire_file_lock("user1", "file1").await.unwrap();

    let manager2 = manager.clone();

    // Second lock attempt should wait or fail (exclusive lock)
    let handle = tokio::spawn(async move {
        tokio::time::timeout(
            Duration::from_millis(100),
            manager2.acquire_file_lock("user2", "file1")
        ).await
    });

    // Should timeout because file is locked
    let result = handle.await.unwrap();
    assert!(result.is_err(), "Lock must be exclusive: second acquire should timeout");

    // Release and verify it can be acquired again
    manager.release_file_lock("user1", "file1").await.unwrap();
}

/
/// The fix ensures consistent lock ordering (e.g., always file before user,
/// or sorted alphabetically).
#[tokio::test]
async fn test_no_deadlock_consistent_lock_order() {
    let manager = Arc::new(LockManager::new());

    let manager1 = manager.clone();
    let manager2 = manager.clone();

    // Task 1: lock_file_for_user("file1", "user1")
    let handle1 = tokio::spawn(async move {
        manager1.lock_file_for_user("file1", "user1").await
    });

    // Task 2: lock_user_files("user2", ["file1"])
    let handle2 = tokio::spawn(async move {
        manager2.lock_user_files("user2", &["file1".to_string()]).await
    });

    // After the fix, both tasks must complete within 2 seconds (no deadlock).
    let result = tokio::time::timeout(
        Duration::from_secs(2),
        async {
            let r1 = handle1.await;
            let r2 = handle2.await;
            (r1, r2)
        }
    ).await;

    assert!(
        result.is_ok(),
        "Both lock operations must complete without deadlock (C1). \
         Timed out after 2s, indicating a deadlock."
    );
}

/
#[tokio::test]
async fn test_lock_file_for_user_completes() {
    let manager = LockManager::new();

    let result = tokio::time::timeout(
        Duration::from_secs(1),
        manager.lock_file_for_user("file_a", "user_b")
    ).await;

    assert!(
        result.is_ok(),
        "lock_file_for_user must complete without hanging (C1)"
    );
}

/
#[tokio::test]
async fn test_lock_user_files_completes() {
    let manager = LockManager::new();

    let files = vec![
        "file_c".to_string(),
        "file_a".to_string(),
        "file_b".to_string(),
    ];

    let result = tokio::time::timeout(
        Duration::from_secs(1),
        manager.lock_user_files("user_x", &files)
    ).await;

    assert!(
        result.is_ok(),
        "lock_user_files must complete for multiple files without deadlock (C1)"
    );

    let guards = result.unwrap();
    assert_eq!(
        guards.len(), 3,
        "Must return one guard per file"
    );
}

/// Multiple user locks can coexist (different users, different files).
#[test]
fn test_multiple_user_locks() {
    let manager = LockManager::new();
    let rt = tokio::runtime::Runtime::new().unwrap();

    rt.block_on(async {
        manager.acquire_user_lock("user1").await.unwrap();
        manager.acquire_user_lock("user2").await.unwrap();
        manager.acquire_user_lock("user3").await.unwrap();

        // Release in different order should not cause issues
        manager.release_user_lock("user2").await.unwrap();
        manager.release_user_lock("user1").await.unwrap();
        manager.release_user_lock("user3").await.unwrap();
    });
}

/// Concurrent lock_file_for_user calls with interleaved orderings must not deadlock.
#[tokio::test]
async fn test_concurrent_interleaved_locks_no_deadlock() {
    let manager = Arc::new(LockManager::new());
    let mut handles = Vec::new();

    for i in 0..5 {
        let m = manager.clone();
        let handle = tokio::spawn(async move {
            let file = format!("file_{}", i % 3);
            let user = format!("user_{}", i);
            let _guard = m.lock_file_for_user(&file, &user).await;
            tokio::time::sleep(Duration::from_millis(5)).await;
        });
        handles.push(handle);
    }

    let result = tokio::time::timeout(Duration::from_secs(5), async {
        for h in handles {
            h.await.unwrap();
        }
    }).await;

    assert!(
        result.is_ok(),
        "Concurrent interleaved lock operations must complete without deadlock"
    );
}
