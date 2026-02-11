use vectorharbor::allocator::{
    allocate_costs, check_capacity, compare_by_urgency_then_eta, dispatch_batch,
    estimate_cost, estimate_turnaround, find_available_slots, has_conflict,
    validate_batch, BerthSlot, RollingWindowScheduler,
};
use vectorharbor::contracts::{
    get_service_url, service_definitions, topological_order, validate_contract,
};
use vectorharbor::models::{
    classify_severity, create_batch_orders, validate_dispatch_order, DispatchOrder,
    VesselManifest, SEV_CRITICAL, SEV_HIGH, SEV_INFO,
};
use vectorharbor::policy::{
    check_sla_compliance, get_metadata, previous_policy, sla_percentage, PolicyEngine,
};
use vectorharbor::queue::{
    estimate_wait_time, queue_health, PriorityQueue, QueueItem,
};
use vectorharbor::resilience::{
    deduplicate, Checkpoint, CheckpointManager, CircuitBreaker, Event, CB_CLOSED, CB_OPEN,
};
use vectorharbor::routing::{
    channel_score, compare_routes, estimate_route_cost, estimate_transit_time,
    plan_multi_leg, Route, RouteTable, Waypoint,
};
use vectorharbor::security::{
    is_allowed_origin, sanitise_path, sign_manifest, verify_manifest, TokenStore,
};
use vectorharbor::statistics::{
    generate_heatmap, mean, median, moving_average, stddev, variance, HeatmapEvent,
    ResponseTimeTracker,
};
use vectorharbor::workflow::{
    allowed_transitions, is_terminal_state, is_valid_state, shortest_path, WorkflowEngine,
};

// ---- Allocator extended ----

#[test]
fn allocator_batch() {
    let result = dispatch_batch(
        vec![
            ("a".into(), 10, 1),
            ("b".into(), 20, 2),
            ("c".into(), 5, 3),
        ],
        2,
    );
    assert_eq!(result.planned.len(), 2);
    assert_eq!(result.rejected.len(), 1);
    assert_eq!(result.planned[0].0, "b");
}

#[test]
fn allocator_berth_conflict() {
    let a = BerthSlot {
        berth_id: "B1".into(), start_hour: 0, end_hour: 6, occupied: true, vessel_id: None,
    };
    let b = BerthSlot {
        berth_id: "B1".into(), start_hour: 4, end_hour: 10, occupied: false, vessel_id: None,
    };
    let c = BerthSlot {
        berth_id: "B2".into(), start_hour: 0, end_hour: 6, occupied: false, vessel_id: None,
    };
    assert!(has_conflict(&a, &b));
    assert!(!has_conflict(&a, &c));
}

#[test]
fn allocator_available_slots() {
    let slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 0, end_hour: 6, occupied: true, vessel_id: None },
        BerthSlot { berth_id: "B1".into(), start_hour: 6, end_hour: 12, occupied: false, vessel_id: None },
        BerthSlot { berth_id: "B2".into(), start_hour: 0, end_hour: 12, occupied: false, vessel_id: None },
    ];
    assert_eq!(find_available_slots(&slots).len(), 2);
}

#[test]
fn allocator_cost_estimation() {
    let cost_critical = estimate_cost(5, 10, 100.0);
    let cost_low = estimate_cost(1, 120, 100.0);
    assert!(cost_critical > cost_low);
    assert!((cost_critical - 1500.0).abs() < 0.01);
}

#[test]
fn allocator_cost_allocation() {
    let orders = vec![("a".into(), 30, 1), ("b".into(), 70, 2)];
    let costs = allocate_costs(&orders, 1000.0);
    assert_eq!(costs.len(), 2);
    let total: f64 = costs.iter().map(|c| c.1).sum();
    assert!((total - 1000.0).abs() < 1.0);
}

#[test]
fn allocator_turnaround() {
    let normal = estimate_turnaround(1000, false);
    let hazmat = estimate_turnaround(1000, true);
    assert!(hazmat > normal);
    assert!((hazmat - normal * 1.5).abs() < 0.01);
}

#[test]
fn allocator_validation() {
    assert!(validate_batch(&[("a".into(), 10, 1), ("b".into(), 20, 2)]).is_ok());
    assert!(validate_batch(&[("a".into(), 10, 1), ("a".into(), 20, 2)]).is_err());
    assert!(validate_batch(&[("".into(), 10, 1)]).is_err());
}

// ---- Routing extended ----

#[test]
fn routing_channel_score() {
    let s1 = channel_score(5, 0.95, 8);
    let s2 = channel_score(10, 0.85, 5);
    assert!(s1 > s2);
    assert_eq!(channel_score(0, 0.9, 5), 0.0);
}

#[test]
fn routing_transit_time() {
    let t = estimate_transit_time(100.0, 20.0);
    assert!((t - 5.0).abs() < 0.001);
    assert_eq!(estimate_transit_time(100.0, 0.0), f64::MAX);
}

#[test]
fn routing_multi_leg() {
    let plan = plan_multi_leg(
        &[
            Waypoint { port: "A".into(), distance_nm: 100.0 },
            Waypoint { port: "B".into(), distance_nm: 200.0 },
        ],
        15.0,
    );
    assert_eq!(plan.legs.len(), 2);
    assert!((plan.total_distance - 300.0).abs() < 0.01);
    assert!((plan.estimated_hours - 20.0).abs() < 0.01);
}

#[test]
fn routing_table() {
    let table = RouteTable::new();
    table.add(Route { channel: "alpha".into(), latency: 5 });
    table.add(Route { channel: "beta".into(), latency: 3 });
    assert_eq!(table.count(), 2);
    assert_eq!(table.get("alpha").unwrap().latency, 5);
    table.remove("alpha");
    assert_eq!(table.count(), 1);
    assert!(table.get("alpha").is_none());
}

#[test]
fn routing_cost() {
    let cost = estimate_route_cost(500.0, 2.0, 1000.0);
    assert!((cost - 2000.0).abs() < 0.01);
}

// ---- Policy extended ----

#[test]
fn policy_deescalation() {
    assert_eq!(previous_policy("watch"), "normal");
    assert_eq!(previous_policy("restricted"), "watch");
    assert_eq!(previous_policy("normal"), "normal");
}

#[test]
fn policy_engine_lifecycle() {
    let engine = PolicyEngine::new();
    assert_eq!(engine.current(), "normal");
    engine.escalate(3);
    assert_eq!(engine.current(), "watch");
    engine.escalate(5);
    assert_eq!(engine.current(), "restricted");
    engine.deescalate();
    assert_eq!(engine.current(), "watch");
    assert_eq!(engine.history().len(), 3);
    engine.reset();
    assert_eq!(engine.current(), "normal");
    assert!(engine.history().is_empty());
}

#[test]
fn policy_sla() {
    assert!(check_sla_compliance(30, 60));
    assert!(!check_sla_compliance(90, 60));
}

#[test]
fn policy_sla_percentage() {
    let records = vec![(20, 30), (40, 30), (25, 30)];
    let pct = sla_percentage(&records);
    assert!((pct - 66.66666).abs() < 0.01);
    assert!((sla_percentage(&[]) - 100.0).abs() < 0.01);
}

#[test]
fn policy_metadata() {
    let m = get_metadata("normal").unwrap();
    assert_eq!(m.max_retries, 3);
    let h = get_metadata("halted").unwrap();
    assert_eq!(h.max_retries, 0);
    assert!(get_metadata("unknown").is_none());
}

// ---- Queue extended ----

#[test]
fn queue_priority() {
    let q = PriorityQueue::new(10);
    q.enqueue(QueueItem { id: "low".into(), priority: 1 });
    q.enqueue(QueueItem { id: "high".into(), priority: 10 });
    q.enqueue(QueueItem { id: "mid".into(), priority: 5 });
    let top = q.dequeue().unwrap();
    assert_eq!(top.id, "high");
    assert_eq!(q.size(), 2);
}

#[test]
fn queue_drain() {
    let q = PriorityQueue::new(10);
    q.enqueue(QueueItem { id: "a".into(), priority: 1 });
    q.enqueue(QueueItem { id: "b".into(), priority: 2 });
    let drained = q.drain();
    assert_eq!(drained.len(), 2);
    assert_eq!(q.size(), 0);
}

#[test]
fn queue_health_check() {
    let h = queue_health(800, 1000);
    assert_eq!(h.status, "warning");
    let h2 = queue_health(100, 1000);
    assert_eq!(h2.status, "healthy");
    let h3 = queue_health(1000, 1000);
    assert_eq!(h3.status, "critical");
}

#[test]
fn queue_wait_estimation() {
    let t = estimate_wait_time(100, 10.0);
    assert!((t - 10.0).abs() < 0.01);
    assert_eq!(estimate_wait_time(100, 0.0), f64::MAX);
}

// ---- Security extended ----

#[test]
fn security_manifest() {
    let sig = sign_manifest("cargo:v1", "secret-key");
    assert!(verify_manifest("cargo:v1", "secret-key", &sig));
    assert!(!verify_manifest("cargo:v2", "secret-key", &sig));
    assert!(!verify_manifest("cargo:v1", "wrong-key", &sig));
}

#[test]
fn security_path_sanitise() {
    assert_eq!(sanitise_path("../../../etc/passwd"), "etc/passwd");
    assert_eq!(sanitise_path("/data/files/report.pdf"), "data/files/report.pdf");
    assert_eq!(sanitise_path("safe/path.txt"), "safe/path.txt");
}

#[test]
fn security_origin() {
    assert!(is_allowed_origin("https://vectorharbor.internal"));
    assert!(!is_allowed_origin("https://evil.com"));
}

// ---- Resilience extended ----

#[test]
fn resilience_checkpoint() {
    let mgr = CheckpointManager::new(100);
    mgr.record(Checkpoint { id: "cp1".into(), sequence: 100, timestamp: 1000 });
    mgr.record(Checkpoint { id: "cp2".into(), sequence: 200, timestamp: 2000 });
    assert_eq!(mgr.count(), 2);
    let cp = mgr.get("cp1").unwrap();
    assert_eq!(cp.sequence, 100);
    assert!(mgr.should_checkpoint(200, 50));
    assert!(!mgr.should_checkpoint(120, 50));
    mgr.reset();
    assert_eq!(mgr.count(), 0);
}

#[test]
fn resilience_circuit_breaker() {
    let cb = CircuitBreaker::new(3, 2);
    assert_eq!(cb.state(), CB_CLOSED);
    cb.record_failure();
    cb.record_failure();
    cb.record_failure();
    assert_eq!(cb.state(), CB_OPEN);
    assert!(!cb.is_call_permitted());
    cb.attempt_reset();
    assert_eq!(cb.state(), "half_open");
    cb.record_success();
    cb.record_success();
    assert_eq!(cb.state(), CB_CLOSED);
}

#[test]
fn resilience_dedup() {
    let events = vec![
        Event { id: "a".into(), sequence: 1 },
        Event { id: "b".into(), sequence: 2 },
        Event { id: "a".into(), sequence: 3 },
    ];
    let deduped = deduplicate(&events);
    assert_eq!(deduped.len(), 2);
    assert_eq!(deduped[0].id, "a");
    assert_eq!(deduped[0].sequence, 1);
}

// ---- Statistics extended ----

#[test]
fn stats_descriptive() {
    let vals = vec![2.0, 4.0, 6.0, 8.0];
    assert!((mean(&vals) - 5.0).abs() < 0.001);
    assert!((median(&vals) - 5.0).abs() < 0.001);
    assert_eq!(mean(&[]), 0.0);
}

#[test]
fn stats_variance() {
    let vals = vec![2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
    let v = variance(&vals);
    assert!(v > 0.0);
    let s = stddev(&vals);
    assert!((s - v.sqrt()).abs() < 0.001);
}

#[test]
fn stats_response_tracker() {
    let tracker = ResponseTimeTracker::new(5);
    for ms in [10.0, 20.0, 30.0, 40.0, 50.0] {
        tracker.record(ms);
    }
    assert_eq!(tracker.count(), 5);
    assert!(tracker.p50() > 0.0);
    assert!(tracker.p95() >= tracker.p50());
    assert!(tracker.p99() >= tracker.p95());
}

#[test]
fn stats_moving_average() {
    let ma = moving_average(&[1.0, 2.0, 3.0, 4.0, 5.0], 3);
    assert_eq!(ma.len(), 3);
    assert!((ma[0] - 2.0).abs() < 0.001);
    assert!((ma[2] - 4.0).abs() < 0.001);
}

#[test]
fn stats_heatmap() {
    let events = vec![
        HeatmapEvent { x: 0.0, y: 0.0, weight: 1.0 },
        HeatmapEvent { x: 1.0, y: 1.0, weight: 2.0 },
        HeatmapEvent { x: 0.0, y: 0.0, weight: 3.0 },
    ];
    let cells = generate_heatmap(&events, 3, 3);
    assert_eq!(cells.len(), 9);
    let origin = cells.iter().find(|c| c.row == 0 && c.col == 0).unwrap();
    assert!((origin.value - 4.0).abs() < 0.01);
}

// ---- Workflow extended ----

#[test]
fn workflow_shortest_path() {
    let path = shortest_path("queued", "arrived").unwrap();
    assert_eq!(path, vec!["queued", "allocated", "departed", "arrived"]);
    assert!(shortest_path("arrived", "queued").is_none());
}

#[test]
fn workflow_engine() {
    let engine = WorkflowEngine::new();
    engine.register("order-1");
    assert_eq!(engine.get_state("order-1"), Some("queued".to_string()));
    assert_eq!(engine.active_count(), 1);
    let r = engine.transition("order-1", "allocated", 100);
    assert!(r.success);
    let r = engine.transition("order-1", "departed", 200);
    assert!(r.success);
    let r = engine.transition("order-1", "arrived", 300);
    assert!(r.success);
    assert!(engine.is_terminal("order-1"));
    assert_eq!(engine.active_count(), 0);
}

#[test]
fn workflow_terminal() {
    assert!(is_terminal_state("arrived"));
    assert!(is_terminal_state("cancelled"));
    assert!(!is_terminal_state("queued"));
    assert!(is_valid_state("queued"));
    assert!(!is_valid_state("unknown"));
}

#[test]
fn workflow_audit() {
    let engine = WorkflowEngine::new();
    engine.register("e1");
    engine.transition("e1", "allocated", 1);
    engine.transition("e1", "departed", 2);
    let log = engine.audit_log();
    assert_eq!(log.len(), 2);
    assert!(log[0].contains("queued"));
    assert!(log[1].contains("departed"));
}

// ---- Model extended ----

#[test]
fn model_vessel_manifest() {
    let v = VesselManifest {
        vessel_id: "V-1".into(), name: "MV Test".into(),
        cargo_tons: 55000.0, containers: 4000, hazmat: true,
    };
    assert!(v.is_heavy());
    assert!((v.container_weight_ratio() - 13.75).abs() < 0.01);
    let light = VesselManifest {
        vessel_id: "V-2".into(), name: "MV Small".into(),
        cargo_tons: 10000.0, containers: 0, hazmat: false,
    };
    assert!(!light.is_heavy());
    assert_eq!(light.container_weight_ratio(), 0.0);
}

#[test]
fn model_batch_creation() {
    let batch = create_batch_orders(&["d1", "d2", "d3"], 4, 30);
    assert_eq!(batch.len(), 3);
    assert_eq!(batch[0].severity, 4);
    assert_eq!(batch[0].sla_minutes, 30);
    let clamped = create_batch_orders(&["x"], 10, 0);
    assert_eq!(clamped[0].severity, SEV_CRITICAL);
    assert_eq!(clamped[0].sla_minutes, 1);
}

#[test]
fn model_validation() {
    let good = DispatchOrder { id: "d1".into(), severity: 3, sla_minutes: 60 };
    assert!(validate_dispatch_order(&good).is_ok());
    let bad_id = DispatchOrder { id: "".into(), severity: 3, sla_minutes: 60 };
    assert!(validate_dispatch_order(&bad_id).is_err());
    let bad_sev = DispatchOrder { id: "d1".into(), severity: 0, sla_minutes: 60 };
    assert!(validate_dispatch_order(&bad_sev).is_err());
    let bad_sla = DispatchOrder { id: "d1".into(), severity: 3, sla_minutes: 0 };
    assert!(validate_dispatch_order(&bad_sla).is_err());
}

#[test]
fn model_classify_severity() {
    assert_eq!(classify_severity("Critical engine failure"), SEV_CRITICAL);
    assert_eq!(classify_severity("High priority cargo"), SEV_HIGH);
    assert_eq!(classify_severity("routine maintenance"), SEV_INFO);
}

// ---- Contracts extended ----

#[test]
fn contracts_service_defs() {
    let defs = service_definitions();
    assert_eq!(defs.len(), 8);
    assert_eq!(defs[0].id, "gateway");
    assert!(defs[0].dependencies.is_empty());
    assert!(defs[1].dependencies.contains(&"gateway".to_string()));
}

#[test]
fn contracts_url() {
    let url = get_service_url("gateway").unwrap();
    assert_eq!(url, "http://gateway:8120/health");
    assert!(get_service_url("nonexistent").is_none());
}

#[test]
fn contracts_validation() {
    let defs = service_definitions();
    assert!(validate_contract(&defs).is_ok());
}

#[test]
fn contracts_topo_order() {
    let defs = service_definitions();
    let order = topological_order(&defs).unwrap();
    assert_eq!(order[0], "gateway");
    let gw_pos = order.iter().position(|s| s == "gateway").unwrap();
    let rt_pos = order.iter().position(|s| s == "routing").unwrap();
    assert!(gw_pos < rt_pos);
}

// ---- Integration ----

#[test]
fn end_to_end_dispatch() {
    use vectorharbor::allocator::allocate_orders;
    use vectorharbor::routing::{choose_route, Route};
    use vectorharbor::policy::next_policy;
    use vectorharbor::workflow::can_transition;
    use vectorharbor::security::digest;

    let order = DispatchOrder { id: "E2E-1".into(), severity: 5, sla_minutes: 15 };
    assert!(validate_dispatch_order(&order).is_ok());

    let planned = allocate_orders(
        vec![(order.id.clone(), order.urgency_score(), 10)],
        1,
    );
    assert_eq!(planned.len(), 1);

    let route = choose_route(
        &[Route { channel: "alpha".into(), latency: 3 }],
        &[],
    ).unwrap();
    assert_eq!(route.channel, "alpha");

    let pol = next_policy("normal", 0);
    assert_eq!(pol, "normal");

    assert!(can_transition("queued", "allocated"));
    assert!(can_transition("allocated", "departed"));

    let sig = digest(&order.id);
    assert!(!sig.is_empty());
}
