use vectorharbor::resilience::{replay, Event};

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
