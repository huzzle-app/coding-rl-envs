//! Security tests for VaultFS
//!
//! These tests verify that security bugs are FIXED.
//! Each test asserts correct (safe) behavior after the fix is applied.
//!
//! Bug coverage:
//! - F1: Path traversal must be rejected
//! - F2: SQL injection must be parameterized
//! - F3: Timing attack - constant-time comparison required
//! - F4: Unsafe mmap - must keep file handle alive, check bounds

use vaultfs::middleware::auth;
use vaultfs::repository::search;
use vaultfs::storage::mmap::MappedFile;
use vaultfs::utils;
use std::path::Path;
use std::time::{Duration, Instant};

// ===== BUG F3: API key verification must be constant-time =====

#[test]
fn test_api_key_verification_correct() {
    let expected = "secret_key_12345";
    let correct = "secret_key_12345";
    let incorrect = "wrong_key_99999";

    assert!(auth::verify_api_key(correct, expected), "Correct key must be accepted");
    assert!(!auth::verify_api_key(incorrect, expected), "Incorrect key must be rejected");
}

/
/// After fix, the source must use constant-time comparison (ct_eq or similar).
/// We also do a timing measurement with wide tolerance as a secondary check.
#[test]
fn test_api_key_constant_time_comparison() {
    // Primary check: verify the source code uses constant-time comparison
    let auth_src = include_str!("../src/middleware/auth.rs");

    // After fix: verify_api_key must use ct_eq, constant_time_eq, or subtle crate
    let verify_section = auth_src.split("fn verify_api_key")
        .nth(1)
        .unwrap_or("");
    let next_fn = verify_section.find("\npub fn").or(verify_section.find("\nfn"))
        .unwrap_or(verify_section.len());
    let verify_body = &verify_section[..next_fn];

    let uses_constant_time = verify_body.contains("ct_eq")
        || verify_body.contains("constant_time")
        || verify_body.contains("ConstantTimeEq")
        || verify_body.contains("subtle::");

    assert!(
        uses_constant_time,
        "verify_api_key must use constant-time comparison (ct_eq from subtle crate) (F3). \
         Found non-constant-time comparison (==) which leaks timing information."
    );

    // Secondary: timing measurement (wider tolerance to reduce flakiness)
    let expected = "abcdefghijklmnopqrstuvwxyz123456789abcdefghijklmnopqrstuvwxyz";
    let wrong_first = "Xbcdefghijklmnopqrstuvwxyz123456789abcdefghijklmnopqrstuvwxyz";
    let wrong_last = "abcdefghijklmnopqrstuvwxyz123456789abcdefghijklmnopqrstuvwxyX";

    let iterations = 100_000;

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = auth::verify_api_key(wrong_first, expected);
    }
    let wrong_first_time = start.elapsed();

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = auth::verify_api_key(wrong_last, expected);
    }
    let wrong_last_time = start.elapsed();

    let ratio = wrong_first_time.as_nanos() as f64 / wrong_last_time.as_nanos().max(1) as f64;
    assert!(
        ratio > 0.2 && ratio < 5.0,
        "Timing ratio {:.2} suggests non-constant-time comparison (F3). \
         wrong_first={:?}, wrong_last={:?}",
        ratio, wrong_first_time, wrong_last_time
    );
}

/
#[test]
fn test_signature_constant_time_comparison() {
    // Primary check: verify source uses constant-time comparison
    let auth_src = include_str!("../src/middleware/auth.rs");

    let verify_section = auth_src.split("fn verify_signature")
        .nth(1)
        .unwrap_or("");
    let next_fn = verify_section.find("\npub fn").or(verify_section.find("\nfn"))
        .unwrap_or(verify_section.len());
    let verify_body = &verify_section[..next_fn];

    // Must not have early return inside the byte-comparison loop
    let has_early_return_in_loop = verify_body.contains("if a != b")
        || verify_body.contains("if *a != *b");
    assert!(
        !has_early_return_in_loop,
        "verify_signature must not early-exit on first mismatch (F3). \
         Use ct_eq or accumulate XOR differences."
    );

    let uses_constant_time = verify_body.contains("ct_eq")
        || verify_body.contains("constant_time")
        || verify_body.contains("xor")
        || verify_body.contains("^=");
    assert!(
        uses_constant_time,
        "verify_signature must use constant-time comparison (F3)"
    );

    let expected: Vec<u8> = (0..64).collect();
    let mut wrong_first = expected.clone();
    wrong_first[0] = 255;
    let mut wrong_last = expected.clone();
    wrong_last[63] = 255;

    assert!(!auth::verify_signature(&wrong_first, &expected));
    assert!(!auth::verify_signature(&wrong_last, &expected));

    let iterations = 100_000;

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = auth::verify_signature(&wrong_first, &expected);
    }
    let t1 = start.elapsed();

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = auth::verify_signature(&wrong_last, &expected);
    }
    let t2 = start.elapsed();

    let ratio = t1.as_nanos() as f64 / t2.as_nanos().max(1) as f64;
    assert!(
        ratio > 0.2 && ratio < 5.0,
        "Signature comparison timing ratio {:.2} indicates early exit (F3). t1={:?}, t2={:?}",
        ratio, t1, t2
    );
}

/
#[test]
fn test_hash_constant_time_comparison() {
    // Primary check: verify source uses constant-time comparison
    let auth_src = include_str!("../src/middleware/auth.rs");

    let verify_section = auth_src.split("fn verify_hash")
        .nth(1)
        .unwrap_or("");
    let next_fn = verify_section.find("\npub fn").or(verify_section.find("\nfn"))
        .unwrap_or(verify_section.len());
    let verify_body = &verify_section[..next_fn];

    // After fix: must not use simple == comparison on hash strings
    let uses_plain_eq = verify_body.contains("provided_hash == stored_hash")
        || verify_body.contains("provided == expected");
    assert!(
        !uses_plain_eq,
        "verify_hash must not use plain == comparison (F3). \
         Use ct_eq from subtle crate for constant-time comparison."
    );

    let stored = "a]cdefghijklmnopqrstuvwxyz0123456789abcdef0123456789abcdef01234567";
    let wrong_first = "Xbcdefghijklmnopqrstuvwxyz0123456789abcdef0123456789abcdef01234567";
    let wrong_last = "a]cdefghijklmnopqrstuvwxyz0123456789abcdef0123456789abcdef0123456X";

    assert!(!auth::verify_hash(wrong_first, stored));
    assert!(!auth::verify_hash(wrong_last, stored));

    let iterations = 100_000;

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = auth::verify_hash(wrong_first, stored);
    }
    let t1 = start.elapsed();

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = auth::verify_hash(wrong_last, stored);
    }
    let t2 = start.elapsed();

    let ratio = t1.as_nanos() as f64 / t2.as_nanos().max(1) as f64;
    assert!(
        ratio > 0.2 && ratio < 5.0,
        "Hash comparison timing ratio {:.2} indicates early exit (F3). t1={:?}, t2={:?}",
        ratio, t1, t2
    );
}

// ===== BUG F2: SQL injection - queries must be parameterized =====

/
/// After fix, dangerous characters must be absent from the generated SQL.
#[test]
fn test_search_uses_parameterized_query() {
    // Primary: verify source uses parameterized queries
    let search_src = include_str!("../src/repository/search.rs");
    let build_fn = search_src.split("fn build_search_query")
        .nth(1)
        .unwrap_or("");
    let next_fn = build_fn.find("\npub fn").or(build_fn.find("\nfn"))
        .unwrap_or(build_fn.len());
    let fn_body = &build_fn[..next_fn];

    // After fix: must use $1/$2 placeholders or .bind(), not format!() with raw user input
    let uses_format_interpolation = fn_body.contains("format!(")
        && fn_body.contains("{}");
    let uses_parameterized = fn_body.contains("$1")
        || fn_body.contains("$2")
        || fn_body.contains(".bind(");

    assert!(
        uses_parameterized || !uses_format_interpolation,
        "build_search_query must use parameterized placeholders ($1, $2), \
         not format!() string interpolation (F2)"
    );

    // Secondary: functional check
    let sql = search::build_search_query("normal_search", "user123");
    assert!(
        sql.contains("$1") || sql.contains("$2") || sql.contains("?"),
        "Fixed search must use parameterized placeholders, got: {}",
        sql
    );
}

/
#[test]
fn test_sql_injection_query_escaped() {
    let malicious_queries = vec![
        "'; DROP TABLE files; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM users --",
        "test'; INSERT INTO files VALUES ('hack'); --",
    ];

    for query in malicious_queries {
        let sql = search::build_search_query(query, "user123");
        // After fix: raw SQL metacharacters must not appear unescaped
        assert!(
            !sql.contains("';") && !sql.contains("--") && !sql.contains("UNION"),
            "SQL injection payload '{}' was not sanitized. Generated SQL: {}",
            query, sql
        );
    }
}

/
#[test]
fn test_sql_injection_sort_column_validated() {
    // Malicious sort_by should fall back to a safe default
    let sql = search::build_sorted_query("test", "name; DROP TABLE files; --");
    assert!(
        !sql.contains("DROP TABLE"),
        "Malicious sort_by was not validated (F2). Generated SQL: {}",
        sql
    );
    // Valid sort columns should work
    let sql_valid = search::build_sorted_query("test", "name");
    assert!(
        sql_valid.contains("ORDER BY"),
        "Valid sort column should produce ORDER BY clause"
    );
}

// ===== BUG F1: Path traversal must be rejected =====

/
#[test]
fn test_path_traversal_rejected() {
    // Verify the source handles more than just literal ".."
    let utils_src = include_str!("../src/utils.rs");
    let validate_fn = utils_src.split("fn validate_path")
        .nth(1)
        .unwrap_or("");

    // After fix: must check for absolute paths and encoded traversals
    assert!(
        validate_fn.contains("starts_with('/')") || validate_fn.contains("starts_with(\"/\")")
            || validate_fn.contains("starts_with('\\\\')") || validate_fn.contains("absolute"),
        "validate_path must reject absolute paths like /etc/passwd (F1)"
    );

    let malicious_paths = vec![
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd",
        "....//....//....//etc/passwd",
    ];

    for path in malicious_paths {
        let result = utils::validate_path(path);
        assert!(
            result.is_err(),
            "Path traversal '{}' must be rejected but validate_path returned Ok (F1)",
            path
        );
    }
}

/
#[test]
fn test_path_traversal_encoded_rejected() {
    // Verify the source decodes URL-encoded characters before checking
    let utils_src = include_str!("../src/utils.rs");
    let validate_fn = utils_src.split("fn validate_path")
        .nth(1)
        .unwrap_or("");

    // After fix: must decode %2e%2e before traversal check
    assert!(
        validate_fn.contains("percent") || validate_fn.contains("decode")
            || validate_fn.contains("%2e") || validate_fn.contains("url")
            || validate_fn.contains("file://"),
        "validate_path must handle URL-encoded traversal (%2e%2e) and file:// scheme (F1)"
    );

    let encoded_paths = vec![
        "%2e%2e/%2e%2e/etc/passwd",
        "..%2f..%2f..%2fetc%2fpasswd",
        "file:///etc/passwd",
    ];

    for path in encoded_paths {
        let result = utils::validate_path(path);
        assert!(
            result.is_err(),
            "Encoded path traversal '{}' must be rejected (F1)",
            path
        );
    }
}

/
#[test]
fn test_path_within_base_dir_allowed() {
    let safe_paths = vec![
        "documents/report.pdf",
        "photos/vacation/beach.jpg",
        "notes.txt",
    ];

    for path in safe_paths {
        let result = utils::validate_path(path);
        assert!(
            result.is_ok(),
            "Safe path '{}' should be allowed but was rejected",
            path
        );
    }
}

// ===== BUG F1 (SSRF): Webhook URLs must reject internal addresses =====

/// SSRF: Internal/metadata URLs must be rejected by validate_webhook_url.
#[tokio::test]
async fn test_ssrf_prevention() {
    let dangerous_urls = vec![
        "http://localhost/admin",
        "http://127.0.0.1:8080/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/admin",
        "http://0.0.0.0/",
    ];

    for url in dangerous_urls {
        let result = utils::validate_webhook_url(url);
        assert!(
            result.is_err(),
            "Internal URL '{}' must be rejected to prevent SSRF but was allowed",
            url
        );
    }
}

// ===== BUG F4: Memory-mapped file safety =====

/
#[test]
fn test_mmap_keeps_file_handle_alive() {
    use std::fs::File;
    use std::io::Write;

    let test_path = "/tmp/vaultfs-mmap-handle-test.bin";
    let content = b"Test content for memory mapping validation";
    let mut file = File::create(test_path).unwrap();
    file.write_all(content).unwrap();
    drop(file);

    // After fix: MappedFile should keep file handle alive internally
    let mapped = unsafe { MappedFile::open(Path::new(test_path)).unwrap() };

    // Verify we can read the correct content
    let data = unsafe { mapped.as_slice() };
    assert_eq!(
        &data[..content.len()], content,
        "MappedFile must correctly read file content (F4)"
    );

    // Cleanup
    drop(mapped);
    std::fs::remove_file(test_path).unwrap();
}

/
#[test]
fn test_mmap_bounds_checked() {
    use std::fs::File;
    use std::io::Write;

    let test_path = "/tmp/vaultfs-mmap-bounds-test.bin";
    let content = b"Short";
    let mut file = File::create(test_path).unwrap();
    file.write_all(content).unwrap();
    drop(file);

    let mapped = unsafe { MappedFile::open(Path::new(test_path)).unwrap() };

    // After fix: reading beyond bounds must return an error or empty vec, not UB
    // Offset 100 + len 50 is way beyond the 5-byte file
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        unsafe { mapped.read_at(100, 50) }
    }));

    // The fix should either return an empty result or a proper error,
    // not cause undefined behavior. If it panics with a bounds message, that's also acceptable.
    // What we do NOT want is silent UB (reading garbage memory).
    assert!(
        result.is_err() || result.as_ref().map_or(false, |v| v.is_empty() || v.len() < 50),
        "read_at beyond bounds must not silently read garbage memory (F4)"
    );

    drop(mapped);
    std::fs::remove_file(test_path).unwrap();
}

/
#[test]
fn test_mmap_null_ptr_check() {
    // After fix: opening a non-existent file must return an error, not create
    // a MappedFile with a null or MAP_FAILED pointer.
    let result = unsafe { MappedFile::open(Path::new("/tmp/nonexistent-vaultfs-test-file.bin")) };
    assert!(
        result.is_err(),
        "Opening non-existent file must return Err, not a MappedFile with invalid pointer (F4)"
    );
}

// ===== JWT validation =====

#[test]
fn test_jwt_validation_expired() {
    let expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ.invalid";
    let result = auth::validate_jwt(expired_token, "secret");
    assert!(result.is_err(), "Expired token must be rejected");
}

#[test]
fn test_jwt_validation_tampered() {
    let tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiYWRtaW4iOnRydWV9.tampered";
    let result = auth::validate_jwt(tampered_token, "secret");
    assert!(result.is_err(), "Tampered token must be rejected");
}
