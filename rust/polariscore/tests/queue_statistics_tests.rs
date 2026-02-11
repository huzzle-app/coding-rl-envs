use polariscore::queue::{order_queue, queue_pressure, QueueItem};
use polariscore::statistics::{percentile, rolling_sla, trimmed_mean};

#[test]
fn queue_order_and_pressure() {
    let ranked = order_queue(&[
        QueueItem { id: "a".into(), severity: 2, waited_seconds: 20 },
        QueueItem { id: "b".into(), severity: 4, waited_seconds: 10 },
        QueueItem { id: "c".into(), severity: 1, waited_seconds: 800 },
    ]);
    assert_eq!(ranked.first().map(|item| item.id.as_str()), Some("b"));
    assert!(queue_pressure(&ranked) > 0.0);
}

#[test]
fn statistics_functions() {
    assert_eq!(percentile(&[10, 20, 30, 40, 50], 90), 50);
    assert!((rolling_sla(&[90, 110, 160], 120) - 0.6666).abs() < 0.01);
    assert!((trimmed_mean(&[1.0, 2.0, 3.0, 100.0], 0.25) - 2.5).abs() < 0.001);
}
