use polariscore::resilience::{failover_region, replay_budget, retry_backoff};

#[test]
fn retry_backoff_capped() {
    assert_eq!(retry_backoff(1, 80, 2000), 80);
    assert_eq!(retry_backoff(8, 80, 2000), 2000);
}

#[test]
fn replay_budget_is_bounded() {
    assert_eq!(replay_budget(0, 3), 0);
    assert_eq!(replay_budget(140, 8), 101);
}

#[test]
fn failover_region_skips_degraded() {
    let region = failover_region(
        "us-east",
        &["us-east".to_string(), "eu-central".to_string(), "us-west".to_string()],
        &["eu-central".to_string()],
    );
    assert_eq!(region, "us-west");
}
