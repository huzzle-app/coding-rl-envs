use vectorharbor::allocator::allocate_orders;
use vectorharbor::models::DispatchOrder;
use vectorharbor::policy::next_policy;
use vectorharbor::queue::should_shed;
use vectorharbor::routing::{choose_route, Route};
use vectorharbor::security::{digest, verify_signature};
use vectorharbor::statistics::percentile;
use vectorharbor::workflow::can_transition;

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
