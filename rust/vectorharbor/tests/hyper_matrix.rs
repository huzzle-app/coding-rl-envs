use vectorharbor::allocator::{allocate_orders, dispatch_batch, estimate_cost, validate_order};
use vectorharbor::models::DispatchOrder;
use vectorharbor::policy::{check_sla_compliance, next_policy, previous_policy};
use vectorharbor::queue::{estimate_wait_time, queue_health, should_shed};
use vectorharbor::resilience::{deduplicate, replay, replay_converges, Event};
use vectorharbor::routing::{channel_score, choose_route, estimate_transit_time, Route};
use vectorharbor::security::{digest, sanitise_path, sign_manifest, verify_manifest, verify_signature};
use vectorharbor::statistics::{mean, moving_average, percentile};
use vectorharbor::workflow::{can_transition, is_terminal_state, shortest_path};
use vectorharbor::contracts::get_service_url;

const CASES_PER_MODULE: usize = 1150;

/// Seed for procedural variation across episodes.
/// Set EPISODE_SEED env var to vary scenario parameters between runs.
fn episode_seed() -> u64 {
    std::env::var("EPISODE_SEED")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(0)
}

/// Deterministic mixing function for seed-based parameter variation.
fn mix(idx: usize, seed: u64) -> usize {
    if seed == 0 {
        return idx;
    }
    let h = (idx as u64).wrapping_mul(2654435761).wrapping_add(seed);
    (h ^ (h >> 16)) as usize
}

// ─── Module check functions ─────────────────────────────────────────

fn check_allocator(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let severity_a = (m % 7) as i32 + 1;
    let severity_b = ((m * 3 + 1) % 7) as i32 + 1;
    let sla_a = (20 + (m % 90)) as i32;
    let sla_b = (20 + ((m * 2 + 1) % 90)) as i32;

    let order_a = DispatchOrder { id: format!("a-{idx}"), severity: severity_a, sla_minutes: sla_a };
    let order_b = DispatchOrder { id: format!("b-{idx}"), severity: severity_b, sla_minutes: sla_b };

    let planned = allocate_orders(
        vec![
            (order_a.id.clone(), order_a.urgency_score(), format!("0{}:1{}", m % 9, m % 6).parse::<i32>().unwrap_or(0)),
            (order_b.id.clone(), order_b.urgency_score(), format!("0{}:2{}", (m + 3) % 9, m % 6).parse::<i32>().unwrap_or(0)),
            (format!("c-{idx}"), (m % 50) as i32 + 2, (40 + (m % 30)) as i32),
        ],
        2,
    );

    if planned.is_empty() || planned.len() > 2 {
        return false;
    }
    if planned.len() == 2 && planned[0].1 < planned[1].1 {
        return false;
    }

    for p in &planned {
        if validate_order(p).is_err() {
            return false;
        }
    }

    let batch = dispatch_batch(
        vec![("x".into(), 10, 1), ("y".into(), 5, 2)],
        1,
    );
    if batch.planned.len() != 1 || batch.rejected.len() != 1 {
        return false;
    }

    let cost = estimate_cost(severity_a, sla_a, 10.0);
    if cost < 0.0 {
        return false;
    }

    true
}

fn check_routing(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let mut blocked = Vec::new();
    if m % 5 == 0 {
        blocked.push("beta".to_string());
    }

    let route = choose_route(
        &[
            Route { channel: "alpha".to_string(), latency: 2 + (m % 9) as i32 },
            Route { channel: "beta".to_string(), latency: (m % 3) as i32 },
            Route { channel: "gamma".to_string(), latency: 4 + (m % 4) as i32 },
        ],
        &blocked,
    );

    if route.is_none() {
        return false;
    }
    if blocked.iter().any(|v| v == "beta") && route.as_ref().is_some_and(|r| r.channel == "beta") {
        return false;
    }

    let cs = channel_score(5, 0.9, 8);
    if cs <= 0.0 {
        return false;
    }
    let tt = estimate_transit_time(100.0, 20.0);
    if (tt - 5.0).abs() > 0.01 {
        return false;
    }

    true
}

fn check_workflow(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let (src, dst) = if m % 2 == 0 { ("queued", "allocated") } else { ("allocated", "departed") };
    if !can_transition(src, dst) || can_transition("arrived", "queued") {
        return false;
    }

    // departed -> arrived must be a valid transition
    if !can_transition("departed", "arrived") {
        return false;
    }

    if shortest_path("queued", "arrived").is_none() {
        return false;
    }
    if !is_terminal_state("arrived") || is_terminal_state("queued") {
        return false;
    }

    true
}

fn check_policy(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let pol = next_policy(if m % 2 == 0 { "normal" } else { "watch" }, 2 + (m % 2));
    if pol != "watch" && pol != "restricted" && pol != "halted" {
        return false;
    }

    let prev = previous_policy(pol);
    if prev.is_empty() {
        return false;
    }
    if !check_sla_compliance(30, 60) || check_sla_compliance(90, 60) {
        return false;
    }

    true
}

fn check_queue(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let depth = (m % 30) + 1;
    if should_shed(depth, 40, false) || !should_shed(41, 40, false) {
        return false;
    }

    let health = queue_health(depth, 40);
    if health.status.is_empty() {
        return false;
    }
    let wt = estimate_wait_time(10, 2.0);
    if (wt - 5.0).abs() > 0.01 {
        return false;
    }

    true
}

fn check_resilience(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let replayed = replay(&[
        Event { id: format!("k-{}", m % 17), sequence: 1 },
        Event { id: format!("k-{}", m % 17), sequence: 2 },
        Event { id: format!("z-{}", m % 13), sequence: 1 },
    ]);

    if replayed.len() < 2 {
        return false;
    }

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

    true
}

fn check_statistics(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let p50 = percentile(&[(m % 11) as i32, ((m * 7) % 11) as i32, ((m * 5) % 11) as i32, ((m * 3) % 11) as i32], 50);
    if p50 < 0 {
        return false;
    }

    let avg = mean(&[1.0, 2.0, 3.0]);
    if (avg - 2.0).abs() > 0.01 {
        return false;
    }
    let ma = moving_average(&[1.0, 2.0, 3.0, 4.0], 2);
    if ma.len() != 3 {
        return false;
    }

    true
}

fn check_security(idx: usize) -> bool {
    let m = mix(idx, episode_seed());
    let payload = format!("manifest:{m}");
    let sig = digest(&payload);
    if !verify_signature(&payload, &sig, &sig) {
        return false;
    }
    if verify_signature(&payload, &sig[1..], &sig) {
        return false;
    }

    let msig = sign_manifest(&payload, "key");
    if !verify_manifest(&payload, "key", &msig) {
        return false;
    }

    let clean = sanitise_path("../../etc/passwd");
    if clean.contains("..") {
        return false;
    }

    if get_service_url("gateway").is_none() {
        return false;
    }

    true
}

// ─── Test runner ────────────────────────────────────────────────────

fn run_module_scenarios(name: &str, cases: usize, check: fn(usize) -> bool) {
    let mut passed = 0usize;
    let mut failed = 0usize;

    for idx in 0..cases {
        if check(idx) {
            passed += 1;
        } else {
            failed += 1;
        }
    }

    println!("TB_SUMMARY total={} passed={} failed={}", cases, passed, failed);
    assert_eq!(failed, 0, "{} had {} failing scenarios out of {}", name, failed, cases);
}

// ─── Per-module test functions (8 modules x 1150 cases = 9200 total) ─

#[test]
fn hyper_matrix_allocator() {
    run_module_scenarios("hyper_matrix_allocator", CASES_PER_MODULE, check_allocator);
}

#[test]
fn hyper_matrix_routing() {
    run_module_scenarios("hyper_matrix_routing", CASES_PER_MODULE, check_routing);
}

#[test]
fn hyper_matrix_workflow() {
    run_module_scenarios("hyper_matrix_workflow", CASES_PER_MODULE, check_workflow);
}

#[test]
fn hyper_matrix_policy() {
    run_module_scenarios("hyper_matrix_policy", CASES_PER_MODULE, check_policy);
}

#[test]
fn hyper_matrix_queue() {
    run_module_scenarios("hyper_matrix_queue", CASES_PER_MODULE, check_queue);
}

#[test]
fn hyper_matrix_resilience() {
    run_module_scenarios("hyper_matrix_resilience", CASES_PER_MODULE, check_resilience);
}

#[test]
fn hyper_matrix_statistics() {
    run_module_scenarios("hyper_matrix_statistics", CASES_PER_MODULE, check_statistics);
}

#[test]
fn hyper_matrix_security() {
    run_module_scenarios("hyper_matrix_security", CASES_PER_MODULE, check_security);
}
