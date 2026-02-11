use tensorforge::allocator::allocate_orders;
use tensorforge::models::DispatchOrder;
use tensorforge::policy::next_policy;
use tensorforge::queue::should_shed;
use tensorforge::routing::{choose_route, Route};
use tensorforge::security::{digest, verify_signature};
use tensorforge::statistics::percentile;
use tensorforge::workflow::can_transition;

use tensorforge::config::{default_region, default_pool_size, validate_endpoint, normalize_env_name, ServiceConfig};
use tensorforge::concurrency::{barrier_reached, merge_counts, AtomicCounter};
use tensorforge::events::{sort_events_by_time, TimedEvent};
use tensorforge::telemetry::{error_rate, health_score, should_alert};

#[test]
fn allocator_enforces_capacity() {
    let out = allocate_orders(
        vec![
            ("a".to_string(), 1, 50),
            ("b".to_string(), 4, 70),
            ("c".to_string(), 4, 30),
        ],
        2,
    );
    assert_eq!(out.iter().map(|v| v.0.as_str()).collect::<Vec<_>>(), vec!["c", "b"]);
}

#[test]
fn routing_ignores_blocked_channels() {
    let route = choose_route(
        &[
            Route { channel: "alpha".to_string(), latency: 8 },
            Route { channel: "beta".to_string(), latency: 3 },
        ],
        &["beta".to_string()],
    )
    .unwrap();
    assert_eq!(route.channel, "alpha");
}

#[test]
fn policy_escalates_on_failure_burst() {
    assert_eq!(next_policy("watch", 3), "restricted");
}

#[test]
fn security_scope_and_signature() {
    let payload = "manifest:v1";
    let sig = digest(payload);
    assert!(verify_signature(payload, &sig, &sig));
    assert!(!verify_signature(payload, &sig[..sig.len() - 1], &sig));
}

#[test]
fn queue_shed_on_hard_limit() {
    assert!(!should_shed(9, 10, false));
    assert!(should_shed(11, 10, false));
    assert!(should_shed(8, 10, true));
}

#[test]
fn statistics_percentile_monotonic() {
    assert_eq!(percentile(&[4, 1, 9, 7], 50), 4);
    assert_eq!(percentile(&[], 90), 0);
}

#[test]
fn workflow_transition_graph() {
    assert!(can_transition("queued", "allocated"));
    assert!(!can_transition("queued", "arrived"));
}

#[test]
fn model_urgency_score() {
    let order = DispatchOrder { id: "d1".to_string(), severity: 3, sla_minutes: 30 };
    assert_eq!(order.urgency_score(), 120);
}

// ---- New module tests ----

#[test]
fn config_defaults() {
    assert_eq!(default_region(), "us-east-1");
    assert_eq!(default_pool_size(), 32);
    let cfg = ServiceConfig::new("test-svc");
    assert_eq!(cfg.region, "us-east-1");
    assert_eq!(cfg.pool_size, 32);
}

#[test]
fn config_endpoint_validation() {
    assert!(validate_endpoint("http://localhost:8080/health"));
    assert!(validate_endpoint("https://api.example.com"));
    assert!(!validate_endpoint("ftp://files.example.com"));
    assert!(!validate_endpoint("data:text/html,http://hack"));
    assert!(!validate_endpoint(""));
}

#[test]
fn config_env_normalization() {
    assert_eq!(normalize_env_name("Production"), "production");
    assert_eq!(normalize_env_name("STAGING"), "staging");
}

#[test]
fn concurrency_barrier() {
    assert!(barrier_reached(5, 5));
    assert!(!barrier_reached(4, 5));
    assert!(barrier_reached(6, 5));
}

#[test]
fn concurrency_merge_counts() {
    let mut a = std::collections::HashMap::new();
    a.insert("x".to_string(), 5);
    a.insert("y".to_string(), 3);
    let mut b = std::collections::HashMap::new();
    b.insert("x".to_string(), 2);
    b.insert("z".to_string(), 4);
    let merged = merge_counts(&a, &b);
    assert_eq!(*merged.get("x").unwrap(), 7);  // 5 + 2
    assert_eq!(*merged.get("y").unwrap(), 3);
    assert_eq!(*merged.get("z").unwrap(), 4);
}

#[test]
fn concurrency_atomic_counter() {
    let counter = AtomicCounter::new(0);
    assert_eq!(counter.increment(), 1);
    assert_eq!(counter.increment(), 2);
    assert_eq!(counter.decrement(), 1);
    assert_eq!(counter.get(), 1);
}

#[test]
fn events_time_sorting() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 300, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 100, kind: "B".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 200, kind: "A".into(), payload: "".into() },
    ];
    let sorted = sort_events_by_time(&events);
    assert_eq!(sorted[0].id, "e2");
    assert_eq!(sorted[1].id, "e3");
    assert_eq!(sorted[2].id, "e1");
}

#[test]
fn telemetry_error_rate() {
    let rate = error_rate(100, 5);
    assert!((rate - 0.05).abs() < 0.001);
    assert_eq!(error_rate(100, 0), 0.0);
}

#[test]
fn telemetry_health_score() {
    // availability=1.0, performance=0.5: score = 1.0*0.6 + 0.5*0.4 = 0.8
    let score = health_score(1.0, 0.5);
    assert!((score - 0.8).abs() < 0.001);
}

#[test]
fn telemetry_alerting() {
    assert!(should_alert(95.0, 90.0));  // value > threshold => alert
    assert!(!should_alert(80.0, 90.0));  // value < threshold => no alert
}
