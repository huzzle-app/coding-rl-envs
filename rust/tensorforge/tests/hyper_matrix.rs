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
const NUM_GROUPS: usize = 14;
const GROUP_NAMES: [&str; NUM_GROUPS] = [
    "config", "concurrency", "events", "telemetry", "allocator", "models", "policy",
    "queue", "resilience", "routing", "security", "statistics", "workflow", "integration",
];

/// Group 0 - CONFIG: default_region, default_pool_size, validate_endpoint,
/// normalize_env_name, is_production, config_priority
fn check_config(idx: usize) -> bool {
    // Core config checks
    if default_region() != "us-east-1" {
        return false;
    }
    if default_pool_size() != 32 {
        return false;
    }

    // Vary the endpoint based on idx
    let endpoints = [
        "http://localhost:8080",
        "https://api.example.com",
        "http://service:3000/health",
        "https://internal.host:9090",
    ];
    let valid_ep = endpoints[idx % endpoints.len()];
    if !validate_endpoint(valid_ep) {
        return false;
    }

    // Invalid endpoints
    let bad_endpoints = ["ftp://bad", "ws://nope", "", "just-a-string"];
    let bad_ep = bad_endpoints[idx % bad_endpoints.len()];
    if validate_endpoint(bad_ep) {
        return false;
    }

    // normalize_env_name
    let env_names = ["Production", "STAGING", "Development", "Test"];
    let expected_lower = ["production", "staging", "development", "test"];
    let pick = idx % env_names.len();
    if normalize_env_name(env_names[pick]) != expected_lower[pick] {
        return false;
    }

    // is_production
    if !is_production("production") || !is_production("prod") {
        return false;
    }
    if is_production("staging") || is_production("development") {
        return false;
    }

    // config_priority varies by idx
    let envs = ["production", "staging", "development", "test", "unknown"];
    let expected_prio = [100, 75, 50, 25, 0];
    let ep = idx % envs.len();
    if config_priority(envs[ep]) != expected_prio[ep] {
        return false;
    }

    true
}

/// Group 1 - CONCURRENCY: barrier_reached, merge_counts, partition_by_threshold,
/// detect_cycle, AtomicCounter, parallel_sum
fn check_concurrency(idx: usize) -> bool {
    // barrier_reached: count must meet threshold
    let threshold = 5 + (idx % 10);
    if !barrier_reached(threshold, threshold) {
        return false;
    }
    if barrier_reached(threshold - 1, threshold) {
        return false;
    }

    // merge_counts: must SUM values (buggy: takes max)
    let mut a = std::collections::HashMap::new();
    let mut b = std::collections::HashMap::new();
    let val_a = idx % 20 + 1;
    let val_b = idx % 15 + 1;
    a.insert("x".to_string(), val_a);
    b.insert("x".to_string(), val_b);
    b.insert("y".to_string(), 10);
    let merged = merge_counts(&a, &b);
    if *merged.get("x").unwrap_or(&0) != val_a + val_b {
        return false;
    }
    if *merged.get("y").unwrap_or(&0) != 10 {
        return false;
    }

    // Partition check with idx-varied values
    let val = (idx % 10) as i32;
    let thresh = 5i32;
    let items = [val, val + 3, val + 6, val + 9];
    let (below, above) = partition_by_threshold(&items, thresh);
    // below should contain items < thresh, above should contain items >= thresh
    for &v in &below {
        if v >= thresh {
            return false;
        }
    }
    for &v in &above {
        // Correct: above should include items >= thresh (including thresh itself)
        if v < thresh {
            return false;
        }
    }
    // Also verify threshold value itself is in above if present
    if items.contains(&thresh) && !above.contains(&thresh) {
        return false;
    }

    // detect_cycle: DAG with no cycle should return true (no cycle detected)
    // Buggy: inverted result
    let edges_no_cycle: Vec<(usize, usize)> = vec![(0, 1), (1, 2)];
    if !detect_cycle(&edges_no_cycle, 3) {
        return false;
    }
    // Graph with cycle should return false
    let edges_cycle: Vec<(usize, usize)> = vec![(0, 1), (1, 2), (2, 0)];
    if detect_cycle(&edges_cycle, 3) {
        return false;
    }

    // AtomicCounter
    let counter = AtomicCounter::new(idx as i64);
    let v1 = counter.increment();
    if v1 != (idx as i64) + 1 {
        return false;
    }
    let v2 = counter.get();
    if v2 != (idx as i64) + 1 {
        return false;
    }

    // parallel_sum
    let base = (idx % 100) as i64;
    if parallel_sum(&[vec![base, base + 1], vec![base + 2, base + 3]]) != 4 * base + 6 {
        return false;
    }

    true
}

/// Group 2 - EVENTS: sort_events_by_time, dedup_by_id, filter_time_window,
/// count_by_kind, detect_gaps, batch_events, event_rate, merge_event_streams,
/// correlate_workflow_events
fn check_events(idx: usize) -> bool {
    let base_ts = (idx % 100) as u64;

    // sort_events_by_time
    let timed_events = vec![
        TimedEvent { id: format!("t1-{}", idx), timestamp: base_ts + 300, kind: "A".into(), payload: "".into() },
        TimedEvent { id: format!("t2-{}", idx), timestamp: base_ts + 100, kind: "B".into(), payload: "".into() },
    ];
    let sorted_events = sort_events_by_time(&timed_events);
    if sorted_events[0].timestamp != base_ts + 100 {
        return false;
    }

    // dedup_by_id
    let dup_events = vec![
        TimedEvent { id: "dup".into(), timestamp: 10, kind: "X".into(), payload: "".into() },
        TimedEvent { id: "dup".into(), timestamp: 20, kind: "X".into(), payload: "".into() },
        TimedEvent { id: "unique".into(), timestamp: 15, kind: "Y".into(), payload: "".into() },
    ];
    let deduped = dedup_by_id(&dup_events);
    if deduped.len() != 2 {
        return false;
    }

    // filter_time_window
    let tw = filter_time_window(&timed_events, base_ts + 100, base_ts + 300);
    if tw.len() != 2 {
        return false;
    }

    // count_by_kind
    let ck = count_by_kind(&timed_events);
    if *ck.get("A").unwrap_or(&0) != 1 || *ck.get("B").unwrap_or(&0) != 1 {
        return false;
    }

    // detect_gaps
    let gap_events = vec![
        TimedEvent { id: "g1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "g2".into(), timestamp: 200, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "g3".into(), timestamp: 500, kind: "A".into(), payload: "".into() },
    ];
    let gaps = detect_gaps(&gap_events, 200);
    // gap between 200 and 500 is 300, >= 200 threshold
    if gaps.is_empty() {
        return false;
    }

    // batch_events
    let batch = batch_events(&timed_events, 100);
    if batch.is_empty() {
        return false;
    }

    // event_rate
    let rate_events = vec![
        TimedEvent { id: "r1".into(), timestamp: 0, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "r2".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
    ];
    let er = event_rate(&rate_events);
    if er <= 0.0 {
        return false;
    }

    // merge_event_streams
    let stream_a = vec![
        TimedEvent { id: "s1".into(), timestamp: 10, kind: "A".into(), payload: "".into() },
    ];
    let stream_b = vec![
        TimedEvent { id: "s2".into(), timestamp: 5, kind: "B".into(), payload: "".into() },
    ];
    let merged = merge_event_streams(&stream_a, &stream_b);
    if merged.len() != 2 {
        return false;
    }

    // correlate_workflow_events: looks for events BEFORE transition (within window)
    let corr_events = vec![
        TimedEvent { id: format!("ce1-{}", idx), timestamp: 90, kind: "A".into(), payload: "".into() },
    ];
    let correlated = correlate_workflow_events(&[100], &corr_events, 20);
    if correlated[0].is_empty() {
        return false;
    }

    true
}

/// Group 3 - TELEMETRY: error_rate, latency_bucket, throughput, health_score,
/// is_within_threshold, uptime_percentage, should_alert, alert_priority
fn check_telemetry(idx: usize) -> bool {
    // error_rate
    let total = 100 + (idx % 50);
    let errors = 5 + (idx % 5);
    let err_r = error_rate(total, errors);
    let expected_err = errors as f64 / total as f64;
    if (err_r - expected_err).abs() > 0.01 {
        return false;
    }

    // latency_bucket
    if latency_bucket(100) != "slow" {
        return false;
    }
    if latency_bucket(10) != "fast" {
        return false;
    }

    // throughput
    let count = 1000 + (idx % 500);
    let duration = 2000u64;
    let tput = throughput(count, duration);
    // throughput should be count per second: count * 1000 / duration_ms
    let expected_tput = count as f64 * 1000.0 / duration as f64;
    if (tput - expected_tput).abs() > 0.01 {
        return false;
    }

    // health_score
    let hs = health_score(1.0, 0.5);
    if (hs - 0.8).abs() > 0.01 {
        return false;
    }

    // is_within_threshold
    let val = 9.5 + (idx % 3) as f64 * 0.1;
    if !is_within_threshold(val, 10.0, 1.0) {
        return false;
    }

    // uptime_percentage
    let total_sec = 1000 + (idx % 200) as u64;
    let down_sec = 100u64;
    let up = uptime_percentage(total_sec, down_sec);
    let expected_up = ((total_sec - down_sec) as f64 / total_sec as f64) * 100.0;
    if (up - expected_up).abs() > 0.01 {
        return false;
    }

    // should_alert
    if !should_alert(95.0, 90.0) || should_alert(80.0, 90.0) {
        return false;
    }

    // alert_priority
    if alert_priority(95.0, 80.0, 90.0) != "critical" {
        return false;
    }
    if alert_priority(85.0, 80.0, 90.0) != "warning" {
        return false;
    }

    true
}

/// Group 4 - ALLOCATOR: allocate_orders, dispatch_batch, estimate_cost, validate_order,
/// weighted_allocate, round_allocation, cost_per_unit, normalize_urgency, is_over_capacity,
/// demand_spike, berth_schedule_conflict_window
fn check_allocator(idx: usize) -> bool {
    let severity_a = (idx % 7) as i32 + 1;
    let sla_a = (20 + (idx % 90)) as i32;

    // allocate_orders with idx-parameterized DispatchOrders
    let order_a = DispatchOrder { id: format!("a-{idx}"), severity: severity_a, sla_minutes: sla_a };
    let planned = allocate_orders(
        vec![
            (order_a.id.clone(), order_a.urgency_score(), 10 + (idx % 30) as i32),
            (format!("b-{idx}"), (idx % 50) as i32 + 5, 20 + (idx % 20) as i32),
            (format!("c-{idx}"), (idx % 30) as i32 + 2, (40 + (idx % 30)) as i32),
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

    // weighted_allocate
    let wa = weighted_allocate(&[("a".into(), 5, 2.0), ("b".into(), 3, 4.0)], 1);
    if wa.is_empty() {
        return false;
    }

    // round_allocation
    if round_allocation(3.7) != 4 || round_allocation(3.2) != 3 {
        return false;
    }

    // cost_per_unit
    let total_cost = 100.0 + (idx % 50) as f64;
    let qty = 4 + (idx % 5);
    let cpu = cost_per_unit(total_cost, qty);
    let expected_cpu = total_cost / qty as f64;
    if (cpu - expected_cpu).abs() > 0.01 {
        return false;
    }

    // normalize_urgency
    let raw = (50 + (idx % 50)) as f64;
    let max_val = 100.0;
    let nu = normalize_urgency(raw, max_val);
    let expected_nu = raw / max_val;
    if (nu - expected_nu).abs() > 0.01 {
        return false;
    }

    // is_over_capacity
    if !is_over_capacity(10, 10) || is_over_capacity(9, 10) {
        return false;
    }

    // estimate_cost
    let cost = estimate_cost(severity_a, sla_a, 10.0);
    if cost < 0.0 {
        return false;
    }

    // demand_spike detection
    let current_load = 150.0 + (idx % 20) as f64;
    if !demand_spike(current_load, 100.0, 25.0) || demand_spike(110.0, 100.0, 25.0) {
        return false;
    }

    // berth_schedule_conflict_window
    let conflict_slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 10, end_hour: 14, occupied: true, vessel_id: None },
    ];
    if !berth_schedule_conflict_window(&conflict_slots, 14, 18, "B1", 2) {
        return false;
    }
    // Arrival-side buffer should also detect conflict
    if !berth_schedule_conflict_window(&conflict_slots, 6, 10, "B1", 2) {
        return false;
    }

    true
}

/// Group 5 - MODELS: severity_label, weight_class, estimated_crew,
/// hazmat_surcharge, eta_minutes, effective_sla, time_adjusted_urgency, DispatchOrder
fn check_models(idx: usize) -> bool {
    // severity_label
    if severity_label(5) != "critical" {
        return false;
    }
    if severity_label(4) != "high" {
        return false;
    }
    if severity_label(3) != "medium" {
        return false;
    }
    if severity_label(2) != "low" {
        return false;
    }
    if severity_label(1) != "info" {
        return false;
    }

    // weight_class with idx variation
    if weight_class(100_001.0) != "super-heavy" || weight_class(100_000.0) != "heavy" {
        return false;
    }
    let cargo = (idx % 5) as f64 * 30_000.0 + 1.0;
    let _wc = weight_class(cargo);

    // estimated_crew
    let containers = 100 + (idx % 400) as u32;
    let crew = estimated_crew(containers);
    // Correct: (containers + 99) / 100 (ceiling division), buggy: containers / 100 (floor)
    let expected_crew = (containers + 99) / 100;
    if crew != expected_crew {
        return false;
    }

    // hazmat_surcharge
    let base = 100.0 + (idx % 50) as f64;
    let surcharge = hazmat_surcharge(base, true);
    let expected_surcharge = base * 2.5;
    if (surcharge - expected_surcharge).abs() > 0.01 {
        return false;
    }
    // Non-hazmat should be base cost
    if (hazmat_surcharge(base, false) - base).abs() > 0.01 {
        return false;
    }

    // eta_minutes
    let distance = 60.0 + (idx % 40) as f64;
    let speed = 10.0;
    let eta = eta_minutes(distance, speed);
    let expected_eta = (distance / speed) * 60.0;
    if (eta - expected_eta).abs() > 0.01 {
        return false;
    }

    // effective_sla: serial dependency (correct) vs parallel redundancy (buggy)
    let sla = effective_sla(0.999, 0.999);
    if (sla - 0.998001).abs() > 0.0001 {
        return false;
    }

    // time_adjusted_urgency: should increase near deadline
    let base_urg = 10.0 + (idx % 10) as f64;
    let urg_start = time_adjusted_urgency(base_urg, 0.0, 60.0);
    let urg_end = time_adjusted_urgency(base_urg, 55.0, 60.0);
    if urg_end <= urg_start {
        return false;
    }

    // DispatchOrder urgency_score
    let sev = (idx % 5) as i32 + 1;
    let sla_min = (20 + (idx % 80)) as i32;
    let order = DispatchOrder { id: format!("test-{}", idx), severity: sev, sla_minutes: sla_min };
    let score = order.urgency_score();
    if score < 0 {
        return false;
    }

    true
}

/// Group 6 - POLICY: next_policy, previous_policy, check_sla_compliance,
/// policy_weight, escalation_needed, risk_score, within_grace_period,
/// cooldown_multiplier, aggregate_risk, escalation_with_cooldown
fn check_policy(idx: usize) -> bool {
    // next_policy: escalation from "normal" or "watch" should move UP (not stay at "normal")
    let policies = ["normal", "watch", "restricted", "halted"];
    let start_pol = policies[idx % 2]; // "normal" or "watch"
    let burst = 2 + (idx % 3);
    let pol = next_policy(start_pol, burst);
    if pol != "watch" && pol != "restricted" && pol != "halted" {
        return false;
    }

    // previous_policy (de-escalation)
    let prev = previous_policy(pol);
    if prev.is_empty() {
        return false;
    }

    // check_sla_compliance
    let actual = 30 + (idx % 20) as i32;
    let sla = 60;
    if !check_sla_compliance(actual, sla) {
        return false;
    }
    if check_sla_compliance(90, 60) {
        return false;
    }

    // policy_weight: halted should be > normal
    if policy_weight("halted") <= policy_weight("normal") {
        return false;
    }

    // escalation_needed: at threshold should NOT escalate (must exceed)
    if escalation_needed(0.5, 0.5) {
        return false;
    }

    // risk_score: severity * probability
    let sev = 4.0 + (idx % 3) as f64;
    let prob = 0.5;
    let rs = risk_score(sev, prob);
    let expected_rs = sev * prob;
    if (rs - expected_rs).abs() > 0.01 {
        return false;
    }

    // within_grace_period: elapsed == grace should still be within
    let grace = 10 + (idx % 20) as u64;
    if !within_grace_period(grace, grace) {
        return false;
    }

    // cooldown_multiplier
    let multipliers = [("normal", 1u64), ("watch", 2), ("restricted", 4), ("halted", 8)];
    let pick = idx % multipliers.len();
    if cooldown_multiplier(multipliers[pick].0) != multipliers[pick].1 {
        return false;
    }

    // aggregate_risk
    if (aggregate_risk(&[(10.0, 0.8), (5.0, 0.4)]) - 5.0).abs() > 0.01 {
        return false;
    }

    // escalation_with_cooldown: cooldown not elapsed, should stay at current
    let esc = escalation_with_cooldown("normal", 5, 900, 1000, 200);
    if esc != "normal" {
        return false;
    }

    true
}

/// Group 7 - QUEUE: estimate_wait_time, queue_health, should_shed,
/// priority_boost, queue_pressure, drain_percentage
fn check_queue(idx: usize) -> bool {
    let depth = (idx % 30) + 1;

    // should_shed
    if should_shed(depth, 40, false) || !should_shed(41, 40, false) {
        return false;
    }

    // queue_health
    let health = queue_health(depth, 40);
    if health.status.is_empty() {
        return false;
    }

    // estimate_wait_time
    let rate = 2.0 + (idx % 5) as f64;
    let items = 10 + (idx % 20);
    let wt = estimate_wait_time(items, rate);
    let expected_wt = items as f64 / rate;
    if (wt - expected_wt).abs() > 0.01 {
        return false;
    }

    // priority_boost
    let base_pri = (idx % 10) as i32 + 1;
    let boost = (idx % 5) as i32 + 1;
    let boosted = priority_boost(&QueueItem { id: format!("q-{}", idx), priority: base_pri }, boost);
    if boosted.priority != base_pri + boost {
        return false;
    }

    // queue_pressure
    let qlimit = 10 + (idx % 20);
    let qdepth = 12 + (idx % 15);
    let qp = queue_pressure(qdepth, qlimit);
    let expected_qp = qdepth as f64 / qlimit as f64;
    if (qp - expected_qp).abs() > 0.01 {
        return false;
    }

    // drain_percentage
    let drained = 25 + (idx % 30);
    let total = 100;
    let dp = drain_percentage(drained, total);
    let expected_dp = (drained as f64 / total as f64) * 100.0;
    if (dp - expected_dp).abs() > 0.01 {
        return false;
    }

    true
}

/// Group 8 - RESILIENCE: replay, deduplicate, replay_converges, replay_window,
/// event_ordering, retry_delay, should_trip, recovery_rate, degradation_level,
/// bulkhead_permits_available, cascade_failure_check, health_quorum,
/// process_replay_batch
fn check_resilience(idx: usize) -> bool {
    // replay
    let replayed = replay(&[
        Event { id: format!("k-{}", idx % 17), sequence: 1 },
        Event { id: format!("k-{}", idx % 17), sequence: 2 },
        Event { id: format!("z-{}", idx % 13), sequence: 1 },
    ]);
    if replayed.len() < 2 {
        return false;
    }

    // deduplicate
    let deduped = deduplicate(&[
        Event { id: "d1".into(), sequence: 1 },
        Event { id: "d1".into(), sequence: 2 },
    ]);
    if deduped.len() != 1 {
        return false;
    }

    // replay_converges
    if !replay_converges(
        &[Event { id: "r".into(), sequence: 1 }, Event { id: "r".into(), sequence: 2 }],
        &[Event { id: "r".into(), sequence: 2 }, Event { id: "r".into(), sequence: 1 }],
    ) {
        return false;
    }

    // replay_window: only sequence in [min_seq, max_seq]
    let rw = replay_window(
        &[Event { id: "a".into(), sequence: 5 }, Event { id: "b".into(), sequence: 15 }],
        5, 10,
    );
    if rw.len() != 1 {  // only sequence 5 is in [5,10]
        return false;
    }

    // event_ordering: should sort ascending by sequence
    let seq_a = 1 + (idx % 10) as i64;
    let seq_b = seq_a + 5;
    let eo = event_ordering(&[Event { id: "b".into(), sequence: seq_b }, Event { id: "a".into(), sequence: seq_a }]);
    if eo[0].sequence != seq_a {
        return false;
    }

    // retry_delay: exponential backoff base * 2^attempt
    let base_ms = 100 + (idx % 50) as u64;
    let attempt = 2;
    let rd = retry_delay(base_ms, attempt);
    let expected_rd = base_ms * 2u64.pow(attempt);
    if rd != expected_rd {
        return false;
    }

    // should_trip
    if !should_trip(8, 10, 0.5) {
        return false;
    }

    // recovery_rate
    let successes = 8 + (idx % 5);
    let failures = 2 + (idx % 3);
    let rr = recovery_rate(successes, failures);
    let expected_rr = successes as f64 / (successes + failures) as f64;
    if (rr - expected_rr).abs() > 0.01 {
        return false;
    }

    // degradation_level
    if degradation_level(0.1) != "minor" {
        return false;
    }

    // bulkhead_permits_available: used == max -> no permits
    if bulkhead_permits_available(5, 5) {
        return false;
    }

    // cascade_failure_check: should detect if ANY dependency is unhealthy
    if !cascade_failure_check(&[true, false, true]) {
        return false;
    }

    // health_quorum
    if !health_quorum(&[true, true, true, false], 0.75) {
        return false;
    }

    // process_replay_batch: should sort ascending
    let s1 = 1 + (idx % 5) as i64;
    let s2 = s1 + 1;
    let s3 = s2 + 1;
    let batch = process_replay_batch(&[
        Event { id: "a".into(), sequence: s3 },
        Event { id: "b".into(), sequence: s1 },
        Event { id: "c".into(), sequence: s2 },
    ]);
    if batch[0].sequence != s1 || batch[1].sequence != s2 {
        return false;
    }

    true
}

/// Group 9 - ROUTING: choose_route, channel_score, estimate_transit_time,
/// best_route, distance_between, fuel_efficiency, total_port_fees, knots_to_kmh,
/// route_reliability, congestion_adjusted_latency
fn check_routing(idx: usize) -> bool {
    // choose_route
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

    // channel_score
    let lat = 5 + (idx % 10) as i32;
    let cs = channel_score(lat, 0.9, 8);
    if cs <= 0.0 {
        return false;
    }

    // estimate_transit_time
    let dist = 100.0 + (idx % 100) as f64;
    let speed = 20.0;
    let tt = estimate_transit_time(dist, speed);
    if (tt - dist / speed).abs() > 0.01 {
        return false;
    }

    // best_route: should pick lowest latency
    let br = best_route(&[
        Route { channel: "a".into(), latency: 10 + (idx % 5) as i32 },
        Route { channel: "b".into(), latency: 2 },
    ]);
    if br.unwrap().channel != "b" {
        return false;
    }

    // distance_between: should be absolute difference
    let a_pos = 10.0 + (idx % 20) as f64;
    let b_pos = 3.0;
    if (distance_between(a_pos, b_pos) - (a_pos - b_pos).abs()).abs() > 0.01 {
        return false;
    }

    // fuel_efficiency: distance / fuel
    let fuel = 20.0 + (idx % 10) as f64;
    if (fuel_efficiency(100.0, fuel) - (100.0 / fuel)).abs() > 0.01 {
        return false;
    }

    // total_port_fees: sum of all fees
    let fee1 = 100.0 + (idx % 50) as f64;
    let fee2 = 200.0;
    if (total_port_fees(&[fee1, fee2]) - (fee1 + fee2)).abs() > 0.01 {
        return false;
    }

    // knots_to_kmh
    let knots = 10.0 + (idx % 20) as f64;
    if (knots_to_kmh(knots) - knots * 1.852).abs() > 0.01 {
        return false;
    }

    // route_reliability
    let succ = 8 + (idx % 3);
    let total = 10;
    if (route_reliability(succ, total) - succ as f64 / total as f64).abs() > 0.01 {
        return false;
    }

    // congestion_adjusted_latency
    let base_lat = 100 + (idx % 50) as i32;
    let load = 0.5;
    let cal = congestion_adjusted_latency(base_lat, load);
    let expected_cal = (base_lat as f64 * (1.0 + load)) as i32;
    if cal != expected_cal {
        return false;
    }

    true
}

/// Group 10 - SECURITY: digest, verify_signature, sign_manifest, verify_manifest,
/// sanitise_path, validate_token_format, password_strength, mask_sensitive,
/// rate_limit_key, session_expired, permission_check, ip_in_allowlist,
/// token_needs_refresh
fn check_security(idx: usize) -> bool {
    // digest + verify_signature (unconditional - was conditional on idx % 17 == 0)
    let payload = format!("manifest:{idx}");
    let sig = digest(&payload);
    if !verify_signature(&payload, &sig, &sig) {
        return false;
    }
    if verify_signature(&payload, &sig[1..], &sig) {
        return false;
    }

    // sign_manifest + verify_manifest
    let key = format!("key-{}", idx % 10);
    let msig = sign_manifest(&payload, &key);
    if !verify_manifest(&payload, &key, &msig) {
        return false;
    }

    // sanitise_path
    let paths = ["../../etc/passwd", "../../../root", "..\\windows\\system"];
    let path = paths[idx % paths.len()];
    let clean = sanitise_path(path);
    if clean.contains("..") {
        return false;
    }

    // validate_token_format
    let tokens = ["abc123", "token-xyz", "t1"];
    let tok = tokens[idx % tokens.len()];
    if !validate_token_format(tok) || validate_token_format("") {
        return false;
    }

    // password_strength
    if password_strength("abcdefgh") != "medium" {
        return false;
    }

    // mask_sensitive: last 4 chars should be visible
    let sensitive_vals = ["abcdefgh", "mysecretkey", "password123"];
    let sv = sensitive_vals[idx % sensitive_vals.len()];
    if !mask_sensitive(sv).ends_with(&sv[sv.len()-4..]) {
        return false;
    }

    // rate_limit_key: should contain IP
    let ips = ["192.168.1.1", "10.0.0.5", "172.16.0.1"];
    let ip = ips[idx % ips.len()];
    if !rate_limit_key(ip, "/api").contains(ip) {
        return false;
    }

    // session_expired
    if session_expired(1000, 300, 1200) {
        return false;
    }

    // permission_check: all required must be in granted
    if !permission_check(&["read", "write"], &["read", "write", "admin"]) {
        return false;
    }
    if permission_check(&["read", "write"], &["read"]) {
        return false;
    }

    // ip_in_allowlist
    if ip_in_allowlist("10.0.0.10", &["10.0.0.1"]) {
        return false;
    }

    // token_needs_refresh
    if !token_needs_refresh(1000, 4400, 3600, 300) {
        return false;
    }
    if token_needs_refresh(1000, 4200, 3600, 300) {
        return false;
    }

    true
}

/// Group 11 - STATISTICS: mean, moving_average, percentile, weighted_mean,
/// exponential_moving_average, min_max_normalize, sum_of_squares, rate_of_change,
/// z_score, cumulative_sum, running_variance, detect_trend
fn check_statistics(idx: usize) -> bool {
    // mean
    let vals: Vec<f64> = (0..3).map(|i| (1 + i + (idx % 5)) as f64).collect();
    let m = mean(&vals);
    let expected_m = vals.iter().sum::<f64>() / vals.len() as f64;
    if (m - expected_m).abs() > 0.01 {
        return false;
    }

    // moving_average
    let ma = moving_average(&[1.0, 2.0, 3.0, 4.0], 2);
    if ma.len() != 3 {
        return false;
    }

    // percentile
    let pct_vals = [(idx % 11) as i32, ((idx * 7) % 11) as i32, ((idx * 5) % 11) as i32, ((idx * 3) % 11) as i32];
    let p50 = percentile(&pct_vals, 50);
    if p50 < 0 {
        return false;
    }

    // weighted_mean
    let wm = weighted_mean(&[10.0, 20.0, 30.0], &[1.0, 2.0, 3.0]);
    if (wm - 23.333).abs() > 0.01 {
        return false;
    }

    // exponential_moving_average
    let ema = exponential_moving_average(10.0, 20.0, 0.5);
    if (ema - 15.0).abs() > 0.01 {
        return false;
    }

    // min_max_normalize
    let val = (idx % 10) as f64;
    let nmm = min_max_normalize(val, 0.0, 10.0);
    let expected_nmm = val / 10.0;
    if (nmm - expected_nmm).abs() > 0.01 {
        return false;
    }

    // sum_of_squares
    let sq_vals: Vec<f64> = (1..=3).map(|i| (i + (idx % 3)) as f64).collect();
    let ss = sum_of_squares(&sq_vals);
    let expected_ss: f64 = sq_vals.iter().map(|v| v * v).sum();
    if (ss - expected_ss).abs() > 0.01 {
        return false;
    }

    // rate_of_change
    let old_val = 100.0 + (idx % 50) as f64;
    let new_val = old_val * 1.5;
    let roc = rate_of_change(old_val, new_val);
    let expected_roc = (new_val - old_val) / old_val;
    if (roc - expected_roc).abs() > 0.01 {
        return false;
    }

    // z_score
    let value = 80.0 + (idx % 20) as f64;
    let pop_mean = 70.0;
    let pop_std = 5.0;
    let z = z_score(value, pop_mean, pop_std);
    let expected_z = (value - pop_mean) / pop_std;
    if (z - expected_z).abs() > 0.01 {
        return false;
    }

    // cumulative_sum
    let cs = cumulative_sum(&[1.0, 2.0, 3.0]);
    if cs.len() != 3 || (cs[2] - 6.0).abs() > 0.01 {
        return false;
    }

    // running_variance (buggy: uses window as divisor during warmup)
    let rv = running_variance(&[10.0, 20.0, 30.0], 5);
    // At i=1: slice=[10,20], len=2, correct divisor=(len-1)=1 -> variance=50.0
    if rv.len() != 3 || (rv[1] - 50.0).abs() > 0.01 {
        return false;
    }

    // detect_trend
    let trend_vals: Vec<f64> = (0..5).map(|i| (1 + i + (idx % 3)) as f64).collect();
    if detect_trend(&trend_vals, 0.3) != "rising" {
        return false;
    }

    true
}

/// Group 12 - WORKFLOW: can_transition, is_terminal_state, shortest_path,
/// can_cancel, estimated_completion, state_age_seconds, valid_path,
/// entity_throughput, reachable_from, can_resume, compact_history
fn check_workflow(idx: usize) -> bool {
    // can_transition
    let (src, dst) = if idx % 2 == 0 { ("queued", "allocated") } else { ("allocated", "departed") };
    if !can_transition(src, dst) || can_transition("arrived", "queued") {
        return false;
    }

    // shortest_path
    if shortest_path("queued", "arrived").is_none() {
        return false;
    }

    // is_terminal_state
    if !is_terminal_state("arrived") || is_terminal_state("queued") {
        return false;
    }

    // can_cancel: should allow cancelling allocated too, not just queued
    if !can_cancel("allocated") || can_cancel("arrived") {
        return false;
    }

    // estimated_completion
    let avg_time = 10.0 + (idx % 5) as f64;
    let ec = estimated_completion("queued", avg_time);
    // shortest_path("queued", "arrived") = ["queued", "allocated", "departed", "arrived"] = 4 nodes, 3 transitions
    let expected_ec = 3.0 * avg_time;
    if (ec - expected_ec).abs() > 0.01 {
        return false;
    }

    // state_age_seconds
    let entered = 100 + (idx % 100) as u64;
    let now = 500 + (idx % 200) as u64;
    let age = state_age_seconds(entered, now);
    let expected_age = now as i64 - entered as i64;
    if age != expected_age {
        return false;
    }

    // valid_path
    if !valid_path(&["queued", "allocated", "departed", "arrived"]) {
        return false;
    }

    // entity_throughput
    let completed = 360 + (idx % 100);
    let elapsed = 3600u64;
    let tp = entity_throughput(completed, elapsed);
    let expected_tp = completed as f64 / (elapsed as f64 / 60.0);
    if (tp - expected_tp).abs() > 0.01 {
        return false;
    }

    // reachable_from
    let reachable = reachable_from("queued");
    if !reachable.contains(&"allocated".to_string()) {
        return false;
    }

    // can_resume
    if !can_resume("queued") || can_resume("arrived") {
        return false;
    }

    // compact_history: keeps LAST record per entity (not first)
    let ts1 = 1 + (idx % 10) as u64;
    let ts2 = ts1 + 1;
    let hist = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: ts1 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: ts2 },
    ];
    let compacted = compact_history(&hist);
    if compacted.len() != 1 || compacted[0].to != "departed" {
        return false;
    }

    true
}

/// Group 13 - INTEGRATION: Cross-module interactions.
/// Includes the original full run_case checks that span multiple modules,
/// plus contracts (get_service_url).
fn check_integration(idx: usize) -> bool {
    let severity_a = (idx % 7) as i32 + 1;
    let severity_b = ((idx * 3) % 7) as i32 + 1;
    let sla_a = (20 + (idx % 90)) as i32;
    let sla_b = (20 + ((idx * 2) % 90)) as i32;

    let order_a = DispatchOrder { id: format!("a-{idx}"), severity: severity_a, sla_minutes: sla_a };
    let order_b = DispatchOrder { id: format!("b-{idx}"), severity: severity_b, sla_minutes: sla_b };

    // allocate_orders with idx-parameterized DispatchOrders
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

    // choose_route
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

    // channel_score and transit time
    let cs = channel_score(5, 0.9, 8);
    if cs <= 0.0 {
        return false;
    }
    let tt = estimate_transit_time(100.0, 20.0);
    if (tt - 5.0).abs() > 0.01 {
        return false;
    }

    // workflow transitions
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

    // === Cross-module strict checks (one per module to ensure ALL are correct) ===

    // CONFIG: default_region must be "us-east-1" (buggy: "eu-west-1")
    if default_region() != "us-east-1" {
        return false;
    }

    // CONCURRENCY: merge_counts must SUM (buggy: takes max)
    {
        let mut a = std::collections::HashMap::new();
        let mut b = std::collections::HashMap::new();
        a.insert("x".to_string(), 3usize);
        b.insert("x".to_string(), 4usize);
        let merged = merge_counts(&a, &b);
        if *merged.get("x").unwrap_or(&0) != 7 {
            return false;
        }
    }

    // EVENTS: sort_events_by_time must be ascending (buggy: descending)
    {
        let te = vec![
            TimedEvent { id: "e1".into(), timestamp: 200, kind: "X".into(), payload: "".into() },
            TimedEvent { id: "e2".into(), timestamp: 50, kind: "X".into(), payload: "".into() },
        ];
        let sorted = sort_events_by_time(&te);
        if sorted[0].timestamp != 50 {
            return false;
        }
    }

    // TELEMETRY: error_rate = errors/total (buggy: total/errors)
    {
        let er = error_rate(200, 10);
        if (er - 0.05).abs() > 0.01 {
            return false;
        }
    }

    // ALLOCATOR: cost_per_unit = total/qty (buggy: total*qty)
    {
        let cpu = cost_per_unit(100.0, 4);
        if (cpu - 25.0).abs() > 0.01 {
            return false;
        }
    }

    // MODELS: severity_label(5) must be "critical" (buggy: "high")
    if severity_label(5) != "critical" {
        return false;
    }

    // POLICY: next_policy must escalate (buggy may not)
    let pol = next_policy(if idx % 2 == 0 { "normal" } else { "watch" }, 2 + (idx % 2));
    if pol != "watch" && pol != "restricted" && pol != "halted" {
        return false;
    }

    // QUEUE: priority_boost must ADD (buggy: subtracts)
    {
        let boosted = priority_boost(&QueueItem { id: "x".into(), priority: 5 }, 3);
        if boosted.priority != 8 {
            return false;
        }
    }

    // RESILIENCE: event_ordering must sort ascending (buggy: descending)
    {
        let eo = event_ordering(&[Event { id: "b".into(), sequence: 5 }, Event { id: "a".into(), sequence: 1 }]);
        if eo[0].sequence != 1 {
            return false;
        }
    }

    // ROUTING: best_route must pick lowest latency (buggy: highest)
    {
        let br = best_route(&[Route { channel: "a".into(), latency: 10 }, Route { channel: "b".into(), latency: 2 }]);
        if br.unwrap().channel != "b" {
            return false;
        }
    }

    // SECURITY: validate_token_format must reject empty (buggy: always true)
    if validate_token_format("") {
        return false;
    }

    // STATISTICS: weighted_mean exact check (buggy: wrong divisor)
    {
        let wm = weighted_mean(&[10.0, 20.0, 30.0], &[1.0, 2.0, 3.0]);
        if (wm - 23.333).abs() > 0.01 {
            return false;
        }
    }

    // WORKFLOW: can_cancel must accept "allocated" (buggy: only "queued")
    if !can_cancel("allocated") {
        return false;
    }

    // === Original cross-module integration flow ===

    // SLA compliance
    if !check_sla_compliance(30, 60) || check_sla_compliance(90, 60) {
        return false;
    }

    // should_shed
    let depth = (idx % 30) + 1;
    if should_shed(depth, 40, false) || !should_shed(41, 40, false) {
        return false;
    }

    // replay with idx-parameterized events
    let replayed = replay(&[
        Event { id: format!("k-{}", idx % 17), sequence: 1 },
        Event { id: format!("k-{}", idx % 17), sequence: 2 },
        Event { id: format!("z-{}", idx % 13), sequence: 1 },
    ]);
    if replayed.len() < 2 {
        return false;
    }

    // Security digest
    let payload = format!("manifest:{idx}");
    let sig = digest(&payload);
    if !verify_signature(&payload, &sig, &sig) {
        return false;
    }

    // Cost estimation
    let cost = estimate_cost(severity_a, sla_a, 10.0);
    if cost < 0.0 {
        return false;
    }

    // Service URL resolution (contracts)
    if get_service_url("gateway").is_none() {
        return false;
    }

    true
}

fn run_case(idx: usize) -> bool {
    match idx % NUM_GROUPS {
        0 => check_config(idx),
        1 => check_concurrency(idx),
        2 => check_events(idx),
        3 => check_telemetry(idx),
        4 => check_allocator(idx),
        5 => check_models(idx),
        6 => check_policy(idx),
        7 => check_queue(idx),
        8 => check_resilience(idx),
        9 => check_routing(idx),
        10 => check_security(idx),
        11 => check_statistics(idx),
        12 => check_workflow(idx),
        13 => check_integration(idx),
        _ => unreachable!(),
    }
}

#[test]
fn hyper_matrix_scenarios() {
    let mut passed = 0usize;
    let mut failed = 0usize;
    let mut group_passed = [0usize; NUM_GROUPS];
    let mut group_total = [0usize; NUM_GROUPS];

    for idx in 0..TOTAL_CASES {
        let group = idx % NUM_GROUPS;
        group_total[group] += 1;
        if run_case(idx) {
            passed += 1;
            group_passed[group] += 1;
        } else {
            failed += 1;
        }
    }

    // Per-module detail line for diagnostic parsing
    let detail_parts: Vec<String> = (0..NUM_GROUPS)
        .map(|g| format!("{}={}/{}", GROUP_NAMES[g], group_passed[g], group_total[g]))
        .collect();
    println!("TB_DETAIL {}", detail_parts.join(" "));
    println!("TB_SUMMARY total={} passed={} failed={}", TOTAL_CASES, passed, failed);
    assert_eq!(failed, 0, "hyper matrix had {} failing scenarios", failed);
}
