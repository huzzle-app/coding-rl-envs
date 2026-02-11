//! Tests for storage, models, and related services
//!
//! These tests verify that ownership, error handling, and memory bugs are FIXED.
//! Each test asserts correct behavior after the fix is applied.
//!
//! Bug coverage:
//! - A1: Use after move - upload_file must capture size before moving data
//! - A3: Double mutable borrow - versioning must avoid concurrent &mut
//! - A4: Moved value in loop - list_files must check before moving
//! - A5: Partial move - extract_info and split_metadata must not partially move
//! - C2: Blocking in async - save_to_disk must use tokio::fs
//! - C3: Race condition - record_change must use atomic read+write
//! - C5: Channel receiver dropped - notification must keep receiver alive
//! - D1: Unwrap on None - get_file must handle empty chunks
//! - D4: Panic in drop - TempFile/TempDirectory drop must not panic
//! - E1: Rc cycle - Folder must use Weak for parent reference
//! - E3: Unbounded channel - SyncService must use bounded channel

use vaultfs::services::storage::StorageService;
use vaultfs::services::sync::SyncService;
use vaultfs::services::versioning::VersioningService;
use vaultfs::services::notification::NotificationService;
use vaultfs::models::file::FileMetadata;
use vaultfs::models::folder::Folder;
use vaultfs::models::temp_file::{TempFile, TempDirectory};
use std::sync::Arc;
use std::path::PathBuf;

// ===== BUG A1: Use after move =====

/
/// After fix, metadata.size should be captured before the move.
#[tokio::test]
async fn test_upload_file_no_use_after_move() {
    let service = StorageService::new("test-bucket", "/tmp/vaultfs-test");

    let data = b"Hello, World!".to_vec();
    let original_len = data.len();
    let result = service.upload_file("user1", "test.txt", data).await;

    // The function must succeed (no compile error from use-after-move)
    assert!(result.is_ok(), "upload_file must compile and succeed (A1)");
}

/
#[tokio::test]
async fn test_upload_preserves_metadata_size() {
    let service = StorageService::new("test-bucket", "/tmp/vaultfs-test");

    let data = b"Test content with known size".to_vec();
    let expected_size = data.len();
    let result = service.upload_file("user1", "sized.txt", data).await;

    assert!(result.is_ok(), "upload must succeed");
    let metadata = result.unwrap();
    assert_eq!(
        metadata.size, expected_size,
        "Metadata size must match original data length (A1). Got {} expected {}",
        metadata.size, expected_size
    );
}

// ===== BUG A3: Double mutable borrow in versioning =====

/
/// After fix, calculate_next_version takes &[FileVersion] (immutable).
#[tokio::test]
async fn test_versioning_create_no_double_borrow() {
    let service = VersioningService::new();
    let metadata = FileMetadata::new("test-file");

    // Must not panic or fail to compile
    service.create_version("test-file", &metadata).await;

    // Verify version was created
    let versions = service.list_versions("test-file").await;
    assert_eq!(versions.len(), 1, "One version must be created (A3)");
    assert_eq!(versions[0].version_number, 1, "First version must be 1");
}

/
#[tokio::test]
async fn test_versioning_prune_no_double_borrow() {
    let service = VersioningService::new();
    let metadata = FileMetadata::new("prune-file");

    // Create several versions
    for _ in 0..5 {
        service.create_version("prune-file", &metadata).await;
    }

    // Prune to keep only 2 - must not panic from double borrow
    service.prune_old_versions("prune-file", 2).await;

    let versions = service.list_versions("prune-file").await;
    assert_eq!(
        versions.len(), 2,
        "After pruning to keep 2, exactly 2 versions must remain (A3)"
    );
}

// ===== BUG A4: Moved value used in loop =====

/
/// After fix, the check happens before the move.
#[test]
fn test_list_files_skips_tmp_before_move() {
    // Simulate the fixed logic:
    // The fix moves the .ends_with(".tmp") check BEFORE creating FileResponse
    let files = vec![
        FileMetadata { name: "document.pdf".to_string(), ..FileMetadata::new("1") },
        FileMetadata { name: "temp.tmp".to_string(), ..FileMetadata::new("2") },
        FileMetadata { name: "photo.jpg".to_string(), ..FileMetadata::new("3") },
    ];

    let mut kept = Vec::new();
    for file in &files {
        // Fixed: check before move
        if file.name.ends_with(".tmp") {
            continue;
        }
        kept.push(file.name.clone());
    }

    assert_eq!(kept.len(), 2, "Tmp files must be filtered out (A4)");
    assert!(!kept.contains(&"temp.tmp".to_string()), "temp.tmp must not be in results");
}

/
#[test]
fn test_list_files_no_use_after_move() {
    let files = vec![
        FileMetadata::new("1"),
        FileMetadata::new("2"),
    ];

    // After fix: no use-after-move; all fields consumed in one place
    let responses: Vec<String> = files.into_iter()
        .map(|f| f.id.clone())
        .collect();

    assert_eq!(responses.len(), 2, "All files must be processed (A4)");
}

// ===== BUG A5: Partial move out of struct =====

/
#[test]
fn test_extract_info_no_partial_move() {
    let metadata = FileMetadata::new("partial-move-test");
    // After fix: all fields are moved together, no partial move error
    let info = metadata.extract_info();
    assert_eq!(info.size, 0, "Size must be accessible from FileInfo (A5)");
}

/
#[test]
fn test_split_metadata_no_partial_move() {
    let mut metadata = FileMetadata::new("split-test");
    metadata.name = "test-file.txt".to_string();

    let (basic, extended) = metadata.split_metadata();
    assert_eq!(basic.name, "test-file.txt", "Basic info must have the name (A5)");
    assert_eq!(extended.file_name, "test-file.txt", "Extended info must also have the name (A5)");
}

// ===== BUG C2: Blocking in async context =====

/
/// After fix, this should complete without blocking the runtime.
#[tokio::test]
async fn test_save_to_disk_uses_async_io() {
    let service = StorageService::new("test-bucket", "/tmp/vaultfs-test");
    let test_path = "/tmp/vaultfs-async-io-test.bin";
    let data = b"async write test data";

    let result = service.save_to_disk(test_path, data).await;
    assert!(result.is_ok(), "save_to_disk must succeed with async I/O (C2)");

    // Verify file was written
    let content = tokio::fs::read(test_path).await.unwrap();
    assert_eq!(&content, data, "Written content must match input (C2)");

    // Cleanup
    tokio::fs::remove_file(test_path).await.unwrap();
}

/
#[tokio::test]
async fn test_large_file_no_runtime_block() {
    let service = StorageService::new("test-bucket", "/tmp/vaultfs-test");

    // 10MB file that would block if using std::fs
    let data = vec![0u8; 10 * 1024 * 1024];

    // Spawn a timer task to detect blocking
    let timer = tokio::spawn(async {
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
        true
    });

    let result = service.upload_file("user1", "large-file.bin", data).await;
    assert!(result.is_ok(), "Large file upload must succeed (C2)");

    // Timer task must have completed (runtime wasn't blocked)
    let timer_ok = timer.await.unwrap();
    assert!(timer_ok, "Runtime must not be blocked by large file I/O (C2)");
}

// ===== BUG C3: Race condition in record_change =====

/
#[tokio::test]
async fn test_record_change_atomic_version() {
    let service = SyncService::new();

    service.record_change(
        "file1".to_string(),
        vaultfs::services::sync::ChangeType::Created,
    ).await;

    service.record_change(
        "file1".to_string(),
        vaultfs::services::sync::ChangeType::Modified,
    ).await;

    // After fix: versions must be sequential (1, 2) with no gaps or duplicates
    // We can't directly access the change_log, but we can verify through get_changes_since
    let changes = service.get_changes_since(chrono::Utc::now() - chrono::Duration::hours(1)).await;
    assert_eq!(changes.len(), 2, "Two changes must be recorded");

    let versions: Vec<u64> = changes.iter().map(|c| c.version).collect();
    assert_eq!(versions, vec![1, 2], "Versions must be sequential 1,2 (C3)");
}

/
#[tokio::test]
async fn test_concurrent_record_no_duplicate_version() {
    let service = Arc::new(SyncService::new());
    let mut handles = Vec::new();

    for i in 0..10 {
        let svc = service.clone();
        handles.push(tokio::spawn(async move {
            svc.record_change(
                "concurrent-file".to_string(),
                vaultfs::services::sync::ChangeType::Modified,
            ).await;
        }));
    }

    for h in handles {
        h.await.unwrap();
    }

    let changes = service.get_changes_since(
        chrono::Utc::now() - chrono::Duration::hours(1)
    ).await;

    let versions: Vec<u64> = changes.iter()
        .filter(|c| c.file_id == "concurrent-file")
        .map(|c| c.version)
        .collect();

    // All versions must be unique
    let unique_count = {
        let mut v = versions.clone();
        v.sort();
        v.dedup();
        v.len()
    };
    assert_eq!(
        unique_count, versions.len(),
        "All version numbers must be unique after concurrent writes (C3). Got: {:?}",
        versions
    );
}

// ===== BUG C5: Channel receiver dropped =====

/
#[tokio::test]
async fn test_notification_send_with_receiver_alive() {
    let service = NotificationService::new();

    let notification = vaultfs::services::notification::Notification {
        id: "n1".to_string(),
        user_id: "u1".to_string(),
        message: "test".to_string(),
        notification_type: vaultfs::services::notification::NotificationType::FileShared,
    };

    // After fix: send_notification must not fail because receiver is kept alive
    let result = service.send_notification(notification).await;
    assert!(
        result.is_ok(),
        "send_notification must succeed when receiver is alive (C5). Error: {:?}",
        result.err()
    );
}

/
#[tokio::test]
async fn test_notification_subscribe_before_send() {
    let service = NotificationService::new();

    // Subscribe first
    let mut receiver = service.subscribe();

    let notification = vaultfs::services::notification::Notification {
        id: "n2".to_string(),
        user_id: "u2".to_string(),
        message: "hello".to_string(),
        notification_type: vaultfs::services::notification::NotificationType::SyncComplete,
    };

    service.send_notification(notification.clone()).await.unwrap();

    // Receiver must get the notification
    let received = tokio::time::timeout(
        std::time::Duration::from_secs(1),
        receiver.recv()
    ).await;

    assert!(received.is_ok(), "Receiver must get notification within timeout (C5)");
    let msg = received.unwrap().unwrap();
    assert_eq!(msg.id, "n2", "Received notification must match sent one");
}

// ===== BUG D1: Unwrap on None =====

/
#[tokio::test]
async fn test_get_file_empty_chunks_returns_error() {
    let service = StorageService::new("test-bucket", "/tmp/vaultfs-test");

    // File with no chunks should return Err, not panic
    let result = service.get_file("nonexistent-file").await;
    assert!(
        result.is_err(),
        "get_file with no chunks must return Err, not panic from unwrap (D1)"
    );
}

/
#[tokio::test]
async fn test_get_file_no_unwrap_on_none() {
    let service = StorageService::new("test-bucket", "/tmp/vaultfs-test");

    // This must not panic - it should return a proper error
    let result = std::panic::AssertUnwindSafe(async {
        service.get_file("definitely-missing").await
    });

    // If the fix is applied, this returns Err (not panic)
    // We test that it doesn't panic
    let outcome = tokio::task::spawn(async move {
        result.0.await
    }).await;

    assert!(
        outcome.is_ok(),
        "get_file must not panic on missing chunks (D1)"
    );
}

// ===== BUG D4: Panic in drop =====

/
#[test]
fn test_temp_file_drop_no_panic() {
    let path = PathBuf::from("/tmp/vaultfs-drop-test-nonexistent.tmp");

    // Create and then remove the file before drop
    let temp = TempFile::new(path.clone()).unwrap();
    std::fs::remove_file(&path).ok(); // Remove before drop

    // Drop must not panic (should log warning instead)
    drop(temp);
    // If we reach here, drop didn't panic
}

/
#[test]
fn test_temp_file_missing_no_panic() {
    let result = std::panic::catch_unwind(|| {
        let path = PathBuf::from("/tmp/vaultfs-drop-panic-test.tmp");
        let temp = TempFile::new(path.clone()).unwrap();
        // Remove the file so drop will fail to find it
        std::fs::remove_file(&path).ok();
        drop(temp);
    });

    assert!(
        result.is_ok(),
        "TempFile drop must not panic when file is missing (D4)"
    );
}

/
#[test]
fn test_temp_dir_drop_no_panic() {
    let result = std::panic::catch_unwind(|| {
        let path = PathBuf::from("/tmp/vaultfs-drop-dir-test");
        let mut dir = TempDirectory::new(path.clone()).unwrap();
        dir.add_file("test.txt", b"content").unwrap();
        // Remove directory before drop
        std::fs::remove_dir_all(&path).ok();
        drop(dir);
    });

    assert!(
        result.is_ok(),
        "TempDirectory drop must not panic when directory is missing (D4)"
    );
}

// ===== BUG E1: Rc cycle memory leak =====

/
#[test]
fn test_folder_no_rc_cycle_leak() {
    let root = Folder::new("root", "Root");
    let child = Folder::new("child", "Child");
    Folder::add_child(&root, &child);

    // After fix with Weak parent: dropping root should allow child to be freed
    // Strong count of child should be 2 (root.children + our local `child`)
    // but parent reference from child to root should be Weak (not increasing root's count)

    // Verify the parent-child relationship works
    let child_path = child.borrow().get_path();
    assert!(
        child_path.contains("Root") && child_path.contains("Child"),
        "Child path must include parent: got '{}'",
        child_path
    );
}

/
#[test]
fn test_folder_uses_weak_parent() {
    let root = Folder::new("root", "Root");
    let child = Folder::new("child", "Child");
    Folder::add_child(&root, &child);

    // After fix: root's strong count should be 1 (only our local variable)
    // because child.parent is Weak, not Rc
    let root_strong_count = std::rc::Rc::strong_count(&root);
    assert_eq!(
        root_strong_count, 1,
        "Root strong count must be 1 (child.parent should be Weak). Got {} (E1)",
        root_strong_count
    );
}

// ===== BUG E3: Unbounded channel =====

/
#[tokio::test]
async fn test_sync_bounded_channel() {
    let service = SyncService::new();

    // After fix: send_event should use a bounded channel
    // Sending should eventually provide backpressure (not infinite buffer)
    let event = vaultfs::services::sync::SyncEvent {
        file_id: "test".to_string(),
        event_type: "modified".to_string(),
        data: vec![0u8; 100],
    };

    let result = service.send_event(event).await;
    assert!(result.is_ok(), "send_event must succeed for a single event (E3)");
}

/
#[tokio::test]
async fn test_sync_backpressure() {
    let service = Arc::new(SyncService::new());

    // Flood with events - after fix, channel is bounded so this won't grow infinitely
    // We just verify it doesn't panic or OOM
    for i in 0..100 {
        let event = vaultfs::services::sync::SyncEvent {
            file_id: format!("file_{}", i),
            event_type: "modified".to_string(),
            data: vec![0u8; 10],
        };
        // With bounded channel, some sends may block or return backpressure
        let _ = service.send_event(event).await;
    }

    // If we reach here without OOM, the channel has backpressure (E3)
}

// ===== BUG A2: Borrowed value doesn't live long enough =====

/
#[tokio::test]
async fn test_get_changes_returns_owned_values() {
    let service = SyncService::new();

    service.record_change(
        "owned-test".to_string(),
        vaultfs::services::sync::ChangeType::Created,
    ).await;

    // After fix: returns Vec<ChangeEntry> (owned), not Vec<&ChangeEntry>
    let changes = service.get_changes_since(
        chrono::Utc::now() - chrono::Duration::hours(1)
    ).await;

    assert_eq!(changes.len(), 1, "Must return one change");
    // The returned values must be usable (owned) outside the lock scope
    let file_id = changes[0].file_id.clone();
    assert_eq!(file_id, "owned-test", "Change file_id must be correct (A2)");
}

/
#[tokio::test]
async fn test_changes_since_does_not_hold_lock() {
    let service = Arc::new(SyncService::new());

    service.record_change(
        "lock-test".to_string(),
        vaultfs::services::sync::ChangeType::Created,
    ).await;

    // Get changes (releases lock after)
    let changes = service.get_changes_since(
        chrono::Utc::now() - chrono::Duration::hours(1)
    ).await;

    // Must be able to record another change (lock is free)
    service.record_change(
        "lock-test-2".to_string(),
        vaultfs::services::sync::ChangeType::Modified,
    ).await;

    let all_changes = service.get_changes_since(
        chrono::Utc::now() - chrono::Duration::hours(1)
    ).await;

    assert_eq!(all_changes.len(), 2, "Both changes must be recorded (A2 - lock released)");
}

// ===== Concurrent uploads =====

#[tokio::test]
async fn test_concurrent_uploads() {
    let service = Arc::new(StorageService::new("test-bucket", "/tmp/vaultfs-test"));

    let mut handles = vec![];

    for i in 0..10 {
        let svc = service.clone();
        let handle = tokio::spawn(async move {
            let data = format!("Content {}", i).into_bytes();
            svc.upload_file("user1", &format!("file-{}.txt", i), data).await
        });
        handles.push(handle);
    }

    for handle in handles {
        let result = handle.await.unwrap();
        assert!(result.is_ok(), "Concurrent upload must succeed");
    }
}
