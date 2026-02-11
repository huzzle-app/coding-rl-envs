use aerolith::resilience::{replay_sequence, ReplayEvent};

#[test]
fn ordered_vs_shuffled_replay_converges() {
    let ordered = vec![
        ReplayEvent { version: 11, idempotency_key: "k1".into(), generation_delta: 30.0, reserve_delta: 4.0 },
        ReplayEvent { version: 12, idempotency_key: "k2".into(), generation_delta: -10.0, reserve_delta: 1.0 },
        ReplayEvent { version: 13, idempotency_key: "k3".into(), generation_delta: 8.0, reserve_delta: -2.0 },
    ];
    let shuffled = vec![ordered[2].clone(), ordered[0].clone(), ordered[1].clone()];
    let a = replay_sequence(500.0, 70.0, 10, &ordered);
    let b = replay_sequence(500.0, 70.0, 10, &shuffled);
    assert_eq!(a, b);
}

#[test]
fn stale_versions_are_ignored() {
    let events = vec![
        ReplayEvent { version: 9, idempotency_key: "old".into(), generation_delta: 100.0, reserve_delta: 100.0 },
        ReplayEvent { version: 10, idempotency_key: "eq".into(), generation_delta: 5.0, reserve_delta: 2.0 },
    ];
    let s = replay_sequence(400.0, 50.0, 10, &events);
    assert_eq!(s.applied, 1);
    assert_eq!(s.generation_mw, 405.0);
    assert_eq!(s.reserve_mw, 52.0);
}

#[test]
fn idempotency_collision_dedupes() {
    let events = vec![
        ReplayEvent { version: 11, idempotency_key: "dup".into(), generation_delta: 5.0, reserve_delta: 1.0 },
        ReplayEvent { version: 12, idempotency_key: "dup".into(), generation_delta: 50.0, reserve_delta: 20.0 },
        ReplayEvent { version: 13, idempotency_key: "ok".into(), generation_delta: -2.0, reserve_delta: 0.0 },
    ];
    let s = replay_sequence(300.0, 40.0, 10, &events);
    assert_eq!(s.applied, 2);
}

#[test]
fn stale_duplicate_does_not_shadow_fresh_event() {
    let events = vec![
        ReplayEvent { version: 9, idempotency_key: "dup".into(), generation_delta: 100.0, reserve_delta: 100.0 },
        ReplayEvent { version: 11, idempotency_key: "dup".into(), generation_delta: 7.0, reserve_delta: 3.0 },
    ];
    let s = replay_sequence(300.0, 40.0, 10, &events);
    assert_eq!(s.applied, 1);
    assert_eq!(s.generation_mw, 307.0);
    assert_eq!(s.reserve_mw, 43.0);
}
