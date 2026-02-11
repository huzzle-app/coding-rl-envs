use tensorforge::resilience::{replay, replay_converges, Event, retry_delay, retry_delay_with_jitter,
    should_trip, recovery_rate, cascade_failure_check, fallback_priority};
use tensorforge::events::{sort_events_by_time, dedup_by_id, merge_event_streams, TimedEvent};

#[test]
fn replay_latest_sequence_wins() {
    let events = replay(&[
        Event { id: "k".to_string(), sequence: 1 },
        Event { id: "k".to_string(), sequence: 2 },
    ]);
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].sequence, 2);
}

#[test]
fn replay_ordered_and_shuffled_converge() {
    let ordered = replay(&[
        Event { id: "x".to_string(), sequence: 1 },
        Event { id: "x".to_string(), sequence: 2 },
    ]);
    let shuffled = replay(&[
        Event { id: "x".to_string(), sequence: 2 },
        Event { id: "x".to_string(), sequence: 1 },
    ]);
    assert_eq!(ordered, shuffled);
}

#[test]
fn retry_backoff_exponential() {
    let d0 = retry_delay(100, 0);
    let d1 = retry_delay(100, 1);
    let d2 = retry_delay(100, 2);
    assert_eq!(d0, 100);  // 100 * 2^0 = 100
    assert_eq!(d1, 200);  // 100 * 2^1 = 200
    assert_eq!(d2, 400);  // 100 * 2^2 = 400
}

#[test]
fn retry_jitter_adds_delay() {
    let base = retry_delay_with_jitter(100, 2, 0.5);
    // 100 * 2^2 = 400, jitter = 400 * 0.5 = 200, total should be 600
    assert!(base > 400);
}

#[test]
fn circuit_breaker_trip_threshold() {
    assert!(should_trip(8, 10, 0.5));   // 0.8 >= 0.5 => trip
    assert!(!should_trip(2, 10, 0.5));  // 0.2 < 0.5 => no trip
    assert!(!should_trip(0, 0, 0.5));   // no data => no trip
}

#[test]
fn recovery_rate_computation() {
    let rate = recovery_rate(8, 2);
    // 8 / (8+2) = 0.8
    assert!((rate - 0.8).abs() < 0.01);
}

#[test]
fn cascade_failure_any_dependency() {
    assert!(cascade_failure_check(&[true, false, true]));  // one failure => cascade
    assert!(!cascade_failure_check(&[true, true, true]));   // all healthy => no cascade
}

#[test]
fn fallback_ordering() {
    let fallbacks = vec![
        ("svc-a".to_string(), 0.7),
        ("svc-b".to_string(), 0.95),
        ("svc-c".to_string(), 0.85),
    ];
    let ordered = fallback_priority(&fallbacks);
    // Highest reliability first
    assert_eq!(ordered[0], "svc-b");
    assert_eq!(ordered[1], "svc-c");
    assert_eq!(ordered[2], "svc-a");
}

#[test]
fn event_dedup_keeps_earliest() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 100, kind: "A".into(), payload: "first".into() },
        TimedEvent { id: "e1".into(), timestamp: 200, kind: "A".into(), payload: "second".into() },
        TimedEvent { id: "e2".into(), timestamp: 150, kind: "B".into(), payload: "only".into() },
    ];
    let deduped = dedup_by_id(&events);
    assert_eq!(deduped.len(), 2);
    let e1 = deduped.iter().find(|e| e.id == "e1").unwrap();
    assert_eq!(e1.timestamp, 100);  // should keep earliest
}

#[test]
fn event_merge_preserves_order() {
    let a = vec![
        TimedEvent { id: "a1".into(), timestamp: 1, kind: "X".into(), payload: "".into() },
        TimedEvent { id: "a2".into(), timestamp: 3, kind: "X".into(), payload: "".into() },
    ];
    let b = vec![
        TimedEvent { id: "b1".into(), timestamp: 2, kind: "Y".into(), payload: "".into() },
    ];
    let merged = merge_event_streams(&a, &b);
    assert_eq!(merged[0].timestamp, 1);
    assert_eq!(merged[1].timestamp, 2);
    assert_eq!(merged[2].timestamp, 3);
}
