use tensorforge::allocator::{allocate_orders, dispatch_batch, estimate_cost, validate_order,
    weighted_allocate, round_allocation, cost_per_unit, normalize_urgency, is_over_capacity,
    demand_spike, berth_schedule_conflict_window, BerthSlot};
use tensorforge::models::{DispatchOrder, severity_label, weight_class, estimated_crew,
    hazmat_surcharge, eta_minutes, effective_sla, time_adjusted_urgency};
use tensorforge::policy::{check_sla_compliance, next_policy, previous_policy,
    policy_weight, escalation_needed, risk_score, within_grace_period, cooldown_multiplier,
    aggregate_risk, escalation_with_cooldown};
use tensorforge::queue::{estimate_wait_time, queue_health, should_shed,
    priority_boost, queue_pressure, drain_percentage, QueueItem};
use tensorforge::resilience::{deduplicate, replay, replay_converges, Event,
    replay_window, event_ordering, retry_delay, should_trip, recovery_rate,
    degradation_level, bulkhead_permits_available, cascade_failure_check,
    health_quorum, process_replay_batch};
use tensorforge::routing::{channel_score, choose_route, estimate_transit_time, Route,
    best_route, distance_between, fuel_efficiency, total_port_fees, knots_to_kmh,
    route_reliability, congestion_adjusted_latency};
use tensorforge::security::{digest, sanitise_path, sign_manifest, verify_manifest, verify_signature,
    validate_token_format, password_strength, mask_sensitive, rate_limit_key,
    session_expired, permission_check, ip_in_allowlist, token_needs_refresh};
use tensorforge::statistics::{mean, moving_average, percentile,
    weighted_mean, exponential_moving_average, min_max_normalize,
    sum_of_squares, rate_of_change, z_score, cumulative_sum, running_variance, detect_trend};
use tensorforge::workflow::{can_transition, is_terminal_state, shortest_path,
    can_cancel, estimated_completion, state_age_seconds, valid_path,
    entity_throughput, reachable_from, can_resume, compact_history, TransitionRecord};
use tensorforge::contracts::get_service_url;
use tensorforge::config::{default_region, default_pool_size, validate_endpoint,
    normalize_env_name, is_production, config_priority};
use tensorforge::concurrency::{barrier_reached, merge_counts, partition_by_threshold,
    detect_cycle, AtomicCounter, parallel_sum};
use tensorforge::events::{sort_events_by_time, dedup_by_id, filter_time_window,
    count_by_kind, detect_gaps, batch_events, event_rate, merge_event_streams, TimedEvent,
    correlate_workflow_events};
use tensorforge::telemetry::{error_rate, latency_bucket, throughput, health_score,
    is_within_threshold, uptime_percentage, should_alert, alert_priority};

const TOTAL_CASES: usize = 12500;

fn run_case(idx: usize) -> bool {
    let severity_a = (idx % 7) as i32 + 1;
    let severity_b = ((idx * 3) % 7) as i32 + 1;
    let sla_a = (20 + (idx % 90)) as i32;
    let sla_b = (20 + ((idx * 2) % 90)) as i32;

    let order_a = DispatchOrder { id: format!("a-{idx}"), severity: severity_a, sla_minutes: sla_a };
    let order_b = DispatchOrder { id: format!("b-{idx}"), severity: severity_b, sla_minutes: sla_b };

    let planned = allocate_orders(
        vec![
            (order_a.id.clone(), order_a.urgency_score(), format!("0{}:1{}", idx % 9, idx % 6).parse::<i32>().unwrap_or(0)),
            (order_b.id.clone(), order_b.urgency_score(), format!("0{}:2{}", (idx + 3) % 9, idx % 6).parse::<i32>().unwrap_or(0)),
            (format!("c-{idx}"), (idx % 50) as i32 + 2, (40 + (idx % 30)) as i32),
        ],
        2,
    );

    if planned.is_empty() || planned.len() > 2 {
        return false;
    }
    if planned.len() == 2 && planned[0].1 < planned[1].1 {
        return false;
    }

    // Validate order tuples
    for p in &planned {
        if validate_order(p).is_err() {
            return false;
        }
    }

    // Dispatch batch check
    let batch = dispatch_batch(
        vec![("x".into(), 10, 1), ("y".into(), 5, 2)],
        1,
    );
    if batch.planned.len() != 1 || batch.rejected.len() != 1 {
        return false;
    }

    let mut blocked = Vec::new();
    if idx % 5 == 0 {
        blocked.push("beta".to_string());
    }

    let route = choose_route(
        &[
            Route { channel: "alpha".to_string(), latency: 2 + (idx % 9) as i32 },
            Route { channel: "beta".to_string(), latency: (idx % 3) as i32 },
            Route { channel: "gamma".to_string(), latency: 4 + (idx % 4) as i32 },
        ],
        &blocked,
    );

    if route.is_none() {
        return false;
    }
    if blocked.iter().any(|v| v == "beta") && route.as_ref().is_some_and(|r| r.channel == "beta") {
        return false;
    }

    // Channel score and transit time
    let cs = channel_score(5, 0.9, 8);
    if cs <= 0.0 {
        return false;
    }
    let tt = estimate_transit_time(100.0, 20.0);
    if (tt - 5.0).abs() > 0.01 {
        return false;
    }

    let (src, dst) = if idx % 2 == 0 { ("queued", "allocated") } else { ("allocated", "departed") };
    if !can_transition(src, dst) || can_transition("arrived", "queued") {
        return false;
    }

    // Shortest path and terminal state checks
    if shortest_path("queued", "arrived").is_none() {
        return false;
    }
    if !is_terminal_state("arrived") || is_terminal_state("queued") {
        return false;
    }

    let pol = next_policy(if idx % 2 == 0 { "normal" } else { "watch" }, 2 + (idx % 2));
    if pol != "watch" && pol != "restricted" && pol != "halted" {
        return false;
    }

    // De-escalation and SLA
    let prev = previous_policy(pol);
    if prev.is_empty() {
        return false;
    }
    if !check_sla_compliance(30, 60) || check_sla_compliance(90, 60) {
        return false;
    }

    let depth = (idx % 30) + 1;
    if should_shed(depth, 40, false) || !should_shed(41, 40, false) {
        return false;
    }

    // Queue health and wait time
    let health = queue_health(depth, 40);
    if health.status.is_empty() {
        return false;
    }
    let wt = estimate_wait_time(10, 2.0);
    if (wt - 5.0).abs() > 0.01 {
        return false;
    }

    let replayed = replay(&[
        Event { id: format!("k-{}", idx % 17), sequence: 1 },
        Event { id: format!("k-{}", idx % 17), sequence: 2 },
        Event { id: format!("z-{}", idx % 13), sequence: 1 },
    ]);

    if replayed.len() < 2 {
        return false;
    }

    // Deduplicate and convergence
    let deduped = deduplicate(&[
        Event { id: "d1".into(), sequence: 1 },
        Event { id: "d1".into(), sequence: 2 },
    ]);
    if deduped.len() != 1 {
        return false;
    }
    if !replay_converges(
        &[Event { id: "r".into(), sequence: 1 }, Event { id: "r".into(), sequence: 2 }],
        &[Event { id: "r".into(), sequence: 2 }, Event { id: "r".into(), sequence: 1 }],
    ) {
        return false;
    }

    let p50 = percentile(&[(idx % 11) as i32, ((idx * 7) % 11) as i32, ((idx * 5) % 11) as i32, ((idx * 3) % 11) as i32], 50);
    if p50 < 0 {
        return false;
    }

    // Mean and moving average
    let m = mean(&[1.0, 2.0, 3.0]);
    if (m - 2.0).abs() > 0.01 {
        return false;
    }
    let ma = moving_average(&[1.0, 2.0, 3.0, 4.0], 2);
    if ma.len() != 3 {
        return false;
    }

    if idx % 17 == 0 {
        let payload = format!("manifest:{idx}");
        let sig = digest(&payload);
        if !verify_signature(&payload, &sig, &sig) {
            return false;
        }
        if verify_signature(&payload, &sig[1..], &sig) {
            return false;
        }
        // Manifest signing
        let msig = sign_manifest(&payload, "key");
        if !verify_manifest(&payload, "key", &msig) {
            return false;
        }
        // Path sanitisation
        let clean = sanitise_path("../../etc/passwd");
        if clean.contains("..") {
            return false;
        }
    }

    // Cost estimation
    let cost = estimate_cost(severity_a, sla_a, 10.0);
    if cost < 0.0 {
        return false;
    }

    // Service URL resolution
    if get_service_url("gateway").is_none() {
        return false;
    }

    // ---- New module checks ----

    // Config checks
    if default_region() != "us-east-1" {
        return false;
    }
    if default_pool_size() != 32 {
        return false;
    }
    if !validate_endpoint("http://localhost:8080") {
        return false;
    }
    if validate_endpoint("ftp://bad") {
        return false;
    }
    if normalize_env_name("Production") != "production" {
        return false;
    }

    // Concurrency checks
    if !barrier_reached(5, 5) {
        return false;
    }
    if barrier_reached(4, 5) {
        return false;
    }

    // Partition check
    let (below, above) = partition_by_threshold(&[1, 5, 3, 7], 5);
    if below.len() != 2 || !above.contains(&5) {
        return false;
    }

    // Events checks
    let timed_events = vec![
        TimedEvent { id: "t1".into(), timestamp: 300, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "t2".into(), timestamp: 100, kind: "B".into(), payload: "".into() },
    ];
    let sorted_events = sort_events_by_time(&timed_events);
    if sorted_events[0].timestamp != 100 {
        return false;
    }

    // Telemetry checks
    let err_rate = error_rate(100, 5);
    if (err_rate - 0.05).abs() > 0.01 {
        return false;
    }
    let hs = health_score(1.0, 0.5);
    if (hs - 0.8).abs() > 0.01 {
        return false;
    }
    if !should_alert(95.0, 90.0) || should_alert(80.0, 90.0) {
        return false;
    }

    // New allocator checks
    let wa = weighted_allocate(&[("a".into(), 5, 2.0), ("b".into(), 3, 4.0)], 1);
    if wa.is_empty() {
        return false;
    }
    if round_allocation(3.7) != 4 || round_allocation(3.2) != 3 {
        return false;
    }
    let cpu = cost_per_unit(100.0, 4);
    if (cpu - 25.0).abs() > 0.01 {
        return false;
    }
    let nu = normalize_urgency(50.0, 100.0);
    if (nu - 0.5).abs() > 0.01 {
        return false;
    }
    if !is_over_capacity(10, 10) || is_over_capacity(9, 10) {
        return false;
    }

    // New model checks
    if severity_label(5) != "critical" {
        return false;
    }
    if weight_class(100_001.0) != "super-heavy" || weight_class(100_000.0) != "heavy" {
        return false;
    }
    if estimated_crew(250) != 3 {
        return false;
    }
    if (hazmat_surcharge(100.0, true) - 250.0).abs() > 0.01 {
        return false;
    }
    if (eta_minutes(60.0, 10.0) - 360.0).abs() > 0.01 {
        return false;
    }

    // New policy checks
    if policy_weight("halted") <= policy_weight("normal") {
        return false;
    }
    if escalation_needed(0.5, 0.5) {
        return false;
    }
    if (risk_score(4.0, 0.5) - 2.0).abs() > 0.01 {
        return false;
    }
    if !within_grace_period(10, 10) {
        return false;
    }
    if cooldown_multiplier("watch") != 2 {
        return false;
    }

    // New queue checks
    let boosted = priority_boost(&QueueItem { id: "x".into(), priority: 5 }, 3);
    if boosted.priority != 8 {
        return false;
    }
    let qp = queue_pressure(12, 10);
    if (qp - 1.0).abs() > 0.01 {
        return false;
    }
    let dp = drain_percentage(25, 100);
    if (dp - 25.0).abs() > 0.01 {
        return false;
    }

    // New resilience checks
    let rw = replay_window(
        &[Event { id: "a".into(), sequence: 5 }, Event { id: "b".into(), sequence: 15 }],
        5, 10,
    );
    if rw.len() != 1 {  // only sequence 5 is in [5,10]
        return false;
    }
    let eo = event_ordering(&[Event { id: "b".into(), sequence: 5 }, Event { id: "a".into(), sequence: 1 }]);
    if eo[0].sequence != 1 {
        return false;
    }
    if retry_delay(100, 2) != 400 {
        return false;
    }
    if !should_trip(8, 10, 0.5) {
        return false;
    }
    if (recovery_rate(8, 2) - 0.8).abs() > 0.01 {
        return false;
    }
    if degradation_level(0.1) != "minor" {
        return false;
    }
    if bulkhead_permits_available(5, 5) {
        return false;
    }
    if !cascade_failure_check(&[true, false, true]) {
        return false;
    }

    // New routing checks
    let br = best_route(&[Route { channel: "a".into(), latency: 10 }, Route { channel: "b".into(), latency: 2 }]);
    if br.unwrap().channel != "b" {
        return false;
    }
    if (distance_between(10.0, 3.0) - 7.0).abs() > 0.01 {
        return false;
    }
    if (fuel_efficiency(100.0, 20.0) - 5.0).abs() > 0.01 {
        return false;
    }
    if (total_port_fees(&[100.0, 200.0]) - 300.0).abs() > 0.01 {
        return false;
    }
    if (knots_to_kmh(10.0) - 18.52).abs() > 0.01 {
        return false;
    }

    // New security checks
    if !validate_token_format("abc123") || validate_token_format("") {
        return false;
    }
    if password_strength("abcdefgh") != "medium" {
        return false;
    }
    if !mask_sensitive("abcdefgh").ends_with("efgh") {
        return false;
    }
    if !rate_limit_key("192.168.1.1", "/api").contains("192.168.1.1") {
        return false;
    }
    if session_expired(1000, 300, 1200) {
        return false;
    }
    if !permission_check(&["read", "write"], &["read", "write", "admin"]) {
        return false;
    }
    if permission_check(&["read", "write"], &["read"]) {
        return false;
    }
    if ip_in_allowlist("10.0.0.10", &["10.0.0.1"]) {
        return false;
    }

    // New stats checks
    let wm = weighted_mean(&[10.0, 20.0, 30.0], &[1.0, 2.0, 3.0]);
    if (wm - 23.333).abs() > 0.01 {
        return false;
    }
    let ema = exponential_moving_average(10.0, 20.0, 0.5);
    if (ema - 15.0).abs() > 0.01 {
        return false;
    }
    let nmm = min_max_normalize(5.0, 0.0, 10.0);
    if (nmm - 0.5).abs() > 0.01 {
        return false;
    }
    let ss = sum_of_squares(&[1.0, 2.0, 3.0]);
    if (ss - 14.0).abs() > 0.01 {
        return false;
    }
    let roc = rate_of_change(100.0, 150.0);
    if (roc - 0.5).abs() > 0.01 {
        return false;
    }
    let z = z_score(80.0, 70.0, 5.0);
    if (z - 2.0).abs() > 0.01 {
        return false;
    }

    // New workflow checks
    if !can_cancel("allocated") || can_cancel("arrived") {
        return false;
    }
    let ec = estimated_completion("queued", 10.0);
    if (ec - 30.0).abs() > 0.01 {
        return false;
    }
    if state_age_seconds(100, 500) != 400 {
        return false;
    }
    if !valid_path(&["queued", "allocated", "departed", "arrived"]) {
        return false;
    }
    let tp = entity_throughput(360, 3600);
    if (tp - 360.0).abs() > 0.01 {
        return false;
    }

    // Event extended checks
    let tw = filter_time_window(&timed_events, 100, 300);
    if tw.len() != 2 {
        return false;
    }
    let ck = count_by_kind(&timed_events);
    if *ck.get("A").unwrap_or(&0) != 1 || *ck.get("B").unwrap_or(&0) != 1 {
        return false;
    }

    // Telemetry extended checks
    if latency_bucket(100) != "slow" {
        return false;
    }
    let tput = throughput(1000, 2000);
    if (tput - 500.0).abs() > 0.01 {
        return false;
    }
    if !is_within_threshold(9.5, 10.0, 1.0) {
        return false;
    }
    let up = uptime_percentage(1000, 100);
    if (up - 90.0).abs() > 0.01 {
        return false;
    }

    // Reachable states check (state machine)
    let reachable = reachable_from("queued");
    if !reachable.contains(&"arrived".to_string()) {
        return false;
    }
    if !can_resume("queued") || can_resume("arrived") {
        return false;
    }

    // Parallel sum (concurrency)
    if parallel_sum(&[vec![1, 2], vec![3, 4]]) != 10 {
        return false;
    }

    // Route reliability (domain logic)
    if (route_reliability(8, 10) - 0.8).abs() > 0.01 {
        return false;
    }

    // Congestion adjusted latency (domain logic)
    if congestion_adjusted_latency(100, 0.5) != 150 {
        return false;
    }

    // Cumulative sum (latent)
    let cs = cumulative_sum(&[1.0, 2.0, 3.0]);
    if cs.len() != 3 || (cs[2] - 6.0).abs() > 0.01 {
        return false;
    }

    // Alert priority (integration)
    if alert_priority(95.0, 80.0, 90.0) != "critical" {
        return false;
    }

    // Demand spike detection (domain logic)
    if !demand_spike(150.0, 100.0, 25.0) || demand_spike(110.0, 100.0, 25.0) {
        return false;
    }

    // Health quorum (multi-step)
    if !health_quorum(&[true, true, true, false], 0.75) {
        return false;
    }

    // Aggregate risk (max-weighted aggregation, correct avg = 5.0, buggy = 4.5)
    if (aggregate_risk(&[(10.0, 0.8), (5.0, 0.4)]) - 5.0).abs() > 0.01 {
        return false;
    }

    // Token refresh timing (integration)
    if !token_needs_refresh(1000, 4400, 3600, 300) {
        return false;
    }
    if token_needs_refresh(1000, 4200, 3600, 300) {
        return false;
    }

    // Compact history (latent: keeps first instead of last per entity)
    let hist = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 1 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: 2 },
    ];
    let compacted = compact_history(&hist);
    if compacted.len() != 1 || compacted[0].to != "departed" {
        return false;
    }

    // Running variance (latent: uses window as divisor during warmup)
    let rv = running_variance(&[10.0, 20.0, 30.0], 5);
    // At i=1: slice=[10,20], len=2, buggy divisor=window(5)-1=4 → 12.5, correct=50.0
    if rv.len() != 3 || (rv[1] - 50.0).abs() > 0.01 {
        return false;
    }

    // Berth conflict with buffer (domain: asymmetric buffer - only departure side)
    let conflict_slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 10, end_hour: 14, occupied: true, vessel_id: None },
    ];
    if !berth_schedule_conflict_window(&conflict_slots, 14, 18, "B1", 2) {
        return false;
    }
    // Arrival-side buffer should also detect conflict but doesn't
    if !berth_schedule_conflict_window(&conflict_slots, 6, 10, "B1", 2) {
        return false;
    }

    // Effective SLA (domain: parallel redundancy instead of serial dependency)
    let sla = effective_sla(0.999, 0.999);
    if (sla - 0.998001).abs() > 0.0001 {
        return false;
    }

    // Time adjusted urgency (domain: decreases near deadline)
    let urg_start = time_adjusted_urgency(10.0, 0.0, 60.0);
    let urg_end = time_adjusted_urgency(10.0, 55.0, 60.0);
    if urg_end <= urg_start {
        return false;
    }

    // Process replay batch (multi-step: compensating bugs)
    let batch = process_replay_batch(&[
        Event { id: "a".into(), sequence: 3 },
        Event { id: "b".into(), sequence: 1 },
        Event { id: "c".into(), sequence: 2 },
    ]);
    if batch[0].sequence != 1 || batch[1].sequence != 2 {
        return false;
    }

    // Detect trend (multi-step: swapped labels + bugged EMA)
    if detect_trend(&[1.0, 2.0, 3.0, 4.0, 5.0], 0.3) != "rising" {
        return false;
    }

    // Correlate events (integration: looks after instead of before)
    let corr_events = vec![
        TimedEvent { id: "ce1".into(), timestamp: 90, kind: "A".into(), payload: "".into() },
    ];
    let correlated = correlate_workflow_events(&[100], &corr_events, 20);
    if correlated[0].is_empty() {
        return false;
    }

    // Escalation with cooldown (state machine: wrong cooldown check)
    let esc = escalation_with_cooldown("normal", 5, 900, 1000, 200);
    if esc != "normal" {
        return false;
    }

    true
}

#[test]
fn hyper_matrix_scenarios() {
    let mut passed = 0usize;
    let mut failed = 0usize;

    for idx in 0..TOTAL_CASES {
        if run_case(idx) {
            passed += 1;
        } else {
            failed += 1;
        }
    }

    println!("TB_SUMMARY total={} passed={} failed={}", TOTAL_CASES, passed, failed);
    assert_eq!(failed, 0, "hyper matrix had {} failing scenarios", failed);
}
