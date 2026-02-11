use polariscore::allocator::{allocate_shipments, unallocated_units};
use polariscore::models::{FulfillmentWindow, Shipment};

#[test]
fn allocates_by_priority() {
    let shipments = vec![
        Shipment { id: "s1".into(), lane: "l1".into(), units: 5, priority: 1 },
        Shipment { id: "s2".into(), lane: "l1".into(), units: 4, priority: 3 },
    ];
    let windows = vec![FulfillmentWindow { id: "w1".into(), start_minute: 10, end_minute: 20, capacity: 6 }];
    let allocations = allocate_shipments(shipments.clone(), &windows);
    assert_eq!(allocations.first().map(|entry| entry.shipment_id.as_str()), Some("s2"));
    assert_eq!(unallocated_units(&shipments, &allocations), 3);
}

#[test]
fn full_allocation_when_capacity_is_enough() {
    let shipments = vec![Shipment { id: "s1".into(), lane: "l1".into(), units: 3, priority: 2 }];
    let windows = vec![FulfillmentWindow { id: "w1".into(), start_minute: 0, end_minute: 10, capacity: 5 }];
    let allocations = allocate_shipments(shipments.clone(), &windows);
    assert_eq!(unallocated_units(&shipments, &allocations), 0);
}
