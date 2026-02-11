use std::collections::HashMap;

use polariscore::models::{FulfillmentWindow, Incident, Shipment};
use polariscore::workflow::orchestrate_cycle;

#[test]
fn orchestrates_full_cycle() {
    let shipments = vec![
        Shipment { id: "s1".into(), lane: "north".into(), units: 6, priority: 3 },
        Shipment { id: "s2".into(), lane: "south".into(), units: 5, priority: 2 },
    ];
    let windows = vec![
        FulfillmentWindow { id: "w1".into(), start_minute: 10, end_minute: 20, capacity: 6 },
        FulfillmentWindow { id: "w2".into(), start_minute: 25, end_minute: 40, capacity: 6 },
    ];
    let incidents = vec![Incident { id: "i1".into(), severity: 3, domain: "routing".into() }];
    let hubs = HashMap::from([
        ("hub-a".to_string(), 80_u32),
        ("hub-b".to_string(), 65_u32),
        ("hub-c".to_string(), 95_u32),
    ]);

    let report = orchestrate_cycle(shipments, &windows, &incidents, 18.0, &hubs);
    assert!(report.allocations > 0);
    assert!(report.margin_ratio > 0.0);
    assert_eq!(report.selected_hub, "hub-b");
}
