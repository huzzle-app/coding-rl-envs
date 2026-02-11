use tensorforge::allocator::allocate_orders;
use tensorforge::routing::{choose_route, Route};
use tensorforge::workflow::{can_transition, WorkflowEngine};
use tensorforge::config::ServiceConfig;
use tensorforge::concurrency::SharedRegistry;
use tensorforge::events::{TimedEvent, EventLog, merge_event_streams};
use tensorforge::telemetry::{MetricsCollector, MetricSample};

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

#[test]
fn config_registry_workflow() {
    let cfg = ServiceConfig::new("gateway");
    let registry = SharedRegistry::new();
    registry.register(cfg.name.clone(), format!("port={}", cfg.port));
    assert!(registry.lookup("gateway").is_some());
    assert_eq!(registry.count(), 1);
}

#[test]
fn event_driven_workflow() {
    let log = EventLog::new(100);
    log.append(TimedEvent { id: "e1".into(), timestamp: 100, kind: "dispatch".into(), payload: "order-1".into() });
    log.append(TimedEvent { id: "e2".into(), timestamp: 200, kind: "route".into(), payload: "order-1".into() });
    log.append(TimedEvent { id: "e3".into(), timestamp: 300, kind: "arrive".into(), payload: "order-1".into() });
    assert_eq!(log.count(), 3);
    let latest = log.latest().unwrap();
    assert_eq!(latest.id, "e3");
}

#[test]
fn cross_module_event_merge() {
    let stream_a = vec![
        TimedEvent { id: "a1".into(), timestamp: 100, kind: "X".into(), payload: "".into() },
        TimedEvent { id: "a2".into(), timestamp: 300, kind: "X".into(), payload: "".into() },
    ];
    let stream_b = vec![
        TimedEvent { id: "b1".into(), timestamp: 200, kind: "Y".into(), payload: "".into() },
    ];
    let merged = merge_event_streams(&stream_a, &stream_b);
    assert_eq!(merged.len(), 3);
    // Should be in ascending timestamp order
    assert!(merged[0].timestamp <= merged[1].timestamp);
    assert!(merged[1].timestamp <= merged[2].timestamp);
}

#[test]
fn telemetry_collection_flow() {
    let collector = MetricsCollector::new(100);
    collector.record(MetricSample { name: "latency".into(), value: 50.0, timestamp: 1 });
    collector.record(MetricSample { name: "latency".into(), value: 75.0, timestamp: 2 });
    collector.record(MetricSample { name: "errors".into(), value: 3.0, timestamp: 3 });
    assert_eq!(collector.count(), 3);
    let latency_samples = collector.get_by_name("latency");
    assert_eq!(latency_samples.len(), 2);
}
