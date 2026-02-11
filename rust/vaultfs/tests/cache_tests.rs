//! Tests for cache service
//!
//! These tests verify that lifetime bugs are FIXED.
//! Each test asserts correct (safe) behavior after the fix is applied.
//!
//! Bug coverage:
//! - B1: get_with_fallback must return owned value, not reference to local
//! - B1: get_config_value must return owned String, not &str to dropped local

use vaultfs::services::cache::CacheService;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct TestData {
    id: String,
    value: i32,
}

#[tokio::test]
async fn test_cache_set_get() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();

    let data = TestData {
        id: "test1".to_string(),
        value: 42,
    };

    cache.set("test_key", &data, 60).await.unwrap();
    let result: Option<TestData> = cache.get("test_key").await.unwrap();

    assert!(result.is_some(), "Cached value must be retrievable");
    assert_eq!(result.unwrap(), data, "Retrieved value must match stored value");
}

#[tokio::test]
async fn test_cache_miss() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();

    let result: anyhow::Result<Option<TestData>> = cache.get("nonexistent_key").await;
    // A miss should return Ok(None) or Err, not panic
    match result {
        Ok(None) => {} // correct: key not found
        Ok(Some(_)) => panic!("Nonexistent key must not return a value"),
        Err(_) => {} // also acceptable: error on missing key
    }
}

/
/// After fix, the function signature should be:
///   async fn get_with_fallback<T, F>(...) -> anyhow::Result<T>
/// instead of:
///   async fn get_with_fallback<'a, T, F>(...) -> anyhow::Result<&'a T>
#[tokio::test]
async fn test_cache_get_with_fallback_returns_owned() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();

    // Use the fallback path: key doesn't exist, fallback is called
    let result = cache.get_with_fallback("fallback_test_key", || TestData {
        id: "generated".to_string(),
        value: 999,
    }).await;

    assert!(result.is_ok(), "get_with_fallback must succeed (B1)");
    let value = result.unwrap();
    assert_eq!(value.id, "generated", "Fallback value must be returned correctly");
    assert_eq!(value.value, 999, "Fallback value fields must match");

    // Verify it was cached: second call should return cached value
    let cached = cache.get_with_fallback("fallback_test_key", || TestData {
        id: "should_not_be_used".to_string(),
        value: 0,
    }).await.unwrap();
    assert_eq!(cached.value, 999, "Cached value must be returned on second call");
}

/
/// After fix, signature should be:
///   fn get_config_value(&self, key: &str) -> Option<String>
#[tokio::test]
async fn test_cache_config_value_returns_owned() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();

    let result = cache.get_config_value("some_key");
    // The function must not return a dangling reference.
    // If it returns Some, the String must be usable.
    if let Some(val) = result {
        assert!(
            !val.is_empty(),
            "Config value must be a valid owned string, not empty (B1)"
        );
        // Verify the value is actually usable (not dangling)
        let owned = val.to_string();
        assert!(owned.contains("config_"), "Config value must contain expected prefix");
    }
    // If None, that's also acceptable - the point is it doesn't return &str to dropped data
}

#[tokio::test]
async fn test_cache_expiration() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();

    let data = TestData {
        id: "expiring".to_string(),
        value: 1,
    };

    // Set with 1 second TTL
    cache.set("expiring_key", &data, 1).await.unwrap();

    // Should exist immediately
    let result: Option<TestData> = cache.get("expiring_key").await.unwrap();
    assert!(result.is_some(), "Key must exist immediately after set");
    assert_eq!(result.unwrap().value, 1);

    // Wait for expiration
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    // Should be gone
    let result: Option<TestData> = cache.get("expiring_key").await.unwrap();
    assert!(result.is_none(), "Key must be expired after TTL");
}

#[tokio::test]
async fn test_cache_delete() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();

    let data = TestData {
        id: "to_delete".to_string(),
        value: 999,
    };

    cache.set("delete_key", &data, 60).await.unwrap();
    cache.delete("delete_key").await.unwrap();

    let result: Option<TestData> = cache.get("delete_key").await.unwrap();
    assert!(result.is_none(), "Deleted key must not be retrievable");
}

/
#[tokio::test]
async fn test_cache_fallback_idempotent() {
    let cache = CacheService::new("redis://localhost:6379").await.unwrap();
    let key = "idempotent_test_key";

    // First call: fallback creates value
    let v1 = cache.get_with_fallback(key, || TestData {
        id: "first".to_string(),
        value: 1,
    }).await.unwrap();
    assert_eq!(v1.value, 1);

    // Second call: should return cached value, not call fallback
    let v2 = cache.get_with_fallback(key, || TestData {
        id: "second".to_string(),
        value: 2,
    }).await.unwrap();
    assert_eq!(v2.value, 1, "Second call must return cached value, not new fallback");
}
