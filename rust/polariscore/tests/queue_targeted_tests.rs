use polariscore::queue::{round_robin_drain, QueueItem};

#[test]
fn round_robin_drains_fairly() {
    // With budget for 4 items across 2 queues, each should get 2.
    // Bug: `while` drains q1 entirely first (3 from q1, 1 from q2).
    let q1 = vec![
        QueueItem { id: "a1".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "a2".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "a3".into(), severity: 1, waited_seconds: 0 },
    ];
    let q2 = vec![
        QueueItem { id: "b1".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "b2".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "b3".into(), severity: 1, waited_seconds: 0 },
    ];

    // cost per item = severity*5 + 1 = 6, budget for 4 items = 24
    let results = round_robin_drain(&[q1, q2], 24);

    assert_eq!(results.len(), 2);
    assert_eq!(
        results[0].len(),
        2,
        "Queue 0 should get 2 items in round-robin, got {}",
        results[0].len()
    );
    assert_eq!(
        results[1].len(),
        2,
        "Queue 1 should get 2 items in round-robin, got {}",
        results[1].len()
    );
}
