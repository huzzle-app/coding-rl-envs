use std::collections::HashMap;

use polariscore::models::{FulfillmentWindow, Incident, Shipment, ShipmentState};
use polariscore::workflow::{multi_batch_schedule, plan_fulfillment, ShipmentStateMachine};

#[test]
fn can_deliver_only_from_in_transit() {
    // Allocated shipments should NOT be deliverable — only InTransit should be.
    // Bug: can_deliver() includes Allocated.
    let mut sm = ShipmentStateMachine::new();
    sm.transition(ShipmentState::Queued).unwrap();
    sm.transition(ShipmentState::Allocated).unwrap();
    assert!(
        !sm.can_deliver(),
        "Allocated state should not be deliverable"
    );
}

#[test]
fn held_cannot_transition_to_delivered() {
    // Held → Delivered should be an invalid transition.
    // Bug: the match arm allows Held → Delivered.
    let mut sm = ShipmentStateMachine::new();
    sm.transition(ShipmentState::Queued).unwrap();
    sm.transition(ShipmentState::Allocated).unwrap();
    sm.transition(ShipmentState::Held).unwrap();
    let result = sm.transition(ShipmentState::Delivered);
    assert!(
        result.is_err(),
        "Held → Delivered should be invalid, but transition succeeded"
    );
}

#[test]
fn plan_fulfillment_uses_average_risk() {
    // Combined risk should be the average of batch scores, not the maximum.
    // Bug: uses f64::max fold.
    let batch_low = vec![Shipment {
        id: "s1".into(),
        lane: "a".into(),
        units: 5,
        priority: 1,
    }];
    let batch_high = vec![Shipment {
        id: "s2".into(),
        lane: "b".into(),
        units: 50,
        priority: 5,
    }];
    let windows = vec![FulfillmentWindow {
        id: "w1".into(),
        start_minute: 0,
        end_minute: 60,
        capacity: 200,
    }];
    let incidents = vec![Incident {
        id: "i1".into(),
        severity: 5,
        domain: "logistics".into(),
    }];
    let hubs = HashMap::from([("hub-a".to_string(), 50_u32)]);

    let plan = plan_fulfillment(&[batch_low, batch_high], &windows, &incidents, 20.0, &hubs);

    // The average should be strictly less than the max of the two risk scores.
    // With max-fold, combined_risk equals the higher score.
    // With average, combined_risk is between the two.
    let high_risk = polariscore::policy::risk_score(
        &[Shipment {
            id: "s2".into(),
            lane: "b".into(),
            units: 50,
            priority: 5,
        }],
        &incidents,
        20.0,
    );
    let low_risk = polariscore::policy::risk_score(
        &[Shipment {
            id: "s1".into(),
            lane: "a".into(),
            units: 5,
            priority: 1,
        }],
        &incidents,
        20.0,
    );
    let expected_avg = (high_risk + low_risk) / 2.0;
    assert!(
        (plan.combined_risk - expected_avg).abs() < 0.1,
        "combined_risk should be average ({:.2}), got {:.2} (max would be {:.2})",
        expected_avg,
        plan.combined_risk,
        high_risk
    );
}

#[test]
fn plan_margin_is_revenue_based() {
    // overall_margin should be (revenue - cost) / revenue, which is <= 1.0.
    // Bug: divides by cost, which can yield values >> 1.0 for small batches.
    let batch = vec![Shipment {
        id: "s1".into(),
        lane: "a".into(),
        units: 1,
        priority: 1,
    }];
    let windows = vec![FulfillmentWindow {
        id: "w1".into(),
        start_minute: 0,
        end_minute: 60,
        capacity: 100,
    }];
    let hubs = HashMap::from([("hub-a".to_string(), 50_u32)]);
    let plan = plan_fulfillment(&[batch], &windows, &[], 20.0, &hubs);

    assert!(
        plan.overall_margin <= 1.0,
        "Revenue-based margin should be <= 1.0, got {}",
        plan.overall_margin
    );
}

#[test]
fn multi_batch_uses_independent_capacity() {
    // Each batch should get fresh capacity from the windows.
    // Bug: shared mutable caps across batches — batch 0 consumes capacity, batch 1 gets nothing.
    let batch_a = vec![Shipment {
        id: "a1".into(),
        lane: "l".into(),
        units: 5,
        priority: 3,
    }];
    let batch_b = vec![Shipment {
        id: "b1".into(),
        lane: "l".into(),
        units: 5,
        priority: 3,
    }];
    let windows = vec![FulfillmentWindow {
        id: "w1".into(),
        start_minute: 0,
        end_minute: 60,
        capacity: 5,
    }];

    let results = multi_batch_schedule(&[batch_a, batch_b], &windows);
    assert_eq!(results.len(), 2);
    let (_, allocs_a) = &results[0];
    let (_, allocs_b) = &results[1];

    let units_a: u32 = allocs_a.iter().map(|a| a.units).sum();
    let units_b: u32 = allocs_b.iter().map(|a| a.units).sum();

    assert_eq!(
        units_a, 5,
        "Batch 0 should allocate all 5 units, got {}",
        units_a
    );
    assert_eq!(
        units_b, 5,
        "Batch 1 should independently allocate 5 units, got {}",
        units_b
    );
}
