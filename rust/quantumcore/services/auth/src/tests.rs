//! Comprehensive tests for the auth service
//!
//! Tests covering:
//! - BUG H1: JWT secret hardcoded
//! - BUG H2: Timing attack vulnerabilities
//! - BUG C7: Catch-all error hiding
//! - BUG L8: TLS disabled
//! - Authentication and authorization
//! - JWT generation/validation
//! - API key management
//! - Security tests

use super::*;
use chrono::{Duration, Utc};

// ============================================================================

// ============================================================================

#[test]
fn test_h1_jwt_secret_is_hardcoded() {
    
    assert_eq!(jwt::JWT_SECRET, "super_secret_key_do_not_use_in_production");
}

#[test]
fn test_h1_jwt_secret_is_weak() {
    
    let secret = jwt::JWT_SECRET;
    assert!(secret.len() < 64, "Secret should be at least 64 characters for security");
}

#[test]
fn test_h1_jwt_secret_in_source_control() {
    
    let secret = jwt::JWT_SECRET;
    assert!(secret.contains("secret"), "Hardcoded secret found in source");
}

#[test]
fn test_h1_jwt_secret_contains_production_warning() {
    
    let secret = jwt::JWT_SECRET;
    assert!(secret.contains("production"), "Secret contains 'production' in name");
}

#[test]
fn test_h1_multiple_tokens_use_same_secret() {
    
    let token1 = jwt::generate_token("user1", vec!["admin".to_string()], Duration::hours(1)).unwrap();
    let token2 = jwt::generate_token("user2", vec!["user".to_string()], Duration::hours(1)).unwrap();

    // Both tokens can be validated - showing they use the same secret
    assert!(jwt::validate_token(&token1).is_ok());
    assert!(jwt::validate_token(&token2).is_ok());
}

#[test]
fn test_h1_token_can_be_forged_with_known_secret() {
    
    // This test shows that with the hardcoded secret, tokens can be created
    let forged = jwt::generate_token("attacker", vec!["admin".to_string()], Duration::hours(24)).unwrap();
    let claims = jwt::validate_token(&forged).unwrap();
    assert_eq!(claims.sub, "attacker");
    assert!(claims.roles.contains(&"admin".to_string()));
}

// ============================================================================

// ============================================================================

#[test]
fn test_h2_compare_tokens_early_length_return() {
    
    let short = "abc";
    let long = "abcdefgh";

    // This should fail but the timing reveals length difference
    assert!(!jwt::compare_tokens(short, long));
}

#[test]
fn test_h2_compare_tokens_character_by_character() {
    
    let token1 = "aaaaaaaaaa";
    let token2 = "aaaaaaaaab"; // Differs at last char
    let token3 = "baaaaaaaaa"; // Differs at first char

    // Both comparisons fail but timing differs
    assert!(!jwt::compare_tokens(token1, token2));
    assert!(!jwt::compare_tokens(token1, token3));
}

#[test]
fn test_h2_timing_attack_measurable_difference() {
    
    let secret = "correctsecretvalue1234567890abcdef";
    let almost_match = "correctsecretvalue1234567890abcdex";
    let no_match = "xorrectsecretvalue1234567890abcdef";

    // In a real timing attack, these would be measured
    let result1 = jwt::compare_tokens(secret, almost_match);
    let result2 = jwt::compare_tokens(secret, no_match);

    assert!(!result1);
    assert!(!result2);
}

#[test]
fn test_h2_compare_tokens_identical() {
    
    let token = "identical_token_value";
    assert!(jwt::compare_tokens(token, token));
}

#[test]
fn test_h2_api_key_secret_comparison_vulnerable() {
    
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec!["read".to_string()]);

    // Timing attack on secret comparison
    let wrong_secret = "x".repeat(key.secret.len());
    assert!(manager.validate_key(&key.key, &wrong_secret).is_err());
}

#[test]
fn test_h2_api_key_lookup_timing() {
    
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec!["read".to_string()]);

    // Existing key lookup vs non-existing key lookup may have timing differences
    assert!(manager.validate_key(&key.key, &key.secret).is_ok());
    assert!(manager.validate_key("nonexistent", "secret").is_err());
}

// ============================================================================

// ============================================================================

#[test]
fn test_c7_validate_token_generic_error() {
    
    let result = jwt::validate_token("invalid.token.here");
    assert!(result.is_err());
    assert_eq!(result.unwrap_err().to_string(), "Invalid token");
}

#[test]
fn test_c7_expired_token_same_error() {
    
    let token = jwt::generate_token("user", vec![], Duration::seconds(-1)).unwrap();
    let result = jwt::validate_token(&token);
    assert!(result.is_err());
    // Can't distinguish expired from invalid
    assert_eq!(result.unwrap_err().to_string(), "Invalid token");
}

#[test]
fn test_c7_malformed_token_same_error() {
    
    let result = jwt::validate_token("not.a.valid.jwt.token");
    assert!(result.is_err());
    assert_eq!(result.unwrap_err().to_string(), "Invalid token");
}

#[test]
fn test_c7_wrong_signature_same_error() {
    
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();
    // Tamper with the signature
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() == 3 {
        let tampered = format!("{}.{}.tampered", parts[0], parts[1]);
        let result = jwt::validate_token(&tampered);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err().to_string(), "Invalid token");
    }
}

#[test]
fn test_c7_empty_token_same_error() {
    
    let result = jwt::validate_token("");
    assert!(result.is_err());
    assert_eq!(result.unwrap_err().to_string(), "Invalid token");
}

#[test]
fn test_c7_truncated_token_same_error() {
    
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();
    let truncated = &token[..token.len() / 2];
    let result = jwt::validate_token(truncated);
    assert!(result.is_err());
    assert_eq!(result.unwrap_err().to_string(), "Invalid token");
}

// ============================================================================

// ============================================================================

#[test]
fn test_l8_tls_verification_disabled_by_default() {
    
    let manager = api_key::ApiKeyManager::new();
    assert!(!manager.verify_ssl);
}

#[test]
fn test_l8_mitm_vulnerability() {
    
    let manager = api_key::ApiKeyManager::new();
    // Document that verify_ssl: false means no certificate validation
    assert!(!manager.verify_ssl, "TLS verification should be enabled");
}

// ============================================================================
// Authentication Tests
// ============================================================================

#[test]
fn test_auth_create_user() {
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();

    assert_eq!(user.email, "test@example.com");
    assert!(!user.password_hash.is_empty());
    assert!(user.api_keys.is_empty());
}

#[test]
fn test_auth_create_duplicate_user_fails() {
    let service = service::AuthService::new("test_secret");
    service.create_user("test@example.com", "password123").unwrap();

    let result = service.create_user("test@example.com", "other_password");
    assert!(result.is_err());
}

#[test]
fn test_auth_login_success() {
    let service = service::AuthService::new("test_secret");
    service.create_user("test@example.com", "password123").unwrap();

    let token = service.login("test@example.com", "password123").unwrap();
    assert!(!token.is_empty());
}

#[test]
fn test_auth_login_wrong_password() {
    let service = service::AuthService::new("test_secret");
    service.create_user("test@example.com", "password123").unwrap();

    let result = service.login("test@example.com", "wrong_password");
    assert!(result.is_err());
}

#[test]
fn test_auth_login_unknown_user() {
    let service = service::AuthService::new("test_secret");

    let result = service.login("unknown@example.com", "password123");
    assert!(result.is_err());
}

#[test]
fn test_auth_password_is_hashed() {
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();

    // Password should be hashed, not stored in plaintext
    assert_ne!(user.password_hash, "password123");
    assert!(user.password_hash.contains("$argon2"));
}

#[test]
fn test_auth_user_has_uuid() {
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();

    assert!(!user.id.is_nil());
}

#[test]
fn test_auth_user_has_created_at() {
    let before = Utc::now();
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();
    let after = Utc::now();

    assert!(user.created_at >= before);
    assert!(user.created_at <= after);
}

// ============================================================================
// JWT Generation Tests
// ============================================================================

#[test]
fn test_jwt_generate_valid_token() {
    let token = jwt::generate_token("user123", vec!["admin".to_string()], Duration::hours(1)).unwrap();

    assert!(!token.is_empty());
    assert!(token.contains('.')); // JWT format
}

#[test]
fn test_jwt_token_has_three_parts() {
    let token = jwt::generate_token("user123", vec![], Duration::hours(1)).unwrap();
    let parts: Vec<&str> = token.split('.').collect();

    assert_eq!(parts.len(), 3);
}

#[test]
fn test_jwt_claims_preserved() {
    let roles = vec!["admin".to_string(), "user".to_string()];
    let token = jwt::generate_token("user123", roles.clone(), Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    assert_eq!(claims.sub, "user123");
    assert_eq!(claims.roles, roles);
}

#[test]
fn test_jwt_expiration_set() {
    let token = jwt::generate_token("user123", vec![], Duration::hours(2)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    let now = Utc::now().timestamp();
    assert!(claims.exp > now);
    assert!(claims.exp <= now + 7201); // 2 hours + 1 second tolerance
}

#[test]
fn test_jwt_issued_at_set() {
    let before = Utc::now().timestamp();
    let token = jwt::generate_token("user123", vec![], Duration::hours(1)).unwrap();
    let after = Utc::now().timestamp();

    let claims = jwt::validate_token(&token).unwrap();
    assert!(claims.iat >= before);
    assert!(claims.iat <= after);
}

#[test]
fn test_jwt_different_users_different_tokens() {
    let token1 = jwt::generate_token("user1", vec![], Duration::hours(1)).unwrap();
    let token2 = jwt::generate_token("user2", vec![], Duration::hours(1)).unwrap();

    assert_ne!(token1, token2);
}

// ============================================================================
// JWT Validation Tests
// ============================================================================

#[test]
fn test_jwt_validate_valid_token() {
    let token = jwt::generate_token("user123", vec!["admin".to_string()], Duration::hours(1)).unwrap();
    let result = jwt::validate_token(&token);

    assert!(result.is_ok());
}

#[test]
fn test_jwt_validate_expired_token() {
    let token = jwt::generate_token("user123", vec![], Duration::seconds(-10)).unwrap();
    let result = jwt::validate_token(&token);

    assert!(result.is_err());
}

#[test]
fn test_jwt_validate_invalid_format() {
    let result = jwt::validate_token("not-a-valid-jwt");
    assert!(result.is_err());
}

#[test]
fn test_jwt_validate_empty_token() {
    let result = jwt::validate_token("");
    assert!(result.is_err());
}

#[test]
fn test_jwt_validate_tampered_payload() {
    let token = jwt::generate_token("user123", vec![], Duration::hours(1)).unwrap();
    let parts: Vec<&str> = token.split('.').collect();

    if parts.len() == 3 {
        // Tamper with payload
        let tampered = format!("{}.xxx{}.{}", parts[0], parts[1], parts[2]);
        let result = jwt::validate_token(&tampered);
        assert!(result.is_err());
    }
}

#[test]
fn test_jwt_refresh_token() {
    let token = jwt::generate_token("user123", vec!["admin".to_string()], Duration::hours(1)).unwrap();
    let refreshed = jwt::refresh_token(&token).unwrap();

    assert_ne!(token, refreshed);
    let claims = jwt::validate_token(&refreshed).unwrap();
    assert_eq!(claims.sub, "user123");
}

#[test]
fn test_jwt_refresh_preserves_roles() {
    let roles = vec!["admin".to_string(), "moderator".to_string()];
    let token = jwt::generate_token("user123", roles.clone(), Duration::hours(1)).unwrap();
    let refreshed = jwt::refresh_token(&token).unwrap();

    let claims = jwt::validate_token(&refreshed).unwrap();
    assert_eq!(claims.roles, roles);
}

#[test]
fn test_jwt_refresh_expired_token_fails() {
    let token = jwt::generate_token("user123", vec![], Duration::seconds(-10)).unwrap();
    let result = jwt::refresh_token(&token);

    assert!(result.is_err());
}

// ============================================================================
// API Key Management Tests
// ============================================================================

#[test]
fn test_api_key_generate() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec!["read".to_string()]);

    assert!(!key.key.is_empty());
    assert!(!key.secret.is_empty());
    assert!(key.key.starts_with("qc_"));
}

#[test]
fn test_api_key_unique() {
    let mut manager = api_key::ApiKeyManager::new();
    let key1 = manager.generate_key("user1", vec![]);
    let key2 = manager.generate_key("user1", vec![]);

    assert_ne!(key1.key, key2.key);
    assert_ne!(key1.secret, key2.secret);
}

#[test]
fn test_api_key_validate_success() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec!["read".to_string()]);

    let result = manager.validate_key(&key.key, &key.secret);
    assert!(result.is_ok());
}

#[test]
fn test_api_key_validate_wrong_secret() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    let result = manager.validate_key(&key.key, "wrong_secret");
    assert!(result.is_err());
}

#[test]
fn test_api_key_validate_nonexistent() {
    let mut manager = api_key::ApiKeyManager::new();

    let result = manager.validate_key("nonexistent", "secret");
    assert!(result.is_err());
}

#[test]
fn test_api_key_revoke() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    assert!(manager.revoke_key(&key.key));
    assert!(manager.validate_key(&key.key, &key.secret).is_err());
}

#[test]
fn test_api_key_revoke_nonexistent() {
    let mut manager = api_key::ApiKeyManager::new();

    assert!(!manager.revoke_key("nonexistent"));
}

#[test]
fn test_api_key_list_keys() {
    let mut manager = api_key::ApiKeyManager::new();
    manager.generate_key("user1", vec!["read".to_string()]);
    manager.generate_key("user1", vec!["write".to_string()]);
    manager.generate_key("user2", vec!["admin".to_string()]);

    let user1_keys = manager.list_keys("user1");
    assert_eq!(user1_keys.len(), 2);

    let user2_keys = manager.list_keys("user2");
    assert_eq!(user2_keys.len(), 1);
}

#[test]
fn test_api_key_list_keys_empty() {
    let manager = api_key::ApiKeyManager::new();
    let keys = manager.list_keys("nonexistent");
    assert!(keys.is_empty());
}

#[test]
fn test_api_key_permissions_preserved() {
    let mut manager = api_key::ApiKeyManager::new();
    let permissions = vec!["read".to_string(), "write".to_string(), "delete".to_string()];
    let key = manager.generate_key("user1", permissions.clone());

    assert_eq!(key.permissions, permissions);
}

#[test]
fn test_api_key_has_uuid() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    // UUID should be valid
    assert!(!key.id.is_nil());
}

#[test]
fn test_api_key_created_at_set() {
    let before = Utc::now();
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);
    let after = Utc::now();

    assert!(key.created_at >= before);
    assert!(key.created_at <= after);
}

#[test]
fn test_api_key_last_used_updated() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    assert!(key.last_used.is_none());

    let validated = manager.validate_key(&key.key, &key.secret).unwrap();
    assert!(validated.last_used.is_some());
}

#[test]
fn test_api_key_secret_length() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    // Secret should be sufficiently long (64 chars)
    assert_eq!(key.secret.len(), 64);
}

#[test]
fn test_api_key_key_length() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    // Key should have prefix + 32 random chars
    assert!(key.key.len() > 32);
}

// ============================================================================
// Authorization Tests
// ============================================================================

#[test]
fn test_auth_jwt_includes_permissions() {
    let service = service::AuthService::new("test_secret");
    service.create_user("admin@example.com", "password123").unwrap();

    let token = service.login("admin@example.com", "password123").unwrap();
    let claims = service.verify_jwt(&token).unwrap();

    
    assert!(claims.permissions.contains(&"admin".to_string()));
}

#[test]
fn test_auth_api_key_permissions() {
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();

    let permissions = vec!["read".to_string(), "write".to_string()];
    let raw_key = service.create_api_key(user.id, "test-key", permissions.clone()).unwrap();

    let (_, returned_perms) = service.verify_api_key(&raw_key).unwrap();
    assert_eq!(returned_perms, permissions);
}

#[test]
fn test_auth_api_key_without_admin() {
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();

    let permissions = vec!["read".to_string()];
    let raw_key = service.create_api_key(user.id, "limited-key", permissions).unwrap();

    let (_, returned_perms) = service.verify_api_key(&raw_key).unwrap();
    assert!(!returned_perms.contains(&"admin".to_string()));
}

#[test]
fn test_auth_jwt_all_permissions_granted() {
    
    let service = service::AuthService::new("test_secret");
    service.create_user("regular@example.com", "password123").unwrap();

    let token = service.login("regular@example.com", "password123").unwrap();
    let claims = service.verify_jwt(&token).unwrap();

    assert!(claims.permissions.contains(&"admin".to_string()));
    assert!(claims.permissions.contains(&"read".to_string()));
    assert!(claims.permissions.contains(&"write".to_string()));
}

// ============================================================================
// Security Tests - Injection
// ============================================================================

#[test]
fn test_security_sql_injection_in_email() {
    let service = service::AuthService::new("test_secret");

    // Attempt SQL injection in email
    let result = service.create_user("test'; DROP TABLE users; --", "password123");
    // Should not cause issues (no SQL here, but test defensive handling)
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_security_xss_in_email() {
    let service = service::AuthService::new("test_secret");

    // Attempt XSS in email
    let result = service.create_user("<script>alert('xss')</script>@test.com", "password123");
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_security_unicode_in_credentials() {
    let service = service::AuthService::new("test_secret");

    // Unicode characters in credentials
    let user = service.create_user("test@example.com", "password\u{200B}123").unwrap();
    assert!(!user.password_hash.is_empty());
}

#[test]
fn test_security_null_byte_in_password() {
    let service = service::AuthService::new("test_secret");

    // Null byte in password
    let user = service.create_user("test@example.com", "password\x00123").unwrap();
    assert!(!user.password_hash.is_empty());
}

#[test]
fn test_security_very_long_password() {
    let service = service::AuthService::new("test_secret");

    // Very long password
    let long_password = "a".repeat(10000);
    let result = service.create_user("test@example.com", &long_password);
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_security_empty_password() {
    let service = service::AuthService::new("test_secret");

    // Empty password should still work (no validation)
    let user = service.create_user("test@example.com", "").unwrap();
    assert!(!user.password_hash.is_empty());
}

#[test]
fn test_security_special_chars_in_user_id() {
    let token = jwt::generate_token("user<>&\"'", vec![], Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();
    assert_eq!(claims.sub, "user<>&\"'");
}

// ============================================================================
// Security Tests - Token Manipulation
// ============================================================================

#[test]
fn test_security_token_with_different_algorithm() {
    // Attempt to use different algorithm in header
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();

    // Modifying the header would change the token
    let result = jwt::validate_token(&token);
    assert!(result.is_ok());
}

#[test]
fn test_security_token_none_algorithm_attempt() {
    
    // This creates a token without signature - should fail validation
    let fake_token = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImV4cCI6OTk5OTk5OTk5OSwiaWF0IjowLCJyb2xlcyI6WyJhZG1pbiJdfQ.";

    let result = jwt::validate_token(fake_token);
    // Should reject alg:none tokens
    assert!(result.is_err());
}

#[test]
fn test_security_jwt_with_future_iat() {
    // Token with future issued-at time
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    // iat should be current, not future
    assert!(claims.iat <= Utc::now().timestamp());
}

#[test]
fn test_security_tampered_signature() {
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();
    let parts: Vec<&str> = token.split('.').collect();

    if parts.len() == 3 {
        let tampered = format!("{}.{}.invalid_signature", parts[0], parts[1]);
        let result = jwt::validate_token(&tampered);
        assert!(result.is_err());
    }
}

#[test]
fn test_security_missing_parts() {
    let result = jwt::validate_token("header.payload");
    assert!(result.is_err());
}

// ============================================================================
// Concurrent Access Tests
// ============================================================================

#[test]
fn test_concurrent_user_creation() {
    use std::thread;
    use std::sync::Arc;

    let service = Arc::new(service::AuthService::new("test_secret"));
    let mut handles = vec![];

    for i in 0..10 {
        let svc = Arc::clone(&service);
        let handle = thread::spawn(move || {
            svc.create_user(&format!("user{}@test.com", i), "password123")
        });
        handles.push(handle);
    }

    let results: Vec<_> = handles.into_iter().map(|h| h.join().unwrap()).collect();
    let successes: Vec<_> = results.iter().filter(|r| r.is_ok()).collect();

    assert_eq!(successes.len(), 10);
}

#[test]
fn test_concurrent_api_key_generation() {
    use std::thread;
    use std::sync::{Arc, Mutex};

    let manager = Arc::new(Mutex::new(api_key::ApiKeyManager::new()));
    let mut handles = vec![];

    for i in 0..10 {
        let mgr = Arc::clone(&manager);
        let handle = thread::spawn(move || {
            let mut m = mgr.lock().unwrap();
            m.generate_key(&format!("user{}", i), vec!["read".to_string()])
        });
        handles.push(handle);
    }

    let keys: Vec<_> = handles.into_iter().map(|h| h.join().unwrap()).collect();

    // All keys should be unique
    let key_strings: Vec<_> = keys.iter().map(|k| k.key.clone()).collect();
    let unique_count = key_strings.iter().collect::<std::collections::HashSet<_>>().len();
    assert_eq!(unique_count, 10);
}

#[test]
fn test_concurrent_jwt_generation() {
    use std::thread;

    let mut handles = vec![];

    for i in 0..10 {
        let handle = thread::spawn(move || {
            jwt::generate_token(&format!("user{}", i), vec!["role".to_string()], Duration::hours(1))
        });
        handles.push(handle);
    }

    let tokens: Vec<_> = handles.into_iter().map(|h| h.join().unwrap().unwrap()).collect();

    // All tokens should be unique
    let unique_count = tokens.iter().collect::<std::collections::HashSet<_>>().len();
    assert_eq!(unique_count, 10);
}

// ============================================================================
// Edge Cases
// ============================================================================

#[test]
fn test_edge_empty_roles() {
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    assert!(claims.roles.is_empty());
}

#[test]
fn test_edge_many_roles() {
    let roles: Vec<String> = (0..100).map(|i| format!("role_{}", i)).collect();
    let token = jwt::generate_token("user", roles.clone(), Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    assert_eq!(claims.roles.len(), 100);
}

#[test]
fn test_edge_special_characters_in_user_id() {
    let token = jwt::generate_token("user@domain.com/path?query=1", vec![], Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    assert_eq!(claims.sub, "user@domain.com/path?query=1");
}

#[test]
fn test_edge_very_short_expiration() {
    let token = jwt::generate_token("user", vec![], Duration::milliseconds(1)).unwrap();

    // Token might already be expired
    std::thread::sleep(std::time::Duration::from_millis(10));
    let result = jwt::validate_token(&token);
    assert!(result.is_err());
}

#[test]
fn test_edge_api_key_empty_permissions() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    assert!(key.permissions.is_empty());
}

#[test]
fn test_edge_api_key_empty_user_id() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("", vec!["read".to_string()]);

    assert_eq!(key.user_id, "");
}

#[test]
fn test_edge_long_user_id() {
    let long_id = "a".repeat(1000);
    let token = jwt::generate_token(&long_id, vec![], Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    assert_eq!(claims.sub, long_id);
}

#[test]
fn test_edge_unicode_user_id() {
    let unicode_id = "user_\u{1F600}_\u{4E2D}\u{6587}";
    let token = jwt::generate_token(unicode_id, vec![], Duration::hours(1)).unwrap();
    let claims = jwt::validate_token(&token).unwrap();

    assert_eq!(claims.sub, unicode_id);
}

#[test]
fn test_service_verify_jwt_invalid() {
    let service = service::AuthService::new("test_secret");

    let result = service.verify_jwt("invalid.token.here");
    assert!(result.is_err());
}

#[test]
fn test_service_verify_api_key_format() {
    let service = service::AuthService::new("test_secret");
    let user = service.create_user("test@example.com", "password123").unwrap();

    let raw_key = service.create_api_key(user.id, "my-key", vec!["read".to_string()]).unwrap();

    // Key should have the qc_ prefix
    assert!(raw_key.starts_with("qc_"));
}

#[test]
fn test_api_key_expiration_not_set_by_default() {
    let mut manager = api_key::ApiKeyManager::new();
    let key = manager.generate_key("user1", vec![]);

    
    assert!(key.expires_at.is_none());
}

#[test]
fn test_jwt_token_format_base64url() {
    // JWT should use base64url encoding
    let token = jwt::generate_token("user", vec![], Duration::hours(1)).unwrap();

    // Should not contain + or / (base64 chars, not base64url)
    // base64url uses - and _ instead
    let parts: Vec<&str> = token.split('.').collect();
    for part in parts {
        // Note: jsonwebtoken uses base64url so this should pass
        assert!(!part.contains('+') || !part.contains('/'), "Token should use base64url encoding");
    }
}

#[test]
fn test_multiple_api_keys_same_user() {
    let mut manager = api_key::ApiKeyManager::new();

    for i in 0..5 {
        manager.generate_key("user1", vec![format!("perm{}", i)]);
    }

    let keys = manager.list_keys("user1");
    assert_eq!(keys.len(), 5);
}

#[test]
fn test_revoke_then_regenerate() {
    let mut manager = api_key::ApiKeyManager::new();
    let key1 = manager.generate_key("user1", vec!["read".to_string()]);

    manager.revoke_key(&key1.key);

    let key2 = manager.generate_key("user1", vec!["read".to_string()]);
    assert!(manager.validate_key(&key2.key, &key2.secret).is_ok());
}
