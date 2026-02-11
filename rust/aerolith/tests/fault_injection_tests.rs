use aerolith::resilience::{accept_version, circuit_open, dedupe_ids, retry_backoff_ms};

#[test]
fn retry_backoff_grows() {
    assert!(retry_backoff_ms(1, 50) < retry_backoff_ms(2, 50));
    assert!(retry_backoff_ms(2, 50) < retry_backoff_ms(3, 50));
}

#[test]
fn circuit_breaker_trips() {
    assert!(!circuit_open(4));
    assert!(circuit_open(5));
}

#[test]
fn stale_version_rejected() {
    assert!(!accept_version(9, 10));
    assert!(accept_version(10, 10));
}

#[test]
fn idempotency_dedupes() {
    let n = dedupe_ids(&["a", "b", "a", "c", "b"]);
    assert_eq!(n, 3);
}
