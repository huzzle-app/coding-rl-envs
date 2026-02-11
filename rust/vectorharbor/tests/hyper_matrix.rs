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

const TOTAL_CASES: usize = 9200;

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
