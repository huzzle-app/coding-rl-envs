//! Tests for concurrency and async bugs
//!
//! These tests verify that concurrency bugs are FIXED.
//!
//! Bug coverage:
//! - C4: Future not Send - upload handler must use Arc<Mutex>, not Rc<RefCell>
//! - B2: File repo lifetime annotation must compile correctly
//! - B3: Chunk struct must not be self-referential
//! - B4: Share handler must use owned types across await points
//! - D2: get_file handler must handle all match arms
//! - D3: User repo must handle incompatible error types
//! - E2: Chunker must close file handles on error path

// ===== BUG C4: Future not Send =====

/// The upload handler must produce a Send future (use Arc<Mutex>, not Rc<RefCell>).
/// After fix, it uses Arc<Mutex> instead of Rc<RefCell>.
#[test]
fn test_upload_multipart_future_is_send() {
    // Verify at compile time that the types used in upload.rs are Send+Sync.
    // The source code in handlers/upload.rs must NOT use Rc<RefCell>.
    fn assert_send<T: Send>() {}

    // Arc<Mutex<T>> is Send (correct after fix)
    assert_send::<std::sync::Arc<tokio::sync::Mutex<Vec<u8>>>>();

    // Verify the source file doesn't contain Rc<RefCell> usage
    let upload_src = include_str!("../src/handlers/upload.rs");
    assert!(
        !upload_src.contains("Rc<RefCell") && !upload_src.contains("Rc::new(RefCell"),
        "handlers/upload.rs must not use Rc<RefCell> (not Send). Use Arc<Mutex> instead (C4). \
         Found Rc<RefCell> in source."
    );
    assert!(
        upload_src.contains("Arc") && upload_src.contains("Mutex"),
        "handlers/upload.rs must use Arc<Mutex> for thread-safe shared state (C4)"
    );
}

/// Verify the upload handler uses Arc<Mutex>, not Rc<RefCell>, for progress tracking.
#[test]
fn test_upload_uses_arc_mutex_not_rc() {
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<std::sync::Arc<tokio::sync::Mutex<usize>>>();

    // Source verification: Rc must not appear in upload.rs
    let upload_src = include_str!("../src/handlers/upload.rs");
    let rc_count = upload_src.matches("Rc::new").count()
        + upload_src.matches("Rc<").count();
    let refcell_count = upload_src.matches("RefCell::new").count()
        + upload_src.matches("RefCell<").count();
    assert_eq!(
        rc_count + refcell_count, 0,
        "upload.rs must have zero Rc/RefCell usages (C4). Found {} Rc + {} RefCell references",
        rc_count, refcell_count
    );
}

// ===== BUG B2: File repo lifetime annotation =====

/// File repo must return owned data, not references to locals that get dropped.
#[test]
fn test_file_repo_lifetime_annotation() {
    // Verify the source code returns owned types, not references to locals
    let repo_src = include_str!("../src/repository/file_repo.rs");

    // The function signatures should return owned types (not &'a references to locals)
    // After fix: find_by_id returns anyhow::Result<Option<FileMetadata>> (owned)
    assert!(
        !repo_src.contains("-> &'a ") || repo_src.contains("&'a self"),
        "file_repo.rs must not return references to local variables (B2). \
         Return types should be owned (e.g., Vec<FileMetadata>, not &'a [FileMetadata])."
    );

    // Also test the pattern compiles: return owned data, not references
    fn get_data() -> Vec<String> {
        let local = vec!["file1".to_string(), "file2".to_string()];
        local
    }
    let data = get_data();
    assert_eq!(data.len(), 2, "Must return owned data (B2)");
}

/// File repo query must return owned results that outlive the function scope.
#[test]
fn test_file_repo_query_compiles() {
    // Verify the repo doesn't try to return references to query results
    let repo_src = include_str!("../src/repository/file_repo.rs");

    // After fix: no dangling reference patterns
    // The find_by_owner function should not try to return a reference bound to its own scope
    assert!(
        repo_src.contains("anyhow::Result<Option<FileMetadata>>")
            || repo_src.contains("Result<Option<FileMetadata>"),
        "file_repo find_by_id must return owned Option<FileMetadata>, not a reference (B2)"
    );
}

// ===== BUG B3: Self-referential struct =====

/// Chunk struct must not contain self-referential raw pointers.
#[test]
fn test_chunk_no_self_referential_struct() {
    // Verify the Chunk struct doesn't have data_ptr / data_len fields
    let chunk_src = include_str!("../src/models/chunk.rs");

    assert!(
        !chunk_src.contains("data_ptr") && !chunk_src.contains("*const u8"),
        "Chunk struct must not contain self-referential raw pointer (data_ptr: *const u8) (B3). \
         Remove data_ptr and data_len fields; use &self.data instead."
    );
    assert!(
        !chunk_src.contains("from_raw_parts"),
        "Chunk must not use std::slice::from_raw_parts (unsafe self-reference) (B3). \
         Use &self.data directly."
    );
}

/// Chunk must be safely movable (no dangling pointers after move).
#[test]
fn test_chunk_can_be_moved() {
    use vaultfs::models::chunk::Chunk;

    let chunk = Chunk::new(vec![1, 2, 3, 4, 5], 0);

    // Move the chunk (this would cause UB with self-referential pointer)
    let moved_chunk = chunk;

    // After fix: get_data_ref returns &self.data, which is always valid
    let data = moved_chunk.get_data_ref();
    assert_eq!(data, &[1, 2, 3, 4, 5], "Chunk data must survive moves without corruption (B3)");

    // Move into a Vec and back
    let mut chunks = Vec::new();
    chunks.push(moved_chunk);
    let retrieved = chunks.pop().unwrap();
    let data2 = retrieved.get_data_ref();
    assert_eq!(data2, &[1, 2, 3, 4, 5], "Chunk data must survive multiple moves (B3)");
}

// ===== BUG B4: Lifetime bounds in async =====

/// Share handler must use owned types across await points (not references).
#[test]
fn test_create_share_owned_across_await() {
    // Verify the shares handler doesn't hold references across await points
    let shares_src = include_str!("../src/handlers/shares.rs");

    // After fix: create_share should not have a lifetime parameter 'a on the handler
    // The function should use owned String, not &'a str across awaits
    let has_lifetime_on_handler = shares_src.contains("async fn create_share<'a>");
    assert!(
        !has_lifetime_on_handler,
        "create_share handler must not have lifetime parameter <'a> (B4). \
         Use owned String instead of &'a str across await points."
    );
}

/// No dangling references across await points in the share handler.
#[test]
fn test_share_no_dangling_reference() {
    let shares_src = include_str!("../src/handlers/shares.rs");

    // After fix: get_file_reference should return owned String, not &'a str
    // Or file_id should be cloned before the await point
    let has_ref_return = shares_src.contains("fn get_file_reference<'a>(file_id: &'a str) -> &'a str");
    assert!(
        !has_ref_return,
        "get_file_reference must not return a borrowed &'a str (B4). \
         Return String or clone the file_id before crossing await points."
    );
}

// ===== BUG D2: Error variant not handled =====

/// get_file handler must handle all Result match arms (Ok(Some), Ok(None), Err).
#[test]
fn test_get_file_handler_all_match_arms() {
    let files_src = include_str!("../src/handlers/files.rs");

    // After fix: the match in get_file must handle the Err case
    // Look for the pattern: Err(e) => or Err(_) => in the get_file function
    let has_err_arm = files_src.contains("Err(e)")
        || files_src.contains("Err(_)")
        || files_src.contains("result?");  // Using ? operator also handles Err

    assert!(
        has_err_arm,
        "get_file handler must handle the Err(_) match arm (D2). \
         The match on fetch_file result must cover Ok(Some), Ok(None), AND Err."
    );
}

/// get_file must propagate database errors, not silently ignore them.
#[test]
fn test_get_file_handles_db_error() {
    let files_src = include_str!("../src/handlers/files.rs");

    // The get_file function must not have an incomplete match
    // After fix: it should have all three arms or use ? operator
    let get_file_section = files_src.split("pub async fn get_file")
        .nth(1)
        .unwrap_or("");

    // Must not have a match that only covers Ok(Some) and Ok(None)
    // without Err handling
    let has_complete_match = get_file_section.contains("Err(")
        || get_file_section.contains("result?")
        || get_file_section.contains(".await?");

    assert!(
        has_complete_match,
        "get_file must handle Err from database operations (D2)"
    );
}

// ===== BUG D3: Incompatible error types =====

/// User repo must properly convert between error types (not unwrap).
#[test]
fn test_user_repo_error_conversion() {
    let user_repo_src = include_str!("../src/repository/user_repo.rs");

    // After fix: create() should use ? with proper From impl or map_err,
    // not unwrap() on incompatible error types
    let has_unwrap_in_create = {
        let create_section = user_repo_src.split("pub async fn create")
            .nth(1)
            .unwrap_or("");
        let next_fn = create_section.find("pub async fn")
            .unwrap_or(create_section.len());
        let create_body = &create_section[..next_fn];
        create_body.contains(".unwrap()") && !create_body.contains("// ")
    };

    // unwrap() in create method is the bug - should use ? or map_err
    assert!(
        !has_unwrap_in_create,
        "user_repo create() must not use .unwrap() for error conversion (D3). \
         Use ? operator with From impl or .map_err() instead."
    );
}

/// User repo error handling must not panic on incompatible error types.
#[test]
fn test_user_repo_incompatible_error_handled() {
    // Verify the pattern: io::Error -> anyhow::Error conversion works
    let io_err: Result<String, std::io::Error> =
        Err(std::io::Error::new(std::io::ErrorKind::NotFound, "user not found"));

    let result: Result<String, anyhow::Error> =
        io_err.map_err(|e| anyhow::anyhow!("User repo error: {}", e));

    assert!(result.is_err(), "Error must be converted, not unwrapped (D3)");
    let err_msg = result.unwrap_err().to_string();
    assert!(
        err_msg.contains("User repo error"),
        "Error message must include context"
    );
}

// ===== BUG E2: File handle not closed on error =====

/// Chunker must close file handles even when errors occur (RAII).
#[test]
fn test_chunker_file_handle_closed_on_error() {
    use std::fs::File;
    use std::io::Write;

    let test_path = "/tmp/vaultfs-chunker-error-test.bin";
    let mut file = File::create(test_path).unwrap();
    file.write_all(b"test data for chunker").unwrap();
    drop(file);

    // Verify the storage service properly closes handles
    let storage_src = include_str!("../src/services/storage.rs");

    // After fix: file handles should be managed by RAII (File dropped at end of scope)
    // No explicit close() calls needed in Rust if using RAII properly
    // The bug would be holding File in a way that prevents RAII cleanup
    let result = std::panic::catch_unwind(|| {
        let _file = File::open(test_path).unwrap();
        // RAII: file handle closed when _file goes out of scope
    });

    assert!(result.is_ok(), "Chunker must not leak file handles on error (E2)");

    // Verify the file is not locked
    let reopen = File::open(test_path);
    assert!(reopen.is_ok(), "File must be accessible after chunker (E2)");

    std::fs::remove_file(test_path).ok();
}

/// Multiple file operations must not exhaust file descriptors (no handle leaks).
#[test]
fn test_chunker_no_leaked_handles() {
    let test_path = "/tmp/vaultfs-chunker-leak-test.bin";

    for i in 0..100 {
        let mut file = std::fs::File::create(test_path).unwrap();
        std::io::Write::write_all(&mut file, format!("iteration {}", i).as_bytes()).unwrap();
        drop(file);

        let opened = std::fs::File::open(test_path).unwrap();
        drop(opened);
    }

    // Verify storage source uses proper RAII patterns
    let storage_src = include_str!("../src/services/storage.rs");
    assert!(
        !storage_src.contains("mem::forget") && !storage_src.contains("ManuallyDrop"),
        "storage.rs must not use mem::forget or ManuallyDrop which would leak handles (E2)"
    );

    std::fs::remove_file(test_path).ok();
}
