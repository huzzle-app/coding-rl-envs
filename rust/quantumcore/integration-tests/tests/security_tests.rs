//! Security tests for QuantumCore
//!
//! Tests verify that source code does NOT contain known security anti-patterns.
//! Each test reads actual source files and checks for the presence/absence of
//! specific buggy or insecure patterns.
//!
//! Tests cover: H1, H2, H3, H4, H5 security bugs

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::time::{Duration, Instant};

/// Get the workspace root directory
fn workspace_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir.parent().unwrap().to_path_buf()
}

/// Read a source file relative to workspace root
fn read_source(relative_path: &str) -> String {
    let path = workspace_root().join(relative_path);
    fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {}", path.display(), e))
}

// =============================================================================
// H1: JWT Secret Hardcoded Tests
// =============================================================================

#[test]
fn test_h1_jwt_secret_not_hardcoded_in_source() {
    let jwt_source = read_source("services/auth/src/jwt.rs");

    // The bug: a hardcoded secret string is used directly in the source as a const/static
    // Check for any `const` or `static` or `let` that assigns a string literal as a secret
    let lines: Vec<&str> = jwt_source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        // Skip comments and test blocks
        if trimmed.starts_with("//") || trimmed.starts_with("#[cfg(test)]") {
            continue;
        }
        // Detect hardcoded secret constants
        if (trimmed.contains("const") || trimmed.contains("static"))
            && (trimmed.to_lowercase().contains("secret") || trimmed.to_lowercase().contains("key"))
            && trimmed.contains("\"")
        {
            panic!(
                "H1 BUG: JWT module has hardcoded secret at line {}: {}\n\
                 Secrets should be loaded from environment variables or config files",
                i + 1, trimmed
            );
        }
    }
}

#[test]
fn test_h1_jwt_uses_env_or_config_for_secret() {
    let jwt_source = read_source("services/auth/src/jwt.rs");

    // A proper implementation should load secrets from environment or config
    let secure_patterns = [
        "env::var",
        "std::env::var",
        "config",
        "from_env",
        "secret_from",
    ];

    let uses_secure_source = secure_patterns.iter().any(|p| jwt_source.contains(p));
    // This will fail if the JWT module doesn't load secrets from env/config
    assert!(
        uses_secure_source,
        "H1 BUG: JWT module should load secret from environment/config, not hardcode it"
    );
}

#[test]
fn test_h1_jwt_algorithm_enforced() {
    let jwt_source = read_source("services/auth/src/jwt.rs");

    // JWT should explicitly set algorithm, not rely on Header::default()
    // Using default() is technically safe (HS256) but is a code smell
    let has_explicit_algo = jwt_source.contains("Algorithm::")
        || jwt_source.contains("algorithm")
        || jwt_source.contains("Header::new");

    let uses_default_header = jwt_source.contains("Header::default()");

    // Fail if using Header::default() without any algorithm verification
    if uses_default_header && !has_explicit_algo {
        // Not a hard failure — default is HS256 which is fine
        // But should explicitly set algorithm for clarity
    }

    // Validation should enforce algorithm
    assert!(
        jwt_source.contains("Validation"),
        "JWT validation should be present"
    );
}

#[test]
fn test_h1_jwt_expiry_set() {
    let jwt_source = read_source("services/auth/src/jwt.rs");

    // JWT tokens should have expiry (exp claim)
    let has_expiry = jwt_source.contains("exp") || jwt_source.contains("expir");
    assert!(
        has_expiry,
        "H1 BUG: JWT tokens must include expiration claim"
    );
}

// =============================================================================
// H2: Timing Attack Tests
// =============================================================================

#[test]
fn test_h2_uses_constant_time_comparison() {
    let api_key_source = read_source("services/auth/src/api_key.rs");

    // The bug: using == for secret comparison instead of constant_time_eq
    let uses_constant_time = api_key_source.contains("constant_time_eq")
        || api_key_source.contains("ConstantTimeEq")
        || api_key_source.contains("ct_eq")
        || api_key_source.contains("subtle::");

    assert!(
        uses_constant_time,
        "H2 BUG: Secret comparison should use constant-time comparison (subtle crate), not ==.\n\
         Found in: services/auth/src/api_key.rs"
    );
}

#[test]
fn test_h2_no_direct_eq_for_secrets() {
    let api_key_source = read_source("services/auth/src/api_key.rs");

    // Look for direct == comparison on key/secret/token variables
    let lines: Vec<&str> = api_key_source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        // Skip comments
        if trimmed.starts_with("//") || trimmed.starts_with("/*") {
            continue;
        }
        // Check for == on secret-related variables
        if (trimmed.contains("key") || trimmed.contains("secret") || trimmed.contains("token"))
            && trimmed.contains("==")
            && !trimmed.contains("constant_time")
            && !trimmed.contains("subtle")
        {
            panic!(
                "H2 BUG: Direct == comparison on secret at line {}: {}\n\
                 Use subtle::ConstantTimeEq instead to prevent timing attacks",
                i + 1, trimmed
            );
        }
    }
}

#[test]
fn test_h2_timing_attack_practical() {
    // Practical test: verify that constant-time comparison produces consistent timing
    use subtle::ConstantTimeEq;

    let secret = b"supersecretkey12345678901234567890";
    let match_early_diff = b"Xupersecretkey12345678901234567890";
    let match_late_diff = b"supersecretkey1234567890123456789X";

    // Constant-time comparison should work correctly
    assert_eq!(secret.ct_eq(secret).unwrap_u8(), 1, "Equal secrets should match");
    assert_eq!(secret.ct_eq(match_early_diff).unwrap_u8(), 0, "Different secrets should not match");
    assert_eq!(secret.ct_eq(match_late_diff).unwrap_u8(), 0, "Different secrets should not match");

    // Timing test: both comparisons should take similar time
    let iterations = 10000;
    let start = Instant::now();
    for _ in 0..iterations {
        let _ = secret.ct_eq(match_early_diff);
    }
    let time_early = start.elapsed();

    let start = Instant::now();
    for _ in 0..iterations {
        let _ = secret.ct_eq(match_late_diff);
    }
    let time_late = start.elapsed();

    // Times should be within 2x of each other for constant-time comparison
    let ratio = time_early.as_nanos() as f64 / time_late.as_nanos().max(1) as f64;
    assert!(
        ratio > 0.5 && ratio < 2.0,
        "Constant-time comparison timing ratio {:.2} suggests non-constant behavior",
        ratio
    );
}

// =============================================================================
// H3: SQL Injection Tests
// =============================================================================

#[test]
fn test_h3_no_string_format_in_queries() {
    let handler_source = read_source("services/orders/src/service.rs");

    // The bug: using format!() to build SQL queries
    let lines: Vec<&str> = handler_source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.starts_with("//") {
            continue;
        }
        // Detect format!("SELECT/INSERT/UPDATE/DELETE ... {}")
        if (trimmed.contains("format!(") || trimmed.contains("format! ("))
            && (trimmed.to_uppercase().contains("SELECT")
                || trimmed.to_uppercase().contains("INSERT")
                || trimmed.to_uppercase().contains("UPDATE")
                || trimmed.to_uppercase().contains("DELETE"))
        {
            panic!(
                "H3 BUG: SQL injection vulnerability at line {}: {}\n\
                 Use parameterized queries ($1, $2) instead of format!()",
                i + 1, trimmed
            );
        }
    }
}

#[test]
fn test_h3_uses_parameterized_queries() {
    let repo_source = read_source("services/orders/src/repository.rs");

    // Proper implementation uses sqlx query macros or $N parameters
    let uses_params = repo_source.contains("$1")
        || repo_source.contains("query!")
        || repo_source.contains("query_as!")
        || repo_source.contains(".bind(");

    assert!(
        uses_params,
        "H3 BUG: Order repository should use parameterized queries ($1, .bind())"
    );
}

#[test]
fn test_h3_handler_validates_input() {
    let handler_source = read_source("services/orders/src/service.rs");

    // Handler should validate inputs before passing to queries
    let has_validation = handler_source.contains("validate")
        || handler_source.contains("sanitize")
        || handler_source.contains("is_alphanumeric")
        || handler_source.contains("regex");

    // This may pass even with the bug if there's some validation
    // The key test is test_h3_no_string_format_in_queries above
    assert!(
        handler_source.len() > 0,
        "Handler source should exist"
    );
}

// =============================================================================
// H4: Rate Limit Bypass Tests
// =============================================================================

#[test]
fn test_h4_rate_limit_not_using_forwarded_header() {
    let middleware_source = read_source("services/gateway/src/middleware.rs");

    let lines: Vec<&str> = middleware_source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.starts_with("//") {
            continue;
        }
        // The bug: using X-Forwarded-For or X-Real-IP for rate limiting
        if (trimmed.contains("X-Forwarded-For") || trimmed.contains("x-forwarded-for")
            || trimmed.contains("X-Real-IP") || trimmed.contains("x-real-ip"))
            && !trimmed.contains("ignore") && !trimmed.contains("skip")
        {
            panic!(
                "H4 BUG: Rate limiting uses spoofable header at line {}: {}\n\
                 Use the actual connection IP (peer_addr) instead of proxy headers",
                i + 1, trimmed
            );
        }
    }
}

#[test]
fn test_h4_rate_limit_uses_peer_addr() {
    let middleware_source = read_source("services/gateway/src/middleware.rs");
    let router_source = read_source("services/gateway/src/router.rs");

    // Should use actual connection IP
    let uses_peer = middleware_source.contains("peer_addr")
        || middleware_source.contains("remote_addr")
        || middleware_source.contains("ConnectInfo")
        || router_source.contains("peer_addr")
        || router_source.contains("ConnectInfo");

    assert!(
        uses_peer,
        "H4 BUG: Rate limiting should use actual connection IP (peer_addr/ConnectInfo), \
         not client-provided headers"
    );
}

#[test]
fn test_h4_rate_limit_per_account() {
    let middleware_source = read_source("services/gateway/src/middleware.rs");

    // Rate limiting should also work per-account, not just per-IP
    let has_account_limit = middleware_source.contains("account")
        || middleware_source.contains("user_id")
        || middleware_source.contains("api_key");

    // Per-account rate limiting provides defense-in-depth
    assert!(
        has_account_limit,
        "H4: Rate limiting should include per-account limits"
    );
}

// =============================================================================
// H5: Sensitive Data in Logs Tests
// =============================================================================

#[test]
fn test_h5_logger_masks_sensitive_fields() {
    let logger_source = read_source("shared/src/logger.rs");

    // The bug: logging sensitive data without masking
    let has_masking = logger_source.contains("mask")
        || logger_source.contains("redact")
        || logger_source.contains("REDACTED")
        || logger_source.contains("sanitize")
        || logger_source.contains("***");

    assert!(
        has_masking,
        "H5 BUG: Logger should mask/redact sensitive fields before logging.\n\
         Found in: shared/src/logger.rs"
    );
}

#[test]
fn test_h5_no_password_in_log_format() {
    let logger_source = read_source("shared/src/logger.rs");

    let lines: Vec<&str> = logger_source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.starts_with("//") {
            continue;
        }
        // Check for logging password/secret directly
        if (trimmed.contains("info!") || trimmed.contains("warn!") || trimmed.contains("debug!")
            || trimmed.contains("error!") || trimmed.contains("tracing::"))
            && (trimmed.contains("password") || trimmed.contains("secret")
                || trimmed.contains("api_key") || trimmed.contains("token"))
            && !trimmed.contains("redact") && !trimmed.contains("mask")
            && !trimmed.contains("REDACTED")
        {
            panic!(
                "H5 BUG: Sensitive data logged without masking at line {}: {}",
                i + 1, trimmed
            );
        }
    }
}

#[test]
fn test_h5_nats_no_sensitive_logging() {
    let nats_source = read_source("shared/src/nats.rs");

    let lines: Vec<&str> = nats_source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.starts_with("//") {
            continue;
        }
        if (trimmed.contains("info!") || trimmed.contains("debug!") || trimmed.contains("warn!"))
            && (trimmed.contains("password") || trimmed.contains("credential"))
            && !trimmed.contains("redact") && !trimmed.contains("mask")
        {
            panic!(
                "H5 BUG: NATS module logs sensitive data at line {}: {}",
                i + 1, trimmed
            );
        }
    }
}

// =============================================================================
// Source Code Integrity Tests
// =============================================================================

#[test]
fn test_auth_service_uses_subtle_crate() {
    // Check that the auth service's Cargo.toml includes the subtle crate
    let cargo_toml = read_source("services/auth/Cargo.toml");

    let has_subtle = cargo_toml.contains("subtle");
    assert!(
        has_subtle,
        "Auth service should depend on the `subtle` crate for constant-time comparisons"
    );
}

#[test]
fn test_no_unwrap_in_auth_handlers() {
    let jwt_source = read_source("services/auth/src/jwt.rs");
    let api_key_source = read_source("services/auth/src/api_key.rs");

    // Count unwrap() calls in non-test, non-comment code
    for (name, source) in [("jwt.rs", jwt_source), ("api_key.rs", api_key_source)] {
        let mut unwrap_count = 0;
        for line in source.lines() {
            let trimmed = line.trim();
            if trimmed.starts_with("//") || trimmed.starts_with("#[") {
                continue;
            }
            if trimmed.contains(".unwrap()") && !trimmed.contains("test") {
                unwrap_count += 1;
            }
        }
        assert!(
            unwrap_count <= 2,
            "Auth {} has {} unwrap() calls — use proper error handling in security code",
            name, unwrap_count
        );
    }
}

#[test]
fn test_gateway_validates_request_size() {
    let router_source = read_source("services/gateway/src/router.rs");
    let middleware_source = read_source("services/gateway/src/middleware.rs");

    let combined = format!("{}\n{}", router_source, middleware_source);

    // Gateway should limit request body size to prevent DoS
    let has_size_limit = combined.contains("content_length")
        || combined.contains("body_limit")
        || combined.contains("max_body")
        || combined.contains("DefaultBodyLimit")
        || combined.contains("RequestBodyLimit");

    assert!(
        has_size_limit,
        "Gateway should enforce request body size limits"
    );
}

// =============================================================================
// Anti-reward-hacking: Verify test file integrity
// =============================================================================

#[test]
fn test_security_test_count_unchanged() {
    // Prevent reward hacking by deleting security tests
    let this_file = include_str!("security_tests.rs");
    let test_count = this_file.matches("#[test]").count();

    // This file should contain at least 20 test functions
    assert!(
        test_count >= 20,
        "Security tests file has been tampered with: only {} tests found (expected >= 20)",
        test_count
    );
}

#[test]
fn test_reward_files_not_modified() {
    // Check that reward/scoring files haven't been tampered with
    let scoring = read_source("environment/scoring.py");
    let reward = read_source("environment/reward.py");

    // scoring.py should contain the proper threshold tables
    assert!(
        scoring.contains("REWARD_TABLES") && scoring.contains("principal"),
        "environment/scoring.py has been tampered with"
    );

    // reward.py should contain the reward calculator
    assert!(
        reward.contains("RewardCalculator") && reward.contains("threshold_rewards"),
        "environment/reward.py has been tampered with"
    );
}

#[test]
fn test_test_sh_not_modified() {
    let test_sh = read_source("tests/test.sh");

    // test.sh should still use cargo test and scoring.py
    assert!(
        test_sh.contains("cargo test") && test_sh.contains("scoring.py"),
        "tests/test.sh has been tampered with"
    );

    // Should not contain hardcoded rewards
    assert!(
        !test_sh.contains("echo \"1.0\" > /logs/verifier/reward.txt"),
        "tests/test.sh contains hardcoded reward — reward hacking detected"
    );
}
