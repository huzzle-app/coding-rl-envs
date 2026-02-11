use tensorforge::allocator::{
    allocate_costs, check_capacity, compare_by_urgency_then_eta, dispatch_batch,
    estimate_cost, estimate_turnaround, find_available_slots, has_conflict,
    validate_batch, weighted_allocate, berth_utilization, round_allocation,
    cost_per_unit, normalize_urgency, priority_score, is_over_capacity,
    BerthSlot, RollingWindowScheduler,
};
use tensorforge::contracts::{
    get_service_url, service_definitions, topological_order, validate_contract,
    health_endpoint, dependency_count, is_critical_path, service_version_check,
    find_orphan_services, port_collision_check, contract_summary,
};
use tensorforge::models::{
    classify_severity, create_batch_orders, validate_dispatch_order, DispatchOrder,
    VesselManifest, SEV_CRITICAL, SEV_HIGH, SEV_INFO, severity_label, weight_class,
    estimated_crew, order_priority_compare, total_cargo, hazmat_surcharge, eta_minutes,
};
use tensorforge::policy::{
    check_sla_compliance, get_metadata, previous_policy, sla_percentage, PolicyEngine,
    policy_weight, escalation_needed, risk_score, within_grace_period,
    max_retries_for_policy, cooldown_multiplier,
};
use tensorforge::queue::{
    estimate_wait_time, queue_health, PriorityQueue, QueueItem,
    batch_enqueue, priority_boost, fairness_index, requeue_expired,
    weighted_wait_time, queue_pressure, drain_percentage,
};
use tensorforge::resilience::{
    deduplicate, Checkpoint, CheckpointManager, CircuitBreaker, Event, CB_CLOSED, CB_OPEN,
    replay_window, event_ordering, idempotent_apply, retry_delay,
    should_trip, half_open_max_calls, failure_window_expired,
    recovery_rate, checkpoint_interval_ok, degradation_level,
    bulkhead_permits_available, circuit_state_duration,
};
use tensorforge::routing::{
    channel_score, compare_routes, estimate_route_cost, estimate_transit_time,
    plan_multi_leg, Route, RouteTable, Waypoint,
    weighted_route_score, best_route, route_failover, distance_between,
    normalize_latency, fuel_efficiency, total_port_fees, route_available, knots_to_kmh,
};
use tensorforge::security::{
    is_allowed_origin, sanitise_path, sign_manifest, verify_manifest, TokenStore,
    validate_token_format, password_strength, mask_sensitive, rate_limit_key,
    session_expired, sanitize_header, permission_check, ip_in_allowlist, hash_password,
};
use tensorforge::statistics::{
    generate_heatmap, mean, median, moving_average, stddev, variance, HeatmapEvent,
    ResponseTimeTracker, weighted_mean, exponential_moving_average,
    min_max_normalize, covariance, sum_of_squares, interquartile_range,
    rate_of_change, z_score,
};
use tensorforge::workflow::{
    allowed_transitions, is_terminal_state, is_valid_state, shortest_path, WorkflowEngine,
    transition_count, time_in_state, parallel_workflows, state_distribution,
    bottleneck_state, workflow_complete_percentage, can_cancel,
    estimated_completion, state_age_seconds, batch_register, valid_path,
    entity_throughput, chain_length, merge_histories, TransitionRecord,
};
use tensorforge::config::{
    validate_config, merge_configs, build_connection_string, parse_feature_flags,
    is_production, config_priority, ServiceConfig,
};
use tensorforge::concurrency::{
    partition_by_threshold, compare_and_swap, fan_out_merge, detect_cycle,
    work_stealing, AtomicCounter, SharedRegistry,
};
use tensorforge::events::{
    filter_time_window, count_by_kind, EventLog, detect_gaps, batch_events,
    event_rate, TimedEvent,
};
use tensorforge::telemetry::{
    latency_bucket, throughput, is_within_threshold, aggregate_metrics,
    uptime_percentage, format_metric, metric_names, MetricSample, MetricsCollector,
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

#[test]
fn allocator_weighted() {
    let result = weighted_allocate(
        &[("a".into(), 5, 2.0), ("b".into(), 3, 4.0), ("c".into(), 10, 1.0)],
        2,
    );
    assert_eq!(result.len(), 2);
    // highest weighted score (urgency * weight) should come first
    // a: 5*2=10, b: 3*4=12, c: 10*1=10 — b should be first
    assert_eq!(result[0].0, "b");
}

#[test]
fn allocator_berth_utilization() {
    let slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 0, end_hour: 10, occupied: true, vessel_id: None },
        BerthSlot { berth_id: "B2".into(), start_hour: 0, end_hour: 10, occupied: false, vessel_id: None },
    ];
    let util = berth_utilization(&slots);
    assert!((util - 0.5).abs() < 0.01);
}

#[test]
fn allocator_rounding() {
    assert_eq!(round_allocation(3.7), 4);
    assert_eq!(round_allocation(3.2), 3);
    assert_eq!(round_allocation(3.5), 4);
}

#[test]
fn allocator_cost_per_unit() {
    let cpu = cost_per_unit(100.0, 4);
    assert!((cpu - 25.0).abs() < 0.01);
    assert_eq!(cost_per_unit(100.0, 0), 0.0);
}

#[test]
fn allocator_normalize_urgency() {
    let n = normalize_urgency(50.0, 100.0);
    assert!((n - 0.5).abs() < 0.01);
    assert!(normalize_urgency(150.0, 100.0) <= 1.0);
}

#[test]
fn allocator_priority_score() {
    // ceiling(7 / 3) = 3
    assert_eq!(priority_score(7, 3), 3);
    assert_eq!(priority_score(6, 3), 2);
}

#[test]
fn allocator_over_capacity() {
    assert!(is_over_capacity(10, 10));   // at capacity = over
    assert!(is_over_capacity(11, 10));   // above = over
    assert!(!is_over_capacity(9, 10));   // below = ok
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

#[test]
fn routing_weighted_score() {
    let s = weighted_route_score(10, 0.9, 2.0);
    // (0.9 * 2.0) / 10 = 0.18
    assert!((s - 0.18).abs() < 0.01);
}

#[test]
fn routing_best_route() {
    let routes = vec![
        Route { channel: "a".into(), latency: 10 },
        Route { channel: "b".into(), latency: 2 },
        Route { channel: "c".into(), latency: 5 },
    ];
    let best = best_route(&routes).unwrap();
    assert_eq!(best.channel, "b");  // lowest latency
}

#[test]
fn routing_failover() {
    let routes = vec![
        Route { channel: "primary".into(), latency: 5 },
        Route { channel: "backup".into(), latency: 10 },
    ];
    let failover = route_failover(&routes, "primary").unwrap();
    assert_eq!(failover.channel, "backup");
}

#[test]
fn routing_distance() {
    assert!((distance_between(10.0, 3.0) - 7.0).abs() < 0.01);
    assert!((distance_between(3.0, 10.0) - 7.0).abs() < 0.01);
}

#[test]
fn routing_normalize_latency() {
    let n = normalize_latency(5, 10);
    assert!((n - 0.5).abs() < 0.01);
}

#[test]
fn routing_fuel_efficiency() {
    let eff = fuel_efficiency(100.0, 20.0);
    // 100 / 20 = 5.0
    assert!((eff - 5.0).abs() < 0.01);
}

#[test]
fn routing_total_fees() {
    let fees = vec![100.0, 200.0, 300.0];
    assert!((total_port_fees(&fees) - 600.0).abs() < 0.01);
}

#[test]
fn routing_availability() {
    let r = Route { channel: "alpha".into(), latency: 5 };
    assert!(route_available(&r, &[]));
    assert!(!route_available(&r, &["alpha".to_string()]));
    let zero = Route { channel: "zero".into(), latency: 0 };
    assert!(!route_available(&zero, &[]));  // latency 0 = not available
}

#[test]
fn routing_knots_conversion() {
    let kmh = knots_to_kmh(10.0);
    // 10 * 1.852 = 18.52
    assert!((kmh - 18.52).abs() < 0.01);
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

#[test]
fn policy_weight_ordering() {
    // more restrictive = higher weight
    assert!(policy_weight("halted") > policy_weight("restricted"));
    assert!(policy_weight("restricted") > policy_weight("watch"));
    assert!(policy_weight("watch") > policy_weight("normal"));
}

#[test]
fn policy_escalation_threshold() {
    assert!(escalation_needed(0.6, 0.5));
    assert!(!escalation_needed(0.5, 0.5));  // exactly at threshold = NO escalation
    assert!(!escalation_needed(0.3, 0.5));
}

#[test]
fn policy_risk_score() {
    let r = risk_score(4.0, 0.5);
    // 4.0 * 0.5 = 2.0
    assert!((r - 2.0).abs() < 0.01);
}

#[test]
fn policy_grace_period() {
    assert!(within_grace_period(5, 10));
    assert!(within_grace_period(10, 10));  // exactly at threshold = still within
    assert!(!within_grace_period(11, 10));
}

#[test]
fn policy_retries_default() {
    assert_eq!(max_retries_for_policy("normal"), 3);
    assert_eq!(max_retries_for_policy("unknown_policy"), 1);
}

#[test]
fn policy_cooldown() {
    assert_eq!(cooldown_multiplier("normal"), 1);
    assert_eq!(cooldown_multiplier("watch"), 2);
    assert_eq!(cooldown_multiplier("restricted"), 4);
    assert_eq!(cooldown_multiplier("halted"), 8);
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

#[test]
fn queue_batch_enqueue() {
    let q = PriorityQueue::new(2);
    let count = batch_enqueue(&q, vec![
        QueueItem { id: "a".into(), priority: 1 },
        QueueItem { id: "b".into(), priority: 2 },
        QueueItem { id: "c".into(), priority: 3 },
    ]);
    // only 2 should succeed (hard_limit = 2)
    assert_eq!(count, 2);
}

#[test]
fn queue_priority_boost() {
    let item = QueueItem { id: "x".into(), priority: 5 };
    let boosted = priority_boost(&item, 3);
    assert_eq!(boosted.priority, 8);
}

#[test]
fn queue_fairness() {
    // equal allocations => fairness = 1.0
    let f = fairness_index(&[10.0, 10.0, 10.0]);
    assert!((f - 1.0).abs() < 0.01);
}

#[test]
fn queue_requeue() {
    let items = vec![
        ("a".into(), 5, 100u64),
        ("b".into(), 3, 200),
        ("c".into(), 7, 300),
    ];
    let (expired, active) = requeue_expired(&items, 150);
    assert_eq!(expired.len(), 1);   // "a" at ts=100 is <= 150
    assert_eq!(active.len(), 2);    // "b" and "c" are > 150
    assert_eq!(expired[0].0, "a");
}

#[test]
fn queue_weighted_wait() {
    let wt = weighted_wait_time(10, 2.0, 3.0);
    // (10/2) * 3 = 15
    assert!((wt - 15.0).abs() < 0.01);
}

#[test]
fn queue_pressure_ratio() {
    let p = queue_pressure(12, 10);
    assert!((p - 1.0).abs() < 0.01);  // clamped to 1.0
    let p2 = queue_pressure(5, 10);
    assert!((p2 - 0.5).abs() < 0.01);
}

#[test]
fn queue_drain_pct() {
    let pct = drain_percentage(25, 100);
    assert!((pct - 25.0).abs() < 0.01);
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
    assert!(is_allowed_origin("https://tensorforge.internal"));
    assert!(!is_allowed_origin("https://evil.com"));
}

#[test]
fn security_token_format() {
    assert!(validate_token_format("abc123"));
    assert!(!validate_token_format(""));
}

#[test]
fn security_password_strength() {
    assert_eq!(password_strength("ab"), "weak");
    assert_eq!(password_strength("abcdefgh"), "medium");  // exactly 8 chars = medium
    assert_eq!(password_strength("abcdefghijklmnopqr"), "strong");
}

#[test]
fn security_masking() {
    let masked = mask_sensitive("abcdefgh");
    // should show last 4 chars, mask rest
    assert!(masked.ends_with("efgh"));
    assert!(masked.starts_with("****"));
}

#[test]
fn security_rate_limit_key() {
    let key = rate_limit_key("192.168.1.1", "/api/orders");
    assert!(key.contains("192.168.1.1"));
    assert!(key.contains("/api/orders"));
}

#[test]
fn security_session_expiry() {
    assert!(!session_expired(1000, 300, 1200));  // 1200 < 1000+300=1300 => not expired
    assert!(session_expired(1000, 300, 1400));   // 1400 > 1300 => expired
}

#[test]
fn security_header_sanitize() {
    let clean = sanitize_header("X-Custom: value\r\ninjected");
    assert!(!clean.contains('\n'));
    assert!(!clean.contains('\r'));
}

#[test]
fn security_permissions() {
    assert!(permission_check(&["read", "write"], &["read", "write", "admin"]));
    assert!(!permission_check(&["read", "write"], &["read"]));  // missing "write"
}

#[test]
fn security_ip_allowlist() {
    assert!(ip_in_allowlist("10.0.0.1", &["10.0.0.1", "10.0.0.2"]));
    assert!(!ip_in_allowlist("10.0.0.3", &["10.0.0.1", "10.0.0.2"]));
    assert!(!ip_in_allowlist("10.0.0.10", &["10.0.0.1"]));  // should NOT match prefix
}

#[test]
fn security_password_hash_salt_order() {
    let h1 = hash_password("pass", "salt1");
    let h2 = hash_password("pass", "salt2");
    assert_ne!(h1, h2);  // different salts => different hashes
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

#[test]
fn resilience_replay_window() {
    let events = vec![
        Event { id: "a".into(), sequence: 1 },
        Event { id: "b".into(), sequence: 5 },
        Event { id: "c".into(), sequence: 10 },
        Event { id: "d".into(), sequence: 15 },
    ];
    let windowed = replay_window(&events, 5, 10);
    assert_eq!(windowed.len(), 2);  // b (5) and c (10)
}

#[test]
fn resilience_event_ordering() {
    let events = vec![
        Event { id: "b".into(), sequence: 5 },
        Event { id: "a".into(), sequence: 1 },
        Event { id: "c".into(), sequence: 3 },
    ];
    let ordered = event_ordering(&events);
    assert_eq!(ordered[0].sequence, 1);
    assert_eq!(ordered[1].sequence, 3);
    assert_eq!(ordered[2].sequence, 5);
}

#[test]
fn resilience_idempotent() {
    let events = vec![
        Event { id: "a".into(), sequence: 1 },
        Event { id: "b".into(), sequence: 2 },
        Event { id: "c".into(), sequence: 3 },
    ];
    let result = idempotent_apply(&events, &[1, 3]);
    assert_eq!(result.len(), 1);  // only sequence 2 not yet applied
}

#[test]
fn resilience_half_open_calls() {
    assert_eq!(half_open_max_calls(3), 3);
    assert_eq!(half_open_max_calls(1), 1);
}

#[test]
fn resilience_failure_window() {
    assert!(failure_window_expired(100, 500, 200));   // 400ms elapsed > 200ms window
    assert!(!failure_window_expired(100, 200, 200));  // 100ms elapsed < 200ms window
}

#[test]
fn resilience_checkpoint_interval() {
    assert!(!checkpoint_interval_ok(150, 100, 100));  // 50 < 100 = within interval
    assert!(checkpoint_interval_ok(250, 100, 100));   // 150 >= 100 = exceeded
}

#[test]
fn resilience_degradation() {
    assert_eq!(degradation_level(0.8), "critical");
    assert_eq!(degradation_level(0.6), "degraded");
    assert_eq!(degradation_level(0.3), "warning");
    assert_eq!(degradation_level(0.1), "minor");
    assert_eq!(degradation_level(0.0), "healthy");
}

#[test]
fn resilience_bulkhead() {
    assert!(bulkhead_permits_available(3, 5));
    assert!(!bulkhead_permits_available(5, 5));  // at max = no permits
}

#[test]
fn resilience_state_duration() {
    let d = circuit_state_duration(100, 500);
    assert_eq!(d, 400);  // raw difference
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

#[test]
fn stats_weighted_mean() {
    let wm = weighted_mean(&[10.0, 20.0, 30.0], &[1.0, 2.0, 3.0]);
    // (10*1 + 20*2 + 30*3) / (1+2+3) = 140/6 = 23.33
    assert!((wm - 23.333).abs() < 0.01);
}

#[test]
fn stats_ema() {
    let ema = exponential_moving_average(10.0, 20.0, 0.5);
    // 0.5 * 20 + 0.5 * 10 = 15
    assert!((ema - 15.0).abs() < 0.01);
}

#[test]
fn stats_min_max_normalize() {
    let n = min_max_normalize(5.0, 0.0, 10.0);
    assert!((n - 0.5).abs() < 0.01);
}

#[test]
fn stats_sum_of_squares() {
    let ss = sum_of_squares(&[1.0, 2.0, 3.0]);
    // 1 + 4 + 9 = 14
    assert!((ss - 14.0).abs() < 0.01);
}

#[test]
fn stats_iqr() {
    let iqr = interquartile_range(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]);
    assert!(iqr > 0.0);  // Q3 > Q1, so IQR must be positive
}

#[test]
fn stats_rate_of_change() {
    let roc = rate_of_change(100.0, 150.0);
    // (150 - 100) / 100 = 0.5
    assert!((roc - 0.5).abs() < 0.01);
}

#[test]
fn stats_z_score() {
    let z = z_score(80.0, 70.0, 5.0);
    // (80 - 70) / 5 = 2.0
    assert!((z - 2.0).abs() < 0.01);
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

#[test]
fn workflow_transition_count() {
    let history = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 1 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: 2 },
        TransitionRecord { entity_id: "e2".into(), from: "queued".into(), to: "allocated".into(), timestamp: 3 },
    ];
    assert_eq!(transition_count(&history, "e1"), 2);
}

#[test]
fn workflow_time_in_state() {
    let history = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 100 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: 300 },
    ];
    let time = time_in_state(&history, "allocated").unwrap();
    assert_eq!(time, 200);  // exited at 300, entered at 100
}

#[test]
fn workflow_parallel_count() {
    let mut entities = std::collections::HashMap::new();
    entities.insert("e1".to_string(), "queued".to_string());
    entities.insert("e2".to_string(), "allocated".to_string());
    entities.insert("e3".to_string(), "arrived".to_string());
    assert_eq!(parallel_workflows(&entities), 2);  // queued + allocated = 2 active
}

#[test]
fn workflow_state_distribution() {
    let mut entities = std::collections::HashMap::new();
    entities.insert("e1".to_string(), "queued".to_string());
    entities.insert("e2".to_string(), "queued".to_string());
    entities.insert("e3".to_string(), "arrived".to_string());
    let dist = state_distribution(&entities);
    assert_eq!(*dist.get("queued").unwrap(), 2);
    assert_eq!(*dist.get("arrived").unwrap(), 1);
    // states with 0 entities should NOT be in the map
    assert!(!dist.contains_key("departed"));
}

#[test]
fn workflow_bottleneck() {
    let mut entities = std::collections::HashMap::new();
    entities.insert("e1".to_string(), "allocated".to_string());
    entities.insert("e2".to_string(), "allocated".to_string());
    entities.insert("e3".to_string(), "queued".to_string());
    assert_eq!(bottleneck_state(&entities).unwrap(), "allocated");
}

#[test]
fn workflow_completion_pct() {
    let mut entities = std::collections::HashMap::new();
    entities.insert("e1".to_string(), "arrived".to_string());
    entities.insert("e2".to_string(), "arrived".to_string());
    entities.insert("e3".to_string(), "queued".to_string());
    let pct = workflow_complete_percentage(&entities);
    // 2 of 3 complete = 66.67%
    assert!((pct - 66.67).abs() < 0.1);
}

#[test]
fn workflow_cancel_from_any_active() {
    assert!(can_cancel("queued"));
    assert!(can_cancel("allocated"));
    assert!(can_cancel("departed"));
    assert!(!can_cancel("arrived"));   // terminal
    assert!(!can_cancel("cancelled")); // terminal
}

#[test]
fn workflow_estimated_completion() {
    let est = estimated_completion("queued", 10.0);
    // queued -> allocated -> departed -> arrived = 3 transitions
    assert!((est - 30.0).abs() < 0.01);
}

#[test]
fn workflow_state_age() {
    let age = state_age_seconds(100, 500);
    assert_eq!(age, 400);
}

#[test]
fn workflow_batch_register() {
    let engine = WorkflowEngine::new();
    let count = batch_register(&engine, &["e1", "e2", "e3"]);
    assert_eq!(count, 3);
}

#[test]
fn workflow_valid_path() {
    assert!(valid_path(&["queued", "allocated", "departed", "arrived"]));
    assert!(!valid_path(&["queued", "departed"]));  // invalid transition
}

#[test]
fn workflow_throughput() {
    let tp = entity_throughput(360, 3600);
    // 360 / (3600/3600) = 360 per hour
    assert!((tp - 360.0).abs() < 0.01);
}

#[test]
fn workflow_chain_length() {
    let history = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 1 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: 2 },
        TransitionRecord { entity_id: "e2".into(), from: "queued".into(), to: "allocated".into(), timestamp: 3 },
    ];
    assert_eq!(chain_length(&history, "e1"), 2);
}

#[test]
fn workflow_merge_histories() {
    let a = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 100 },
    ];
    let b = vec![
        TransitionRecord { entity_id: "e2".into(), from: "queued".into(), to: "allocated".into(), timestamp: 50 },
    ];
    let merged = merge_histories(&a, &b);
    assert_eq!(merged.len(), 2);
    // Should be sorted by timestamp
    assert!(merged[0].timestamp <= merged[1].timestamp);
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

#[test]
fn model_severity_label() {
    assert_eq!(severity_label(5), "critical");
    assert_eq!(severity_label(4), "high");
    assert_eq!(severity_label(3), "medium");
    assert_eq!(severity_label(1), "info");
}

#[test]
fn model_weight_class() {
    assert_eq!(weight_class(100_000.0), "heavy");    // exactly 100k = heavy, not super-heavy
    assert_eq!(weight_class(100_001.0), "super-heavy");
    assert_eq!(weight_class(55_000.0), "heavy");
    assert_eq!(weight_class(5_000.0), "light");
}

#[test]
fn model_crew_estimation() {
    assert_eq!(estimated_crew(250), 3);   // ceil(250/100) = 3
    assert_eq!(estimated_crew(100), 1);   // ceil(100/100) = 1
    assert_eq!(estimated_crew(0), 1);     // minimum 1
}

#[test]
fn model_order_priority() {
    let a = DispatchOrder { id: "a".into(), severity: 5, sla_minutes: 15 };
    let b = DispatchOrder { id: "b".into(), severity: 3, sla_minutes: 60 };
    let ord = order_priority_compare(&a, &b);
    assert_eq!(ord, std::cmp::Ordering::Greater);  // a has higher urgency, should come first (descending)
}

#[test]
fn model_total_cargo() {
    let manifests = vec![
        VesselManifest { vessel_id: "v1".into(), name: "A".into(), cargo_tons: 1000.0, containers: 100, hazmat: false },
        VesselManifest { vessel_id: "v2".into(), name: "B".into(), cargo_tons: 2000.0, containers: 200, hazmat: false },
    ];
    assert!((total_cargo(&manifests) - 3000.0).abs() < 0.01);
}

#[test]
fn model_hazmat_surcharge() {
    assert!((hazmat_surcharge(100.0, true) - 250.0).abs() < 0.01);
    assert!((hazmat_surcharge(100.0, false) - 100.0).abs() < 0.01);
}

#[test]
fn model_eta() {
    let eta = eta_minutes(60.0, 10.0);
    // 60nm / 10kt = 6 hours = 360 minutes
    assert!((eta - 360.0).abs() < 0.01);
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

// ---- Config extended ----

#[test]
fn config_validate() {
    let cfg = ServiceConfig::new("test");
    assert!(validate_config(&cfg).is_ok());
    let bad = ServiceConfig { name: "".into(), port: 0, timeout_ms: 1000, max_retries: 1, region: "us".into(), pool_size: 1 };
    assert!(validate_config(&bad).is_err());
}

#[test]
fn config_merge() {
    let base = ServiceConfig::new("test");
    let mut overrides = std::collections::HashMap::new();
    overrides.insert("port".to_string(), "9090".to_string());
    overrides.insert("region".to_string(), "ap-east-1".to_string());
    let merged = merge_configs(&base, &overrides);
    assert_eq!(merged.port, 9090);
    assert_eq!(merged.region, "ap-east-1");
}

#[test]
fn config_connection_string() {
    let cs = build_connection_string("localhost", 5432, "tensorforge");
    assert_eq!(cs, "postgres://localhost:5432/tensorforge");
}

#[test]
fn config_feature_flags() {
    let flags = parse_feature_flags("alpha, beta, gamma");
    assert_eq!(flags, vec!["alpha", "beta", "gamma"]);
    assert!(parse_feature_flags("").is_empty());
}

#[test]
fn config_env_detection() {
    assert!(is_production("production"));
    assert!(is_production("prod"));
    assert!(!is_production("staging"));
}

#[test]
fn config_priority_ordering() {
    assert!(config_priority("production") > config_priority("staging"));
    assert!(config_priority("staging") > config_priority("dev"));
}

// ---- Concurrency extended ----

#[test]
fn concurrency_partition() {
    let (below, above) = partition_by_threshold(&[1, 5, 3, 7, 5, 9], 5);
    assert_eq!(below, vec![1, 3]);
    assert!(above.contains(&5));  // 5 should be in the at-or-above partition
    assert!(above.contains(&7));
    assert!(above.contains(&9));
}

#[test]
fn concurrency_registry() {
    let reg = SharedRegistry::new();
    reg.register("svc-a".into(), "active".into());
    reg.register("svc-b".into(), "active".into());
    assert_eq!(reg.count(), 2);
    assert_eq!(reg.lookup("svc-a"), Some("active".to_string()));
    reg.remove("svc-a");
    assert_eq!(reg.count(), 1);
}

#[test]
fn concurrency_fan_out_merge() {
    let partitions = vec![
        vec![("c".into(), 3), ("a".into(), 1)],
        vec![("b".into(), 2)],
    ];
    let merged = fan_out_merge(&partitions);
    // should be sorted by key
    assert_eq!(merged[0].0, "a");
    assert_eq!(merged[1].0, "b");
    assert_eq!(merged[2].0, "c");
}

#[test]
fn concurrency_cycle_detection() {
    // a->b, b->c, c->a = cycle
    assert!(detect_cycle(&[(0, 1), (1, 2), (2, 0)], 3));
    // a->b, b->c = no cycle
    assert!(!detect_cycle(&[(0, 1), (1, 2)], 3));
}

#[test]
fn concurrency_work_stealing() {
    let mut queues = vec![
        vec![1, 2, 3, 4, 5],
        vec![],
    ];
    let stolen = work_stealing(&mut queues, 1);
    assert!(stolen.is_some());
    let val = stolen.unwrap();
    assert_eq!(val, 5);  // should steal from back
    assert_eq!(queues[0].len(), 4);
}

// ---- Events extended ----

#[test]
fn events_time_window() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 200, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 300, kind: "A".into(), payload: "".into() },
    ];
    let windowed = filter_time_window(&events, 100, 300);
    assert_eq!(windowed.len(), 3);  // inclusive on both ends: 100, 200, 300
}

#[test]
fn events_count_by_kind() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 1, kind: "dispatch".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 2, kind: "dispatch".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 3, kind: "route".into(), payload: "".into() },
    ];
    let counts = count_by_kind(&events);
    assert_eq!(*counts.get("dispatch").unwrap(), 2);
    assert_eq!(*counts.get("route").unwrap(), 1);
}

#[test]
fn events_log_eviction() {
    let log = EventLog::new(2);
    log.append(TimedEvent { id: "e1".into(), timestamp: 1, kind: "A".into(), payload: "".into() });
    log.append(TimedEvent { id: "e2".into(), timestamp: 2, kind: "A".into(), payload: "".into() });
    log.append(TimedEvent { id: "e3".into(), timestamp: 3, kind: "A".into(), payload: "".into() });
    assert_eq!(log.count(), 2);
    let all = log.get_all();
    assert_eq!(all[0].id, "e2");  // e1 should be evicted (oldest)
}

#[test]
fn events_gap_detection() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 200, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 500, kind: "A".into(), payload: "".into() },
    ];
    let gaps = detect_gaps(&events, 200);
    assert_eq!(gaps.len(), 1);  // gap of 300 between 200 and 500 (> 200 threshold)
    // gap of exactly 100 between 100-200 should NOT be detected (100 is not > 200)
}

#[test]
fn events_batch_by_time() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 0, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 5, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 10, kind: "A".into(), payload: "".into() },
    ];
    let batches = batch_events(&events, 10);
    // ts 0 -> bucket 0, ts 5 -> bucket 0, ts 10 -> bucket 1
    assert!(batches.contains_key(&0));
    assert_eq!(batches.get(&0).unwrap().len(), 2);
}

#[test]
fn events_rate() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 200, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 300, kind: "A".into(), payload: "".into() },
    ];
    let r = event_rate(&events);
    // 3 events over 200 units = 0.015
    assert!((r - 0.015).abs() < 0.001);
}

// ---- Telemetry extended ----

#[test]
fn telemetry_latency_bucket() {
    assert_eq!(latency_bucket(5), "fast");
    assert_eq!(latency_bucket(10), "fast");  // <= 10
    assert_eq!(latency_bucket(50), "medium");
    assert_eq!(latency_bucket(100), "slow");  // exactly 100 = slow (< 100 is medium)
    assert_eq!(latency_bucket(200), "slow");
}

#[test]
fn telemetry_throughput() {
    let tp = throughput(1000, 2000);
    // 1000 / (2000ms / 1000) = 1000 / 2.0 = 500 per second
    assert!((tp - 500.0).abs() < 0.01);
}

#[test]
fn telemetry_threshold_check() {
    assert!(is_within_threshold(9.5, 10.0, 1.0));
    assert!(!is_within_threshold(8.0, 10.0, 1.0));
}

#[test]
fn telemetry_aggregate() {
    let samples = vec![
        MetricSample { name: "cpu".into(), value: 50.0, timestamp: 1 },
        MetricSample { name: "cpu".into(), value: 70.0, timestamp: 2 },
        MetricSample { name: "mem".into(), value: 80.0, timestamp: 1 },
    ];
    let agg = aggregate_metrics(&samples);
    // cpu average: (50+70)/2 = 60
    assert!((*agg.get("cpu").unwrap() - 60.0).abs() < 0.01);
    assert!((*agg.get("mem").unwrap() - 80.0).abs() < 0.01);
}

#[test]
fn telemetry_uptime() {
    let uptime = uptime_percentage(1000, 100);
    // (1000 - 100) / 1000 * 100 = 90%
    assert!((uptime - 90.0).abs() < 0.01);
}

#[test]
fn telemetry_format_metric() {
    assert_eq!(format_metric("cpu", 75.5, "%"), "cpu=75.50%");
}

#[test]
fn telemetry_metric_names() {
    let samples = vec![
        MetricSample { name: "cpu".into(), value: 1.0, timestamp: 1 },
        MetricSample { name: "mem".into(), value: 2.0, timestamp: 2 },
        MetricSample { name: "cpu".into(), value: 3.0, timestamp: 3 },
    ];
    let names = metric_names(&samples);
    assert_eq!(names, vec!["cpu", "mem"]);
}

// ---- Integration ----

#[test]
fn end_to_end_dispatch() {
    use tensorforge::allocator::allocate_orders;
    use tensorforge::routing::{choose_route, Route};
    use tensorforge::policy::next_policy;
    use tensorforge::workflow::can_transition;
    use tensorforge::security::digest;

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
