use vectorharbor::allocator::allocate_orders;
use vectorharbor::routing::{choose_route, Route};
use vectorharbor::workflow::can_transition;

#[test]
fn dispatch_routing_workflow_flow() {
    let orders = allocate_orders(vec![("x".to_string(), 5, 20)], 1);
    let route = choose_route(
        &[Route { channel: "north".to_string(), latency: 4 }],
        &[],
    )
    .unwrap();
    assert_eq!(orders.len(), 1);
    assert_eq!(route.channel, "north");
    assert!(can_transition("queued", "allocated"));
}
