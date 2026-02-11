use geneforge::resilience::{replay_sequence, ReplayEvent};

#[test]
fn ordered_vs_shuffled_replay_converges() {
    let ordered = vec![
        ReplayEvent { version: 21, idempotency_key: "k1".into(), findings_delta: 5, samples_delta: 1 },
        ReplayEvent { version: 22, idempotency_key: "k2".into(), findings_delta: -1, samples_delta: 0 },
        ReplayEvent { version: 23, idempotency_key: "k3".into(), findings_delta: 3, samples_delta: 2 },
    ];
    let shuffled = vec![ordered[2].clone(), ordered[0].clone(), ordered[1].clone()];
    let a = replay_sequence(30, 10, 20, &ordered);
    let b = replay_sequence(30, 10, 20, &shuffled);
    assert_eq!(a, b);
}

#[test]
fn stale_versions_are_ignored() {
    let events = vec![
        ReplayEvent { version: 19, idempotency_key: "old".into(), findings_delta: 99, samples_delta: 99 },
        ReplayEvent { version: 20, idempotency_key: "eq".into(), findings_delta: 2, samples_delta: 1 },
    ];
    let s = replay_sequence(10, 3, 20, &events);
    assert_eq!(s.applied, 1);
    assert_eq!(s.findings, 12);
    assert_eq!(s.samples, 4);
}

#[test]
fn idempotency_collision_dedupes() {
    let events = vec![
        ReplayEvent { version: 21, idempotency_key: "dup".into(), findings_delta: 2, samples_delta: 1 },
        ReplayEvent { version: 22, idempotency_key: "dup".into(), findings_delta: 10, samples_delta: 10 },
        ReplayEvent { version: 23, idempotency_key: "ok".into(), findings_delta: 1, samples_delta: 0 },
    ];
    let s = replay_sequence(8, 4, 20, &events);
    assert_eq!(s.applied, 2);
}

#[test]
fn stale_duplicate_does_not_shadow_fresh_event() {
    let events = vec![
        ReplayEvent { version: 19, idempotency_key: "dup".into(), findings_delta: 99, samples_delta: 99 },
        ReplayEvent { version: 21, idempotency_key: "dup".into(), findings_delta: 4, samples_delta: 2 },
    ];
    let s = replay_sequence(8, 4, 20, &events);
    assert_eq!(s.applied, 1);
    assert_eq!(s.findings, 12);
    assert_eq!(s.samples, 6);
}
