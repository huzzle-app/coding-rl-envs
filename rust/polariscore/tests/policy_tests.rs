use polariscore::models::{Incident, Shipment};
use polariscore::policy::{compliance_tier, requires_hold, risk_score};

#[test]
fn risk_score_increases_with_incidents() {
    let shipments = vec![Shipment { id: "s1".into(), lane: "l1".into(), units: 10, priority: 3 }];
    let low = risk_score(&shipments, &[], 22.0);
    let high = risk_score(
        &shipments,
        &[Incident { id: "i1".into(), severity: 4, domain: "cold-chain".into() }],
        38.0,
    );
    assert!(high > low);
}

#[test]
fn hold_and_tier_rules() {
    assert!(requires_hold(72.0, false));
    assert!(requires_hold(55.0, true));
    assert_eq!(compliance_tier(78.0), "board-review");
    assert_eq!(compliance_tier(20.0), "auto");
}
