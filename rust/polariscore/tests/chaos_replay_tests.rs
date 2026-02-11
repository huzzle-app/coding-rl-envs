use polariscore::policy::requires_hold;
use polariscore::resilience::{failover_region, replay_budget};

#[test]
fn replay_chaos_budget_and_failover() {
    let budget = replay_budget(500, 20);
    assert!(budget >= 250);

    let region = failover_region(
        "us-east",
        &["us-east".to_string(), "eu-west".to_string(), "ap-south".to_string()],
        &["eu-west".to_string()],
    );
    assert_eq!(region, "ap-south");
    assert!(requires_hold(68.0, false));
}
