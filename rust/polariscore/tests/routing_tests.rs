use std::collections::HashMap;

use polariscore::routing::{route_segments, select_hub};

#[test]
fn select_hub_respects_blocked_nodes() {
    let candidates = vec!["hub-a".to_string(), "hub-b".to_string(), "hub-c".to_string()];
    let latency = HashMap::from([
        ("hub-a".to_string(), 75_u32),
        ("hub-b".to_string(), 42_u32),
        ("hub-c".to_string(), 63_u32),
    ]);
    let blocked = vec!["hub-b".to_string()];

    let selected = select_hub(&candidates, &latency, &blocked);
    assert_eq!(selected.as_deref(), Some("hub-c"));
}

#[test]
fn route_segments_orders_by_load() {
    let paths = HashMap::from([(String::from("flow-1"), vec!["a".to_string(), "b".to_string(), "c".to_string()])]);
    let load = HashMap::from([
        (String::from("a"), 0.8),
        (String::from("b"), 0.2),
        (String::from("c"), 0.5),
    ]);

    let routed = route_segments(&paths, &load);
    assert_eq!(routed.get("flow-1").cloned(), Some(vec!["b".to_string(), "c".to_string(), "a".to_string()]));
}
