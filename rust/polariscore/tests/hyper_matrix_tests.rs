//! Hyper-matrix stress tests for PolarisCore
//!
//! This module generates parameterized tests covering all core modules.
//! Each test function runs multiple iterations to validate behavior across
//! a wide range of inputs.

use polariscore::allocator::{allocate_shipments, allocate_to_zones, reallocate_on_overflow, risk_adjusted_allocation};
use polariscore::economics::{break_even_units, margin_ratio, projected_cost_cents, sla_penalty_cents};
use polariscore::models::{FulfillmentWindow, Incident, Shipment, ShipmentState, TransitLeg, Zone};
use polariscore::policy::{aggregate_risk_by_volume, compliance_tier, compound_risk, escalation_level, risk_score};
use polariscore::queue::{batch_dequeue, merge_priority_queues, order_queue, round_robin_drain, QueueItem};
use polariscore::resilience::{adaptive_retry_backoff, replay_budget, replay_events_in_order, retry_backoff, BreakerState, CircuitBreaker};
use polariscore::routing::{route_segments, select_hub, select_hub_with_fallback, validate_cold_chain};
use polariscore::security::{requires_step_up, simple_signature, validate_signature};
use polariscore::statistics::{detect_anomalies, exponential_moving_average, percentile, rolling_sla, trimmed_mean};
use polariscore::workflow::{multi_batch_schedule, plan_fulfillment, ShipmentStateMachine};
use std::collections::HashMap;

const ITERATIONS: usize = 100;

fn run_allocator_test(idx: usize) {
    let shipments = vec![
        Shipment {
            id: format!("ship-{}-a", idx),
            lane: "east".to_string(),
            units: (idx as u32 % 50) + 10,
            priority: ((idx % 5) + 1) as u8,
        },
        Shipment {
            id: format!("ship-{}-b", idx),
            lane: "west".to_string(),
            units: ((idx * 3) as u32 % 40) + 5,
            priority: ((idx % 4) + 2) as u8,
        },
    ];
    let windows = vec![
        FulfillmentWindow {
            id: "w1".to_string(),
            start_minute: 0,
            end_minute: 60,
            capacity: 100,
        },
        FulfillmentWindow {
            id: "w2".to_string(),
            start_minute: 60,
            end_minute: 120,
            capacity: 50,
        },
    ];
    let allocations = allocate_shipments(shipments.clone(), &windows);
    assert!(!allocations.is_empty(), "allocations should not be empty at idx {}", idx);

    if allocations.len() >= 2 {
        let first_ship = shipments.iter().find(|s| s.id == allocations[0].shipment_id);
        let second_ship = shipments.iter().find(|s| s.id == allocations[1].shipment_id);
        if let (Some(first), Some(second)) = (first_ship, second_ship) {
            assert!(first.priority >= second.priority,
                "first allocation should have >= priority at idx {}", idx);
        }
    }
}

fn run_routing_test(idx: usize) {
    let mut latency: HashMap<String, u32> = HashMap::new();
    latency.insert("hub-a".to_string(), (idx as u32 % 100) + 10);
    latency.insert("hub-b".to_string(), ((idx * 7) as u32 % 100) + 10);
    latency.insert("hub-c".to_string(), ((idx * 11) as u32 % 100) + 10);

    let candidates = vec!["hub-a".to_string(), "hub-b".to_string(), "hub-c".to_string()];
    let blocked = if idx % 5 == 0 { vec!["hub-a".to_string()] } else { vec![] };

    let selected = select_hub(&candidates, &latency, &blocked);
    assert!(selected.is_some(), "should select a hub at idx {}", idx);
    if !blocked.is_empty() {
        assert_ne!(selected.as_ref().unwrap(), &blocked[0],
            "should not select blocked hub at idx {}", idx);
    }
}

fn run_policy_test(idx: usize) {
    let shipments = vec![
        Shipment {
            id: format!("ship-{}", idx),
            lane: "north".to_string(),
            units: (idx as u32 % 100) + 10,
            priority: ((idx % 5) + 1) as u8,
        },
    ];
    let incidents = vec![
        Incident {
            id: format!("inc-{}", idx),
            severity: ((idx % 3) + 1) as u8,
            domain: "logistics".to_string(),
        },
    ];
    let temp = (idx as f64 % 50.0) - 10.0;
    let score = risk_score(&shipments, &incidents, temp);
    assert!(score >= 0.0 && score <= 100.0, "risk score should be in [0, 100] at idx {}", idx);

    let tier = compliance_tier(score);
    assert!(["auto", "ops-review", "board-review"].contains(&tier),
        "compliance tier should be valid at idx {}", idx);

    // Verify compliance tier thresholds are correctly calibrated
    assert_eq!(compliance_tier(80.0), "board-review",
        "score 80 should trigger board-review at idx {}", idx);
    assert_eq!(compliance_tier(60.0), "ops-review",
        "score 60 should trigger ops-review at idx {}", idx);
    assert_eq!(compliance_tier(20.0), "auto",
        "score 20 should be auto at idx {}", idx);
}

fn run_queue_test(idx: usize) {
    let queue_items = vec![
        QueueItem {
            id: format!("q-{}-1", idx),
            severity: ((idx % 5) + 1) as u8,
            waited_seconds: (idx as u32 % 600) + 10,
        },
        QueueItem {
            id: format!("q-{}-2", idx),
            severity: (((idx * 3) % 5) + 1) as u8,
            waited_seconds: ((idx * 2) as u32 % 600) + 10,
        },
    ];
    let ordered = order_queue(&queue_items);
    assert_eq!(ordered.len(), queue_items.len(), "ordered queue should have same length at idx {}", idx);

    if ordered.len() >= 2 {
        let w0 = (ordered[0].severity as u32) * 10 + (ordered[0].waited_seconds.min(900) / 30);
        let w1 = (ordered[1].severity as u32) * 10 + (ordered[1].waited_seconds.min(900) / 30);
        assert!(w0 >= w1, "queue should be ordered by weight descending at idx {}", idx);
    }
}

fn run_statistics_test(idx: usize) {
    let values: Vec<u32> = (0..10).map(|i| ((idx + i) as u32 % 100) + 1).collect();
    let p50 = percentile(&values, 50);
    let p99 = percentile(&values, 99);
    assert!(p50 <= p99, "p50 should be <= p99 for monotonic percentiles at idx {}", idx);
}

fn run_resilience_test(idx: usize) {
    let backoff = retry_backoff((idx as u32 % 5) + 1, 100, 5000);
    assert!(backoff <= 5000, "backoff should be capped at idx {}", idx);

    let budget = replay_budget((idx as u32 % 100) + 1, 10);
    assert!(budget <= 140, "replay budget should be bounded at idx {}", idx);
}

fn run_security_test(idx: usize) {
    let payload = format!("manifest-{}", idx);
    let secret = "test-secret-key-1234";
    let sig = simple_signature(&payload, secret);
    assert!(validate_signature(&payload, &sig, secret),
        "signature should validate at idx {}", idx);
    assert!(!validate_signature(&payload, "invalid", secret),
        "invalid signature should not validate at idx {}", idx);
    // Near-match: single byte difference must be rejected (constant-time comparison)
    let mut near_bytes = sig.as_bytes().to_vec();
    if near_bytes.len() > 2 {
        near_bytes[2] = if near_bytes[2] == b'0' { b'1' } else { b'0' };
        let near_match = String::from_utf8(near_bytes).unwrap();
        assert!(!validate_signature(&payload, &near_match, secret),
            "near-match signature (1 byte diff) should be rejected at idx {}", idx);
    }
}

fn run_economics_test(idx: usize) {
    let shipments = vec![
        Shipment {
            id: format!("ship-{}", idx),
            lane: "east".to_string(),
            units: (idx as u32 % 100) + 10,
            priority: 3,
        },
    ];
    let cost = projected_cost_cents(&shipments, 100.0, 1.1);
    assert!(cost > 0, "cost should be positive at idx {}", idx);

    let margin = margin_ratio(cost + 5000, cost);
    assert!(margin >= 0.0 && margin <= 1.0, "margin should be in [0, 1] at idx {}", idx);

    // Surge multiplier must scale cost proportionally
    let cost_base = projected_cost_cents(&shipments, 100.0, 1.0);
    let cost_doubled = projected_cost_cents(&shipments, 100.0, 2.0);
    if cost_base > 0 {
        let ratio = cost_doubled as f64 / cost_base as f64;
        assert!((ratio - 2.0).abs() < 0.02,
            "2.0x surge should double cost at idx {}, got ratio {:.4}", idx, ratio);
    }
}

// Generate test functions - each runs ITERATIONS cases
macro_rules! matrix_batch {
    ($name:ident, $base:expr, $func:ident) => {
        #[test]
        fn $name() {
            for i in 0..ITERATIONS {
                $func($base + i);
            }
        }
    };
}

// Allocator tests (10 batches x 100 = 1000 cases)
matrix_batch!(allocator_batch_00, 0, run_allocator_test);
matrix_batch!(allocator_batch_01, 100, run_allocator_test);
matrix_batch!(allocator_batch_02, 200, run_allocator_test);
matrix_batch!(allocator_batch_03, 300, run_allocator_test);
matrix_batch!(allocator_batch_04, 400, run_allocator_test);
matrix_batch!(allocator_batch_05, 500, run_allocator_test);
matrix_batch!(allocator_batch_06, 600, run_allocator_test);
matrix_batch!(allocator_batch_07, 700, run_allocator_test);
matrix_batch!(allocator_batch_08, 800, run_allocator_test);
matrix_batch!(allocator_batch_09, 900, run_allocator_test);

// Routing tests
matrix_batch!(routing_batch_00, 0, run_routing_test);
matrix_batch!(routing_batch_01, 100, run_routing_test);
matrix_batch!(routing_batch_02, 200, run_routing_test);
matrix_batch!(routing_batch_03, 300, run_routing_test);
matrix_batch!(routing_batch_04, 400, run_routing_test);
matrix_batch!(routing_batch_05, 500, run_routing_test);
matrix_batch!(routing_batch_06, 600, run_routing_test);
matrix_batch!(routing_batch_07, 700, run_routing_test);
matrix_batch!(routing_batch_08, 800, run_routing_test);
matrix_batch!(routing_batch_09, 900, run_routing_test);

// Policy tests
matrix_batch!(policy_batch_00, 0, run_policy_test);
matrix_batch!(policy_batch_01, 100, run_policy_test);
matrix_batch!(policy_batch_02, 200, run_policy_test);
matrix_batch!(policy_batch_03, 300, run_policy_test);
matrix_batch!(policy_batch_04, 400, run_policy_test);
matrix_batch!(policy_batch_05, 500, run_policy_test);
matrix_batch!(policy_batch_06, 600, run_policy_test);
matrix_batch!(policy_batch_07, 700, run_policy_test);
matrix_batch!(policy_batch_08, 800, run_policy_test);
matrix_batch!(policy_batch_09, 900, run_policy_test);

// Queue tests
matrix_batch!(queue_batch_00, 0, run_queue_test);
matrix_batch!(queue_batch_01, 100, run_queue_test);
matrix_batch!(queue_batch_02, 200, run_queue_test);
matrix_batch!(queue_batch_03, 300, run_queue_test);
matrix_batch!(queue_batch_04, 400, run_queue_test);
matrix_batch!(queue_batch_05, 500, run_queue_test);
matrix_batch!(queue_batch_06, 600, run_queue_test);
matrix_batch!(queue_batch_07, 700, run_queue_test);
matrix_batch!(queue_batch_08, 800, run_queue_test);
matrix_batch!(queue_batch_09, 900, run_queue_test);

// Statistics tests
matrix_batch!(statistics_batch_00, 0, run_statistics_test);
matrix_batch!(statistics_batch_01, 100, run_statistics_test);
matrix_batch!(statistics_batch_02, 200, run_statistics_test);
matrix_batch!(statistics_batch_03, 300, run_statistics_test);
matrix_batch!(statistics_batch_04, 400, run_statistics_test);
matrix_batch!(statistics_batch_05, 500, run_statistics_test);
matrix_batch!(statistics_batch_06, 600, run_statistics_test);
matrix_batch!(statistics_batch_07, 700, run_statistics_test);
matrix_batch!(statistics_batch_08, 800, run_statistics_test);
matrix_batch!(statistics_batch_09, 900, run_statistics_test);

// Resilience tests
matrix_batch!(resilience_batch_00, 0, run_resilience_test);
matrix_batch!(resilience_batch_01, 100, run_resilience_test);
matrix_batch!(resilience_batch_02, 200, run_resilience_test);
matrix_batch!(resilience_batch_03, 300, run_resilience_test);
matrix_batch!(resilience_batch_04, 400, run_resilience_test);
matrix_batch!(resilience_batch_05, 500, run_resilience_test);
matrix_batch!(resilience_batch_06, 600, run_resilience_test);
matrix_batch!(resilience_batch_07, 700, run_resilience_test);
matrix_batch!(resilience_batch_08, 800, run_resilience_test);
matrix_batch!(resilience_batch_09, 900, run_resilience_test);

// Security tests
matrix_batch!(security_batch_00, 0, run_security_test);
matrix_batch!(security_batch_01, 100, run_security_test);
matrix_batch!(security_batch_02, 200, run_security_test);
matrix_batch!(security_batch_03, 300, run_security_test);
matrix_batch!(security_batch_04, 400, run_security_test);
matrix_batch!(security_batch_05, 500, run_security_test);
matrix_batch!(security_batch_06, 600, run_security_test);
matrix_batch!(security_batch_07, 700, run_security_test);
matrix_batch!(security_batch_08, 800, run_security_test);
matrix_batch!(security_batch_09, 900, run_security_test);

// Economics tests
matrix_batch!(economics_batch_00, 0, run_economics_test);
matrix_batch!(economics_batch_01, 100, run_economics_test);
matrix_batch!(economics_batch_02, 200, run_economics_test);
matrix_batch!(economics_batch_03, 300, run_economics_test);
matrix_batch!(economics_batch_04, 400, run_economics_test);
matrix_batch!(economics_batch_05, 500, run_economics_test);
matrix_batch!(economics_batch_06, 600, run_economics_test);
matrix_batch!(economics_batch_07, 700, run_economics_test);
matrix_batch!(economics_batch_08, 800, run_economics_test);
matrix_batch!(economics_batch_09, 900, run_economics_test);

// ---------------------------------------------------------------------------
// Allocator: zone allocation and overflow reallocation
// ---------------------------------------------------------------------------

#[test]
fn zone_allocation_includes_boundary_temp() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 10,
        priority: 3,
    }];
    let zones = vec![Zone {
        id: "z1".into(),
        temp_min_c: -5.0,
        temp_max_c: 4.0,
        capacity: 20,
    }];
    let allocs = allocate_to_zones(&shipments, &zones, 4.0);
    assert!(
        !allocs.is_empty(),
        "zone with temp_max_c equal to required_temp should be eligible"
    );
    assert_eq!(allocs[0].units, 10);
}

#[test]
fn zone_allocation_empty_when_no_eligible_zones() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 10,
        priority: 3,
    }];
    let zones = vec![Zone {
        id: "z1".into(),
        temp_min_c: -5.0,
        temp_max_c: 0.0,
        capacity: 20,
    }];
    let allocs = allocate_to_zones(&shipments, &zones, 10.0);
    assert!(allocs.is_empty());
}

#[test]
fn reallocate_uses_all_alternate_windows() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 20,
        priority: 3,
    }];
    let windows = vec![
        FulfillmentWindow {
            id: "overflow".into(),
            start_minute: 0,
            end_minute: 30,
            capacity: 5,
        },
        FulfillmentWindow {
            id: "w2".into(),
            start_minute: 30,
            end_minute: 60,
            capacity: 15,
        },
        FulfillmentWindow {
            id: "w3".into(),
            start_minute: 60,
            end_minute: 90,
            capacity: 10,
        },
    ];
    let allocs = reallocate_on_overflow(&shipments, &windows, "overflow");
    let total_assigned: u32 = allocs.iter().map(|a| a.units).sum();
    assert_eq!(
        total_assigned, 20,
        "should allocate across all non-overflow windows, got {} units",
        total_assigned
    );
}

#[test]
fn reallocate_empty_when_only_overflow() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 10,
        priority: 3,
    }];
    let windows = vec![FulfillmentWindow {
        id: "overflow".into(),
        start_minute: 0,
        end_minute: 30,
        capacity: 50,
    }];
    let allocs = reallocate_on_overflow(&shipments, &windows, "overflow");
    assert!(allocs.is_empty());
}

// ---------------------------------------------------------------------------
// Economics: SLA penalties and break-even analysis
// ---------------------------------------------------------------------------

#[test]
fn sla_penalty_based_on_cost_not_time() {
    let penalty = sla_penalty_cents(90, 60, 50_000);
    assert_eq!(
        penalty, 1000,
        "SLA penalty should be 2% of base cost (50000), got {}",
        penalty
    );
}

#[test]
fn sla_no_penalty_when_on_time() {
    let penalty = sla_penalty_cents(30, 60, 10_000);
    assert_eq!(penalty, 0);
}

#[test]
fn break_even_accounts_for_variable_cost() {
    let result = break_even_units(10_000, 10.0, 6.0);
    assert_eq!(
        result, 2500,
        "break-even should account for variable costs, got {}",
        result
    );
}

#[test]
fn break_even_infinite_when_costs_exceed_revenue() {
    let result = break_even_units(1000, 5.0, 8.0);
    assert_eq!(result, u32::MAX);
}

// ---------------------------------------------------------------------------
// Policy: compound risk and escalation
// ---------------------------------------------------------------------------

#[test]
fn compound_risk_with_correlated_incidents() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 10,
        priority: 2,
    }];
    let incidents = vec![
        Incident {
            id: "i1".into(),
            severity: 3,
            domain: "cold-chain".into(),
        },
        Incident {
            id: "i2".into(),
            severity: 4,
            domain: "cold-chain".into(),
        },
        Incident {
            id: "i3".into(),
            severity: 2,
            domain: "cold-chain".into(),
        },
    ];
    let score = compound_risk(&shipments, &incidents, 20.0);
    let base = risk_score(&shipments, &incidents, 20.0);
    let expected_factor = 3.0_f64 * 1.5_f64.powi(2);
    assert!(
        (score - base - expected_factor).abs() < 0.01,
        "compound risk should use exponential compounding, got {}, expected base {} + {}",
        score,
        base,
        expected_factor
    );
}

#[test]
fn compound_risk_single_domain_no_extra() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 10,
        priority: 2,
    }];
    let incidents = vec![Incident {
        id: "i1".into(),
        severity: 3,
        domain: "routing".into(),
    }];
    let score = compound_risk(&shipments, &incidents, 20.0);
    let base = risk_score(&shipments, &incidents, 20.0);
    assert!(
        (score - base).abs() < 0.001,
        "single incident per domain should add no correlation factor"
    );
}

#[test]
fn escalation_higher_on_weekend() {
    let weekday = escalation_level(60.0, 3, false);
    let weekend = escalation_level(60.0, 3, true);
    assert!(
        weekend > weekday,
        "weekend should escalate higher (fewer staff), weekday={}, weekend={}",
        weekday,
        weekend
    );
}

#[test]
fn escalation_base_levels() {
    assert_eq!(escalation_level(10.0, 0, false), 1);
    assert_eq!(escalation_level(60.0, 0, false), 3);
    assert_eq!(escalation_level(90.0, 0, false), 4);
}

// ---------------------------------------------------------------------------
// Routing: cold-chain validation and hub fallback
// ---------------------------------------------------------------------------

#[test]
fn cold_chain_validates_cumulative_exposure() {
    let legs = vec![
        TransitLeg {
            from_hub: "a".into(),
            to_hub: "b".into(),
            duration_minutes: 40,
            ambient_temp_c: 12.0,
        },
        TransitLeg {
            from_hub: "b".into(),
            to_hub: "c".into(),
            duration_minutes: 40,
            ambient_temp_c: 15.0,
        },
        TransitLeg {
            from_hub: "c".into(),
            to_hub: "d".into(),
            duration_minutes: 40,
            ambient_temp_c: 11.0,
        },
    ];
    let valid = validate_cold_chain(&legs, 60, (2.0, 8.0));
    assert!(
        !valid,
        "cumulative thermal exposure of 120 min exceeds 60 min limit"
    );
}

#[test]
fn cold_chain_passes_single_safe_leg() {
    let legs = vec![TransitLeg {
        from_hub: "a".into(),
        to_hub: "b".into(),
        duration_minutes: 30,
        ambient_temp_c: 4.0,
    }];
    let valid = validate_cold_chain(&legs, 60, (2.0, 8.0));
    assert!(valid);
}

#[test]
fn select_hub_uses_fallback_when_all_blocked() {
    let candidates = vec!["hub-a".to_string(), "hub-b".to_string()];
    let latency = HashMap::from([("hub-a".to_string(), 50_u32), ("hub-b".to_string(), 60)]);
    let blocked = vec!["hub-a".to_string(), "hub-b".to_string()];

    let selected = select_hub_with_fallback(&candidates, &latency, &blocked, "fallback-hub");
    assert_eq!(
        selected, "fallback-hub",
        "should return fallback when all candidates blocked, got {}",
        selected
    );
}

#[test]
fn select_hub_prefers_lowest_latency() {
    let candidates = vec!["hub-a".to_string(), "hub-b".to_string(), "hub-c".to_string()];
    let latency = HashMap::from([
        ("hub-a".to_string(), 80_u32),
        ("hub-b".to_string(), 30),
        ("hub-c".to_string(), 60),
    ]);
    let selected = select_hub_with_fallback(&candidates, &latency, &[], "fallback");
    assert_eq!(selected, "hub-b");
}

// ---------------------------------------------------------------------------
// Queue: batch dequeue and merge
// ---------------------------------------------------------------------------

#[test]
fn batch_dequeue_cost_independent_of_wait_time() {
    let short_wait = vec![QueueItem {
        id: "a".into(),
        severity: 2,
        waited_seconds: 0,
    }];
    let long_wait = vec![QueueItem {
        id: "b".into(),
        severity: 2,
        waited_seconds: 300,
    }];
    let budget = 11; // severity*5 + 1 = 11
    let (p1, _) = batch_dequeue(&short_wait, budget);
    let (p2, _) = batch_dequeue(&long_wait, budget);
    assert_eq!(p1.len(), 1, "short wait item should be processed");
    assert_eq!(
        p2.len(),
        1,
        "long wait item should be processed with same budget (cost should not depend on wait time)"
    );
}

#[test]
fn batch_dequeue_empty_items() {
    let (processed, remaining) = batch_dequeue(&[], 100);
    assert!(processed.is_empty());
    assert!(remaining.is_empty());
}

#[test]
fn merge_queues_stable_on_equal_weight() {
    let q1 = vec![QueueItem {
        id: "q1-a".into(),
        severity: 3,
        waited_seconds: 60,
    }];
    let q2 = vec![QueueItem {
        id: "q2-a".into(),
        severity: 3,
        waited_seconds: 60,
    }];
    let merged = merge_priority_queues(&q1, &q2);
    assert_eq!(
        merged[0].id, "q1-a",
        "q1 items should precede q2 with equal weight (stable merge)"
    );
}

#[test]
fn merge_queues_single_queue() {
    let q1 = vec![
        QueueItem {
            id: "a".into(),
            severity: 5,
            waited_seconds: 100,
        },
        QueueItem {
            id: "b".into(),
            severity: 2,
            waited_seconds: 50,
        },
    ];
    let merged = merge_priority_queues(&q1, &[]);
    assert_eq!(merged.len(), 2);
    assert_eq!(merged[0].id, "a");
}

// ---------------------------------------------------------------------------
// Resilience: circuit breaker and adaptive backoff
// ---------------------------------------------------------------------------

#[test]
fn circuit_breaker_resets_failure_count_on_recovery() {
    let mut cb = CircuitBreaker::new(3, 2);

    cb.record_failure();
    cb.record_failure();
    cb.record_failure();
    assert_eq!(cb.state, BreakerState::Open);

    cb.attempt_reset();
    assert_eq!(cb.state, BreakerState::HalfOpen);

    cb.record_success();
    cb.record_success();
    assert_eq!(cb.state, BreakerState::Closed);

    cb.record_failure();
    assert_eq!(
        cb.state,
        BreakerState::Closed,
        "single failure after recovery should not re-trip breaker"
    );
}

#[test]
fn circuit_breaker_basic_open() {
    let mut cb = CircuitBreaker::new(3, 2);
    cb.record_failure();
    cb.record_failure();
    assert_eq!(cb.state, BreakerState::Closed);
    cb.record_failure();
    assert_eq!(cb.state, BreakerState::Open);
    assert!(!cb.can_execute());
}

#[test]
fn circuit_breaker_can_execute_states() {
    let mut cb = CircuitBreaker::new(3, 2);
    assert!(cb.can_execute());
    cb.record_failure();
    cb.record_failure();
    cb.record_failure();
    assert!(!cb.can_execute());
    cb.attempt_reset();
    assert!(cb.can_execute());
}

#[test]
fn adaptive_backoff_longer_when_failing() {
    let healthy = adaptive_retry_backoff(2, 100, 5000, 0.9);
    let failing = adaptive_retry_backoff(2, 100, 5000, 0.1);
    assert!(
        failing > healthy,
        "backoff should be longer when success rate is low, healthy={}, failing={}",
        healthy,
        failing
    );
}

#[test]
fn adaptive_backoff_caps_at_max() {
    let result = adaptive_retry_backoff(10, 500, 3000, 0.5);
    assert!(result <= 3000, "should not exceed cap");
}

// ---------------------------------------------------------------------------
// Statistics: EMA and anomaly detection
// ---------------------------------------------------------------------------

#[test]
fn ema_gives_more_weight_to_recent() {
    let values = vec![10.0, 10.0, 10.0, 100.0];
    let ema = exponential_moving_average(&values, 2);
    assert!(
        ema[3] > 60.0,
        "EMA should weight recent values heavily with span=2, got {}",
        ema[3]
    );
}

#[test]
fn ema_single_value() {
    let ema = exponential_moving_average(&[42.0], 5);
    assert_eq!(ema.len(), 1);
    assert!((ema[0] - 42.0).abs() < f64::EPSILON);
}

#[test]
fn detect_anomalies_uses_sample_std_dev() {
    let anomalies = detect_anomalies(&[10.0, 10.0, 10.0, 10.0, 50.0], 1.95);
    assert!(
        anomalies.is_empty(),
        "with sample std dev, no values should exceed 1.95-sigma threshold, got {:?}",
        anomalies
    );
}

#[test]
fn detect_anomalies_constant_no_anomalies() {
    let anomalies = detect_anomalies(&[5.0, 5.0, 5.0, 5.0, 5.0], 2.0);
    assert!(anomalies.is_empty());
}

// ---------------------------------------------------------------------------
// Workflow: fulfillment plan and state machine
// ---------------------------------------------------------------------------

#[test]
fn fulfillment_plan_averages_risk_across_batches() {
    let batch1 = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 5,
        priority: 1,
    }];
    let batch2 = vec![Shipment {
        id: "s2".into(),
        lane: "l2".into(),
        units: 100,
        priority: 5,
    }];
    let windows = vec![FulfillmentWindow {
        id: "w1".into(),
        start_minute: 0,
        end_minute: 60,
        capacity: 200,
    }];
    let hubs = HashMap::from([("h1".to_string(), 50_u32)]);

    let score1 = risk_score(&batch1, &[], 20.0);
    let score2 = risk_score(&batch2, &[], 20.0);
    let expected_avg = (score1 + score2) / 2.0;

    let plan = plan_fulfillment(&[batch1, batch2], &windows, &[], 20.0, &hubs);

    assert!(
        (plan.combined_risk - expected_avg).abs() < 0.01,
        "combined risk should be average ({:.3}) not max ({:.3}), got {:.3}",
        expected_avg,
        score2,
        plan.combined_risk
    );
}

#[test]
fn fulfillment_plan_margin_is_revenue_based() {
    let batch = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 100,
        priority: 3,
    }];
    let windows = vec![FulfillmentWindow {
        id: "w1".into(),
        start_minute: 0,
        end_minute: 60,
        capacity: 200,
    }];
    let hubs = HashMap::from([("h1".to_string(), 50_u32)]);

    let plan = plan_fulfillment(&[batch], &windows, &[], 20.0, &hubs);

    assert!(
        plan.overall_margin >= 0.0 && plan.overall_margin <= 1.0,
        "margin ratio should be in [0, 1], got {}",
        plan.overall_margin
    );
}

#[test]
fn state_machine_rejects_held_to_delivered() {
    let mut sm = ShipmentStateMachine::new();
    sm.transition(ShipmentState::Queued).unwrap();
    sm.transition(ShipmentState::Allocated).unwrap();
    sm.transition(ShipmentState::Held).unwrap();

    let result = sm.transition(ShipmentState::Delivered);
    assert!(
        result.is_err(),
        "held shipments must be re-queued before delivery"
    );
}

#[test]
fn can_deliver_requires_in_transit() {
    let mut sm = ShipmentStateMachine::new();
    sm.transition(ShipmentState::Queued).unwrap();
    sm.transition(ShipmentState::Allocated).unwrap();

    assert!(
        !sm.can_deliver(),
        "should not be deliverable from Allocated state"
    );

    sm.transition(ShipmentState::InTransit).unwrap();
    assert!(sm.can_deliver());
}

#[test]
fn state_machine_valid_path_to_delivered() {
    let mut sm = ShipmentStateMachine::new();
    assert!(sm.transition(ShipmentState::Queued).is_ok());
    assert!(sm.transition(ShipmentState::Allocated).is_ok());
    assert!(sm.transition(ShipmentState::InTransit).is_ok());
    assert!(sm.transition(ShipmentState::Delivered).is_ok());
    assert_eq!(sm.state, ShipmentState::Delivered);
}

#[test]
fn state_machine_tracks_history() {
    let mut sm = ShipmentStateMachine::new();
    sm.transition(ShipmentState::Queued).unwrap();
    sm.transition(ShipmentState::Allocated).unwrap();
    sm.transition(ShipmentState::Held).unwrap();
    sm.transition(ShipmentState::Queued).unwrap();

    assert_eq!(
        sm.history,
        vec![
            ShipmentState::Pending,
            ShipmentState::Queued,
            ShipmentState::Allocated,
            ShipmentState::Held,
            ShipmentState::Queued,
        ]
    );
}

#[test]
fn integration_allocation_routing_policy_chain() {
    let shipments = vec![
        Shipment {
            id: "s1".into(),
            lane: "north".into(),
            units: 50,
            priority: 4,
        },
        Shipment {
            id: "s2".into(),
            lane: "south".into(),
            units: 30,
            priority: 2,
        },
    ];
    let windows = vec![
        FulfillmentWindow {
            id: "w1".into(),
            start_minute: 0,
            end_minute: 60,
            capacity: 40,
        },
        FulfillmentWindow {
            id: "w2".into(),
            start_minute: 60,
            end_minute: 120,
            capacity: 40,
        },
    ];
    let incidents = vec![Incident {
        id: "i1".into(),
        severity: 3,
        domain: "routing".into(),
    }];
    let hubs = HashMap::from([("hub-a".to_string(), 80_u32), ("hub-b".to_string(), 50)]);

    let plan = plan_fulfillment(&[shipments], &windows, &incidents, 18.0, &hubs);

    assert!(
        plan.overall_margin >= 0.0 && plan.overall_margin <= 1.0,
        "overall margin should be in [0, 1], got {}",
        plan.overall_margin
    );
    assert_eq!(plan.primary_hub, "hub-b");
}

// ---------------------------------------------------------------------------
// Zone allocation: deterministic ordering
// ---------------------------------------------------------------------------

#[test]
fn zone_allocation_deterministic_order() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 15,
        priority: 3,
    }];
    let zones = vec![
        Zone {
            id: "z1".into(),
            temp_min_c: 0.0,
            temp_max_c: 10.0,
            capacity: 10,
        },
        Zone {
            id: "z2".into(),
            temp_min_c: -2.0,
            temp_max_c: 6.0,
            capacity: 10,
        },
    ];
    let allocs = allocate_to_zones(&shipments, &zones, 3.0);
    assert!(!allocs.is_empty());
    assert_eq!(
        allocs[0].window_id, "z1",
        "should allocate to zones in deterministic (ID) order, not by proximity"
    );
}

// ---------------------------------------------------------------------------
// Reallocation: temporal ordering preference
// ---------------------------------------------------------------------------

#[test]
fn reallocate_prefers_earliest_window() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 10,
        priority: 3,
    }];
    let windows = vec![
        FulfillmentWindow {
            id: "overflow".into(),
            start_minute: 0,
            end_minute: 30,
            capacity: 50,
        },
        FulfillmentWindow {
            id: "w-early".into(),
            start_minute: 30,
            end_minute: 60,
            capacity: 8,
        },
        FulfillmentWindow {
            id: "w-late".into(),
            start_minute: 60,
            end_minute: 90,
            capacity: 20,
        },
    ];
    let allocs = reallocate_on_overflow(&shipments, &windows, "overflow");
    assert!(!allocs.is_empty());
    assert_eq!(
        allocs[0].window_id, "w-early",
        "should prefer earliest available window for reallocation"
    );
}

// ---------------------------------------------------------------------------
// Queue merge: source priority stability
// ---------------------------------------------------------------------------

#[test]
fn merge_queues_preserves_source_priority() {
    let q1 = vec![QueueItem {
        id: "zebra".into(),
        severity: 3,
        waited_seconds: 60,
    }];
    let q2 = vec![QueueItem {
        id: "alpha".into(),
        severity: 3,
        waited_seconds: 60,
    }];
    let merged = merge_priority_queues(&q1, &q2);
    assert_eq!(
        merged[0].id, "zebra",
        "q1 items should always precede q2 on equal weight (stable merge), got {}",
        merged[0].id
    );
}

// ---------------------------------------------------------------------------
// Policy: weekend escalation edge case
// ---------------------------------------------------------------------------

#[test]
fn escalation_weekend_with_zero_incidents() {
    let weekday = escalation_level(60.0, 0, false);
    let weekend = escalation_level(60.0, 0, true);
    assert!(
        weekend > weekday,
        "weekend should always escalate higher even with zero incidents, weekday={}, weekend={}",
        weekday,
        weekend
    );
}

// ---------------------------------------------------------------------------
// Cold-chain: total cumulative exposure across safe legs
// ---------------------------------------------------------------------------

#[test]
fn cold_chain_total_exposure_across_safe_legs() {
    let legs = vec![
        TransitLeg {
            from_hub: "a".into(),
            to_hub: "b".into(),
            duration_minutes: 40,
            ambient_temp_c: 12.0,
        },
        TransitLeg {
            from_hub: "b".into(),
            to_hub: "c".into(),
            duration_minutes: 10,
            ambient_temp_c: 5.0,
        },
        TransitLeg {
            from_hub: "c".into(),
            to_hub: "d".into(),
            duration_minutes: 40,
            ambient_temp_c: 11.0,
        },
    ];
    let valid = validate_cold_chain(&legs, 60, (2.0, 8.0));
    assert!(
        !valid,
        "total cumulative exposure across safe legs should not reset; 80 min total > 60 min limit"
    );
}

// ---------------------------------------------------------------------------
// Workflow: multi-batch schedule with independent capacity
// ---------------------------------------------------------------------------

#[test]
fn multi_batch_schedule_independent_capacity() {
    let batch1 = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 80,
        priority: 3,
    }];
    let batch2 = vec![Shipment {
        id: "s2".into(),
        lane: "l2".into(),
        units: 80,
        priority: 3,
    }];
    let windows = vec![FulfillmentWindow {
        id: "w1".into(),
        start_minute: 0,
        end_minute: 60,
        capacity: 100,
    }];
    let results = multi_batch_schedule(&[batch1, batch2], &windows);
    let batch2_units: u32 = results[1].1.iter().map(|a| a.units).sum();
    assert_eq!(
        batch2_units, 80,
        "each batch should have independent window capacity, batch2 got {} units",
        batch2_units
    );
}

// ---------------------------------------------------------------------------
// Resilience: replay events preserve insertion order
// ---------------------------------------------------------------------------

#[test]
fn replay_events_preserve_insertion_order() {
    let events = vec![
        (100, "deploy".to_string(), 1),
        (100, "audit".to_string(), 2),
        (100, "config".to_string(), 3),
    ];
    let replayed = replay_events_in_order(&events, 0);
    assert_eq!(replayed[0].1, "deploy", "first event should be 'deploy'");
    assert_eq!(replayed[1].1, "audit", "second event should be 'audit'");
    assert_eq!(replayed[2].1, "config", "third event should be 'config'");
}

// ---------------------------------------------------------------------------
// Policy: aggregate risk weighted by volume
// ---------------------------------------------------------------------------

#[test]
fn aggregate_risk_weighted_by_volume() {
    let small_batch = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 1,
        priority: 1,
    }];
    let large_batch = vec![Shipment {
        id: "s2".into(),
        lane: "l2".into(),
        units: 200,
        priority: 5,
    }];
    let incidents = vec![Incident {
        id: "i1".into(),
        severity: 3,
        domain: "logistics".into(),
    }];
    let score = aggregate_risk_by_volume(
        &[small_batch.clone(), large_batch.clone()],
        &incidents,
        20.0,
    );
    let score1 = risk_score(&small_batch, &incidents, 20.0);
    let score2 = risk_score(&large_batch, &incidents, 20.0);
    let simple_avg = (score1 + score2) / 2.0;
    assert!(
        (score - simple_avg).abs() > 0.01,
        "aggregate risk should be weighted by volume, not simple average; got {:.3}, simple avg {:.3}",
        score,
        simple_avg
    );
}

// ---------------------------------------------------------------------------
// Routing: unknown hops should be assumed loaded
// ---------------------------------------------------------------------------

#[test]
fn route_segments_unknown_hops_assumed_loaded() {
    let paths = HashMap::from([(
        "flow1".to_string(),
        vec![
            "hop-a".to_string(),
            "hop-b".to_string(),
            "hop-unknown".to_string(),
        ],
    )]);
    let load = HashMap::from([("hop-a".to_string(), 0.8), ("hop-b".to_string(), 0.3)]);
    let result = route_segments(&paths, &load);
    let flow1 = &result["flow1"];
    assert_ne!(
        flow1[0], "hop-unknown",
        "unknown hops should be assumed loaded (default 1.0), not preferred"
    );
}

// ---------------------------------------------------------------------------
// Economics: surge multiplier should scale cost
// ---------------------------------------------------------------------------

#[test]
fn projected_cost_applies_surge_multiplier() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 100,
        priority: 3,
    }];
    let base = projected_cost_cents(&shipments, 200.0, 1.0);
    let surged = projected_cost_cents(&shipments, 200.0, 1.5);
    assert!(
        (surged as f64 / base as f64 - 1.5).abs() < 0.01,
        "1.5x surge should scale cost by 1.5, got ratio {:.4}",
        surged as f64 / base as f64
    );
}

// ---------------------------------------------------------------------------
// Statistics: rolling SLA and trimmed mean
// ---------------------------------------------------------------------------

#[test]
fn rolling_sla_exact_count() {
    let latencies = vec![10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    let sla = rolling_sla(&latencies, 50);
    assert!(
        (sla - 0.5).abs() < 0.01,
        "SLA for 5/10 within objective should be 0.50, got {:.3}",
        sla
    );
}

#[test]
fn trimmed_mean_excludes_outliers() {
    let values = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0];
    let mean = trimmed_mean(&values, 0.1);
    assert!(
        (mean - 5.5).abs() < 0.01,
        "trimmed mean should exclude outliers and average kept values, got {:.3}",
        mean
    );
}

// ---------------------------------------------------------------------------
// Security: signature validation and step-up auth
// ---------------------------------------------------------------------------

#[test]
fn validate_signature_rejects_near_match() {
    let payload = "test-payload";
    let secret = "secret-key";
    let sig = simple_signature(payload, secret);
    let mut bytes = sig.as_bytes().to_vec();
    bytes[0] = if bytes[0] == b'0' { b'1' } else { b'0' };
    let near_match = String::from_utf8(bytes).unwrap();
    assert!(
        !validate_signature(payload, &near_match, secret),
        "signature with single byte difference should not validate"
    );
}

#[test]
fn requires_step_up_for_admin_regardless_of_units() {
    assert!(
        requires_step_up("admin", 0),
        "admin role should always require step-up authentication regardless of units"
    );
}

#[test]
fn requires_step_up_for_large_shipments() {
    assert!(
        requires_step_up("operator", 501),
        "shipments over 500 units should require step-up regardless of role"
    );
}

// ---------------------------------------------------------------------------
// Queue: round-robin fairness across queues
// ---------------------------------------------------------------------------

#[test]
fn round_robin_drain_fair_across_queues() {
    let q1 = vec![
        QueueItem { id: "a1".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "a2".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "a3".into(), severity: 1, waited_seconds: 0 },
    ];
    let q2 = vec![
        QueueItem { id: "b1".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "b2".into(), severity: 1, waited_seconds: 0 },
        QueueItem { id: "b3".into(), severity: 1, waited_seconds: 0 },
    ];
    let results = round_robin_drain(&[q1, q2], 24);
    assert_eq!(
        results[0].len(),
        results[1].len(),
        "round-robin should process equal items from each queue, got q1={}, q2={}",
        results[0].len(),
        results[1].len()
    );
}

// ---------------------------------------------------------------------------
// Multi-step chain: risk-adjusted allocation
// ---------------------------------------------------------------------------

#[test]
fn risk_adjusted_allocation_uses_deterministic_zone_order() {
    let shipments = vec![Shipment {
        id: "s1".into(),
        lane: "l1".into(),
        units: 30,
        priority: 3,
    }];
    let incidents: Vec<Incident> = (0..10)
        .map(|i| Incident {
            id: format!("i{}", i),
            severity: 5,
            domain: "cold-chain".into(),
        })
        .collect();
    let zones = vec![
        Zone {
            id: "z1".into(),
            temp_min_c: 0.0,
            temp_max_c: 10.0,
            capacity: 20,
        },
        Zone {
            id: "z2".into(),
            temp_min_c: 0.0,
            temp_max_c: 5.0,
            capacity: 40,
        },
    ];
    let allocs = risk_adjusted_allocation(&shipments, &zones, &incidents, 20.0, 3.0);
    assert!(!allocs.is_empty());
    assert_eq!(
        allocs[0].window_id, "z1",
        "should allocate to zones in deterministic ID order"
    );
}
