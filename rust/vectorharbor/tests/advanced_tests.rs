use vectorharbor::allocator::{
    estimate_turnaround, has_conflict, BerthSlot, RollingWindowScheduler,
};
use vectorharbor::contracts::{service_definitions, topological_order};
use vectorharbor::models::{
    create_batch_orders, sla_by_severity, DispatchOrder,
    SEV_CRITICAL, SEV_HIGH, SEV_INFO,
};
use vectorharbor::policy::{next_policy, PolicyEngine};
use vectorharbor::queue::{PriorityQueue, QueueItem, RateLimiter};
use vectorharbor::resilience::{CircuitBreaker, CB_HALF_OPEN, CB_OPEN};
use vectorharbor::security::TokenStore;
use vectorharbor::statistics::{stddev, variance};
use vectorharbor::workflow::WorkflowEngine;

// ---------------------------------------------------------------------------
// Category 1: Latent Bugs
// Bugs that don't cause obvious failures, requiring understanding of
// correctness contracts and data semantics to detect.
// ---------------------------------------------------------------------------

#[test]
fn token_expires_at_exact_boundary() {
    // A token with issued_at=100 and ttl=50 expires at time 150.
    // At time 150, the token MUST be invalid — the TTL window is [100, 150).
    // Using <= instead of < extends the validity window by 1 tick,
    // creating a security vulnerability where expired tokens are accepted.
    let store = TokenStore::new();
    store.store("session-1".into(), "secret-tok".into(), 100, 50);

    // Time 149: still valid (149 < 150)
    assert!(store.validate("session-1", "secret-tok", 149));

    // Time 150: must be EXPIRED (150 is NOT < 150)
    assert!(
        !store.validate("session-1", "secret-tok", 150),
        "token must expire at issued_at + ttl = 150 — \
         accepting expired tokens is a security vulnerability"
    );

    // Time 151: definitely expired
    assert!(!store.validate("session-1", "secret-tok", 151));
}

#[test]
fn token_validate_cleanup_boundary_consistency() {
    // validate() and cleanup() must agree on when a token expires.
    // If validate says expired, cleanup must remove it (and vice versa).
    let store = TokenStore::new();
    store.store("t1".into(), "tok".into(), 0, 100);
    store.store("t2".into(), "tok".into(), 0, 200);

    // At time 100: t1 should be expired, t2 still valid
    let t1_valid = store.validate("t1", "tok", 100);
    let t2_valid = store.validate("t2", "tok", 100);

    // cleanup at the same timestamp should agree with validate
    let removed = store.cleanup(100);

    if t1_valid {
        // If validate says t1 is valid, cleanup should keep it
        assert_eq!(removed, 0, "cleanup must agree with validate: t1 is valid at 100");
    } else {
        // If validate says t1 is expired, cleanup must remove it
        assert_eq!(removed, 1, "cleanup must agree with validate: t1 is expired at 100");
    }
    assert!(t2_valid, "t2 (ttl=200) must still be valid at time 100");
}

#[test]
fn sample_variance_bessel_correction() {
    // Sample variance uses Bessel's correction: divide by (n-1), not n.
    // For the dataset [2, 4, 4, 4, 5, 5, 7, 9]:
    //   mean = 5.0
    //   sum_sq = 9+1+1+1+0+0+4+16 = 32
    //   sample variance = 32/7 ≈ 4.571 (correct, n-1=7)
    //   population variance = 32/8 = 4.0 (incorrect for sample)
    let values = vec![2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
    let v = variance(&values);
    let expected_sample = 32.0 / 7.0; // ≈ 4.571
    let wrong_population = 32.0 / 8.0; // = 4.0

    assert!(
        (v - expected_sample).abs() < 0.01,
        "sample variance should be {:.4} (Bessel's correction), got {:.4}. \
         If you got {:.4}, you're using population variance (dividing by n instead of n-1)",
        expected_sample,
        v,
        wrong_population
    );
}

#[test]
fn stddev_uses_sample_variance() {
    // stddev should be sqrt of sample variance, not population variance.
    let values = vec![10.0, 12.0, 23.0, 23.0, 16.0, 23.0, 21.0, 16.0];
    let s = stddev(&values);
    let v = variance(&values);
    assert!(
        (s - v.sqrt()).abs() < 0.001,
        "stddev should be sqrt(variance)"
    );
    // With Bessel's correction, variance of these values is larger
    // than population variance. Verify it's above the population threshold.
    let n = values.len() as f64;
    let mean_val: f64 = values.iter().sum::<f64>() / n;
    let pop_var: f64 = values.iter().map(|x| (x - mean_val).powi(2)).sum::<f64>() / n;
    assert!(
        v > pop_var,
        "sample variance ({:.4}) must exceed population variance ({:.4})",
        v,
        pop_var
    );
}

// ---------------------------------------------------------------------------
// Category 2: Domain Logic Bugs
// Require understanding of maritime scheduling semantics
// ---------------------------------------------------------------------------

#[test]
fn berth_adjacent_slots_conflict_at_boundary() {
    // In maritime scheduling, berth hours are inclusive intervals.
    // Slot [0,6] means the berth is occupied THROUGH hour 6.
    // Slot [6,12] starts AT hour 6 — this creates a conflict at the handoff point.
    // A vessel cannot begin docking at the same hour another is still present.
    let slot_a = BerthSlot {
        berth_id: "B1".into(),
        start_hour: 0,
        end_hour: 6,
        occupied: true,
        vessel_id: Some("V1".into()),
    };
    let slot_b = BerthSlot {
        berth_id: "B1".into(),
        start_hour: 6,
        end_hour: 12,
        occupied: false,
        vessel_id: None,
    };
    assert!(
        has_conflict(&slot_a, &slot_b),
        "slots sharing boundary hour 6 must conflict — \
         vessel V1 occupies hour 6, new vessel cannot start at hour 6"
    );
}

#[test]
fn berth_back_to_back_slots_same_hour() {
    // Two slots on the same berth where one ends and another begins at
    // the same hour must be detected as conflicting. This is the most
    // common scheduling collision in port operations.
    let departing = BerthSlot {
        berth_id: "Dock-A".into(),
        start_hour: 8,
        end_hour: 14,
        occupied: true,
        vessel_id: Some("MV-Cargo".into()),
    };
    let arriving = BerthSlot {
        berth_id: "Dock-A".into(),
        start_hour: 14,
        end_hour: 20,
        occupied: false,
        vessel_id: None,
    };
    assert!(
        has_conflict(&departing, &arriving),
        "departing vessel at hour 14 conflicts with arriving vessel at hour 14 — \
         berth turnaround requires at least 1 hour gap"
    );
}

#[test]
fn turnaround_rounds_up_partial_batches() {
    // Container processing happens in batches of 500. A vessel with 501 containers
    // requires 2 full batch cycles, not 1. Using floor() would underestimate by
    // an entire cycle, creating dangerous scheduling gaps.
    let turn_501 = estimate_turnaround(501, false);
    let turn_500 = estimate_turnaround(500, false);
    assert!(
        turn_501 > turn_500,
        "501 containers ({} hours) must take longer than 500 containers ({} hours) — \
         partial batches require a full cycle",
        turn_501,
        turn_500
    );
}

#[test]
fn turnaround_partial_batch_includes_full_cycle() {
    // 750 containers = 1.5 batches → must round to 2 cycles
    let turn = estimate_turnaround(750, false);
    assert!(
        (turn - 2.0).abs() < 0.01,
        "750 containers should require 2 batch cycles (ceil(750/500)=2), got {}",
        turn
    );

    // Hazmat multiplier applies after batch rounding
    let hazmat_turn = estimate_turnaround(750, true);
    assert!(
        (hazmat_turn - 3.0).abs() < 0.01,
        "750 hazmat containers: 2 cycles * 1.5 = 3 hours, got {}",
        hazmat_turn
    );
}

// ---------------------------------------------------------------------------
// Category 3: Multi-step Bugs
// 3-step dependency chain: fixing #1 reveals #2, fixing #2 reveals #3.
// Chain: can_transition → active_count → audit_log
// ---------------------------------------------------------------------------

#[test]
fn workflow_departed_can_arrive() {
    // Step 1: The fundamental transition from departed to arrived must work.
    // Without this, vessels are stuck at sea — a critical workflow defect.
    let engine = WorkflowEngine::new();
    engine.register("vessel-1");
    engine.transition("vessel-1", "allocated", 100);
    engine.transition("vessel-1", "departed", 200);

    let r = engine.transition("vessel-1", "arrived", 300);
    assert!(
        r.success,
        "departed -> arrived must succeed: {:?}",
        r.error
    );
    assert!(engine.is_terminal("vessel-1"));
}

#[test]
fn active_count_decreases_on_arrival() {
    // Step 2 (masked by Step 1): After fixing departed→arrived,
    // active_count must correctly decrease when entities reach terminal states.
    // With the filter inverted, active_count counts terminal entities instead.
    let engine = WorkflowEngine::new();
    engine.register("v1");
    engine.register("v2");
    engine.register("v3");
    assert_eq!(engine.active_count(), 3);

    // Complete v1's lifecycle
    engine.transition("v1", "allocated", 1);
    engine.transition("v1", "departed", 2);
    engine.transition("v1", "arrived", 3);

    assert_eq!(
        engine.active_count(),
        2,
        "after v1 arrives (terminal), only v2 and v3 should be active"
    );

    // Cancel v2
    engine.transition("v2", "cancelled", 4);
    assert_eq!(
        engine.active_count(),
        1,
        "after v2 cancelled (terminal), only v3 should be active"
    );
}

#[test]
fn audit_log_shows_correct_transition_direction() {
    // Step 3 (masked by Steps 1+2): After fixing transitions and counting,
    // the audit log must show transitions in the correct direction.
    // "queued -> allocated" must NOT appear as "allocated -> queued".
    let engine = WorkflowEngine::new();
    engine.register("ship-1");
    engine.transition("ship-1", "allocated", 100);
    engine.transition("ship-1", "departed", 200);
    engine.transition("ship-1", "arrived", 300);

    let log = engine.audit_log();
    assert_eq!(log.len(), 3);

    // Each log entry has format: [timestamp] FROM -> TO (entity: ID)
    // Verify the FROM state appears before the arrow
    assert!(
        log[0].contains("queued -> allocated"),
        "first transition should be 'queued -> allocated', got: {}",
        log[0]
    );
    assert!(
        log[1].contains("allocated -> departed"),
        "second transition should be 'allocated -> departed', got: {}",
        log[1]
    );
    assert!(
        log[2].contains("departed -> arrived"),
        "third transition should be 'departed -> arrived', got: {}",
        log[2]
    );
}

#[test]
fn multi_entity_lifecycle_with_audit_trail() {
    // Full integration: multiple entities going through lifecycle,
    // with active_count tracking and audit log verification.
    // Exercises all 3 bugs in the chain.
    let engine = WorkflowEngine::new();
    engine.register("alpha");
    engine.register("beta");

    engine.transition("alpha", "allocated", 10);
    engine.transition("beta", "allocated", 11);
    engine.transition("alpha", "departed", 20);
    engine.transition("alpha", "arrived", 30);

    assert_eq!(engine.active_count(), 1, "only beta is active");

    let log = engine.audit_log();
    // Verify chronological ordering and direction
    for entry in &log {
        assert!(
            entry.contains(" -> "),
            "audit entries must contain transition arrow"
        );
        // Verify no entry has the pattern "allocated -> queued" (reversed)
        assert!(
            !entry.contains("allocated -> queued"),
            "audit log must not reverse transitions: {}",
            entry
        );
    }
}

// ---------------------------------------------------------------------------
// Category 4: State Machine Bugs
// Incorrect transition semantics that require understanding of state machine
// invariants and recovery protocols.
// ---------------------------------------------------------------------------

#[test]
fn policy_escalation_caps_at_halted() {
    // The policy state machine has a ceiling: "halted" is the maximum level.
    // Escalating from halted must be a no-op, NOT wrap around to normal.
    // Wrapping would silently downgrade from maximum alert to no alert.
    assert_eq!(next_policy("halted", 5), "halted",
        "escalating from halted must stay at halted, not wrap to normal");
}

#[test]
fn policy_engine_saturates_at_max_escalation() {
    // Repeated escalation must converge to halted and stay there.
    let engine = PolicyEngine::new();
    engine.escalate(3); // normal -> watch
    engine.escalate(3); // watch -> restricted
    engine.escalate(3); // restricted -> halted
    assert_eq!(engine.current(), "halted");

    // Further escalations must not change state
    engine.escalate(100);
    assert_eq!(
        engine.current(),
        "halted",
        "policy must not wrap around from halted"
    );
    engine.escalate(1);
    assert_eq!(
        engine.current(),
        "halted",
        "any further escalation from halted must be no-op"
    );
}

#[test]
fn circuit_breaker_half_open_single_failure_trips() {
    // In the half_open (probationary) state, a SINGLE failure must immediately
    // reopen the circuit. The half_open state exists to test if the downstream
    // service has recovered — if it hasn't, we need to trip immediately,
    // not wait for failure_threshold failures like in closed state.
    let cb = CircuitBreaker::new(5, 2); // high threshold in closed state

    // Drive to open, then half_open
    for _ in 0..5 {
        cb.record_failure();
    }
    assert_eq!(cb.state(), CB_OPEN);
    cb.attempt_reset();
    assert_eq!(cb.state(), CB_HALF_OPEN);

    // A single failure in half_open should immediately reopen
    cb.record_failure();
    assert_eq!(
        cb.state(),
        CB_OPEN,
        "one failure in half_open must immediately reopen the circuit — \
         half_open is probationary, not a second chance with full threshold"
    );
}

#[test]
fn circuit_breaker_half_open_recovery_then_failure() {
    // Complex state sequence: closed → open → half_open → partial recovery → failure
    let cb = CircuitBreaker::new(3, 3);

    // Trip to open
    cb.record_failure();
    cb.record_failure();
    cb.record_failure();
    assert_eq!(cb.state(), CB_OPEN);

    // Enter half_open
    cb.attempt_reset();
    assert_eq!(cb.state(), CB_HALF_OPEN);

    // Record 2 successes (threshold is 3, so still in half_open)
    cb.record_success();
    cb.record_success();
    assert_eq!(cb.state(), CB_HALF_OPEN);

    // One failure should immediately reopen, regardless of prior successes
    cb.record_failure();
    assert_eq!(
        cb.state(),
        CB_OPEN,
        "failure during half_open recovery must immediately reopen"
    );
}

// ---------------------------------------------------------------------------
// Category 5: Concurrency Bugs
// Shared mutable state ordering, admission control, and temporal consistency
// ---------------------------------------------------------------------------

#[test]
fn rate_limiter_refill_before_acquire() {
    // Token bucket must refill BEFORE checking available tokens.
    // If acquire checks stale (pre-refill) state, the first request
    // after a gap always fails even though tokens should be available.
    let rl = RateLimiter::new(2.0, 1.0);
    assert!(rl.try_acquire(0)); // 2→1
    assert!(rl.try_acquire(0)); // 1→0
    assert!(!rl.try_acquire(0)); // empty

    // 5 seconds pass. At rate 1.0/s, should refill to capacity (2.0).
    // The refill MUST happen before the availability check.
    assert!(
        rl.try_acquire(5),
        "after 5 seconds at rate 1.0/s, must refill before checking — \
         checking stale state would incorrectly reject this request"
    );
}

#[test]
fn rate_limiter_incremental_refill_timing() {
    let rl = RateLimiter::new(5.0, 2.0);
    // Drain all 5 tokens
    for _ in 0..5 {
        assert!(rl.try_acquire(0));
    }
    assert!(!rl.try_acquire(0));

    // At t=1, should have 2 tokens (2.0 * 1 second)
    assert!(rl.try_acquire(1), "should have 2 tokens after 1 second");
    assert!(rl.try_acquire(1), "should have 1 token left");
    assert!(!rl.try_acquire(1), "should be empty after using 2 tokens");
}

#[test]
fn priority_queue_rejects_at_capacity() {
    // When the queue is at capacity, new items must be REJECTED (return false)
    // without modifying the existing queue contents. The queue must not
    // silently evict existing items to make room for new ones.
    let q = PriorityQueue::new(2);
    assert!(q.enqueue(QueueItem { id: "first".into(), priority: 5 }));
    assert!(q.enqueue(QueueItem { id: "second".into(), priority: 3 }));

    // Queue is now full (2/2). A new item should be rejected.
    let accepted = q.enqueue(QueueItem { id: "overflow".into(), priority: 4 });
    assert!(!accepted, "queue at capacity must reject new items");

    // The original items must be unchanged — no eviction should have occurred
    assert_eq!(q.size(), 2, "queue size must not exceed capacity");
    let items: Vec<_> = (0..2).filter_map(|_| q.dequeue()).collect();
    let ids: Vec<&str> = items.iter().map(|i| i.id.as_str()).collect();
    assert!(
        ids.contains(&"first") && ids.contains(&"second"),
        "original items must be preserved after rejected enqueue, got {:?}",
        ids
    );
}

#[test]
fn priority_queue_high_priority_cannot_displace_at_capacity() {
    // Even a high-priority item must not displace existing items at capacity.
    // Admission control must be strict: once full, no new items regardless of priority.
    let q = PriorityQueue::new(2);
    q.enqueue(QueueItem { id: "a".into(), priority: 1 });
    q.enqueue(QueueItem { id: "b".into(), priority: 2 });

    // Try to add a HIGHER priority item — must still be rejected
    let accepted = q.enqueue(QueueItem { id: "urgent".into(), priority: 100 });
    assert!(!accepted, "full queue must reject even high-priority items");

    // Verify "b" (lower priority) was NOT evicted
    assert_eq!(q.size(), 2);
    let items: Vec<_> = (0..2).filter_map(|_| q.dequeue()).collect();
    let ids: Vec<&str> = items.iter().map(|i| i.id.as_str()).collect();
    assert!(
        ids.contains(&"a") && ids.contains(&"b"),
        "original items must be preserved: got {:?}",
        ids
    );
}

// ---------------------------------------------------------------------------
// Category 6: Additional Concurrency Bugs
// Temporal ordering issues in shared schedulers
// ---------------------------------------------------------------------------

#[test]
fn rolling_window_flush_boundary_retained() {
    // The rolling window scheduler uses a time-based cutoff.
    // An entry exactly at the cutoff timestamp should be considered ACTIVE
    // (within the window), not expired.
    let scheduler = RollingWindowScheduler::new(10);
    scheduler.submit(5, "early".into());
    scheduler.submit(10, "boundary".into());
    scheduler.submit(15, "recent".into());

    // now=20, cutoff=10. Entry at t=10 is at the boundary.
    let expired = scheduler.flush(20);
    assert_eq!(expired.len(), 1, "only t=5 should expire");
    assert_eq!(scheduler.count(), 2, "t=10 and t=15 should remain active");
}

#[test]
fn rolling_window_boundary_determines_active_set() {
    // With window=100 and now=200, cutoff=100.
    // Entries at t=99 expire (< 100 in correct implementation, <= 100 in buggy).
    // Entry at t=100 should survive.
    let scheduler = RollingWindowScheduler::new(100);
    scheduler.submit(99, "just-outside".into());
    scheduler.submit(100, "at-boundary".into());
    scheduler.submit(150, "well-inside".into());

    let expired = scheduler.flush(200);
    assert_eq!(expired.len(), 1, "only t=99 should expire");
    assert_eq!(scheduler.count(), 2, "t=100 and t=150 should remain");
}

// ---------------------------------------------------------------------------
// Category 7: Integration Bugs
// Cross-module contract violations that require understanding multiple
// modules and their interaction semantics.
// ---------------------------------------------------------------------------

#[test]
fn batch_create_preserves_extreme_severities() {
    // create_batch_orders must preserve the full severity range [SEV_INFO, SEV_CRITICAL].
    // Narrowing the clamp range breaks integration with validate_dispatch_order
    // which accepts the full [1, 5] range.
    let info_batch = create_batch_orders(&["i1"], SEV_INFO, 60);
    assert_eq!(
        info_batch[0].severity, SEV_INFO,
        "SEV_INFO ({}) must be preserved, got {}",
        SEV_INFO, info_batch[0].severity
    );

    let critical_batch = create_batch_orders(&["c1"], SEV_CRITICAL, 15);
    assert_eq!(
        critical_batch[0].severity, SEV_CRITICAL,
        "SEV_CRITICAL ({}) must be preserved, got {}",
        SEV_CRITICAL, critical_batch[0].severity
    );

    let over = create_batch_orders(&["o1"], 10, 30);
    assert_eq!(over[0].severity, SEV_CRITICAL, "severity > 5 should clamp to 5");
    let under = create_batch_orders(&["u1"], 0, 30);
    assert_eq!(under[0].severity, SEV_INFO, "severity < 1 should clamp to 1");
}

#[test]
fn topological_order_siblings_alphabetical() {
    // Service startup order must be deterministic. Services at the same
    // dependency depth should be ordered alphabetically so that deployments
    // are reproducible across environments.
    let defs = service_definitions();
    let order = topological_order(&defs).unwrap();

    // gateway's direct dependents are: routing, policy, resilience, audit, security
    // They should appear in alphabetical order: audit, policy, resilience, routing, security
    let direct_deps: Vec<&str> = defs
        .iter()
        .filter(|d| d.dependencies == vec!["gateway".to_string()])
        .map(|d| d.id.as_str())
        .collect();

    let mut positions: Vec<(&str, usize)> = direct_deps
        .iter()
        .map(|&name| (name, order.iter().position(|s| s == name).unwrap()))
        .collect();
    positions.sort_by_key(|&(_, pos)| pos);

    let ordered_names: Vec<&str> = positions.iter().map(|&(name, _)| name).collect();
    let mut sorted_names = ordered_names.clone();
    sorted_names.sort();

    assert_eq!(
        ordered_names, sorted_names,
        "sibling services must appear in alphabetical order for reproducible deploys"
    );
}

#[test]
fn cross_module_dispatch_lifecycle() {
    // Full integration test spanning allocator → routing → security → workflow.
    // Exercises the multi-step chain and integration bugs simultaneously.
    use vectorharbor::allocator::allocate_orders;
    use vectorharbor::policy::check_sla_compliance;
    use vectorharbor::routing::{choose_route, Route};
    use vectorharbor::security::{sign_manifest, verify_manifest};

    // Create high-severity order with correct SLA
    let order = DispatchOrder {
        id: "INTEG-1".into(),
        severity: SEV_HIGH,
        sla_minutes: 30,
    };
    let sla = sla_by_severity(order.severity);
    assert_eq!(sla, 30);

    // Allocate and route
    let planned = allocate_orders(vec![(order.id.clone(), order.severity, 10)], 1);
    assert_eq!(planned.len(), 1);
    let route = choose_route(
        &[Route { channel: "express".into(), latency: 3 }],
        &[],
    ).unwrap();

    // Sign manifest and verify
    let manifest = format!("{}:{}:{}", order.id, route.channel, sla);
    let sig = sign_manifest(&manifest, "dispatch-key");
    assert!(verify_manifest(&manifest, "dispatch-key", &sig));

    // Full workflow lifecycle
    let engine = WorkflowEngine::new();
    engine.register(&order.id);
    assert!(engine.transition(&order.id, "allocated", 1).success);
    assert!(engine.transition(&order.id, "departed", 2).success);
    assert!(
        engine.transition(&order.id, "arrived", 3).success,
        "full lifecycle must complete for departure→arrival"
    );

    // Verify post-arrival state
    assert!(engine.is_terminal(&order.id));
    assert_eq!(engine.active_count(), 0, "no active entities after arrival");
    assert!(check_sla_compliance(25, sla));

    // Verify audit trail
    let log = engine.audit_log();
    assert_eq!(log.len(), 3);
    assert!(log[0].contains("queued -> allocated"), "audit[0]: {}", log[0]);
    assert!(log[2].contains("departed -> arrived"), "audit[2]: {}", log[2]);
}

#[test]
fn policy_escalation_ceiling_with_deescalation() {
    // Integration between policy state machine and escalation ceiling.
    // After hitting the ceiling, deescalation should work normally.
    let engine = PolicyEngine::new();

    // Escalate to halted
    engine.escalate(1);
    engine.escalate(1);
    engine.escalate(1);
    assert_eq!(engine.current(), "halted");

    // Trying to escalate beyond halted must be no-op
    engine.escalate(99);
    assert_eq!(engine.current(), "halted", "must not wrap around");

    // Deescalation should work normally from halted
    engine.deescalate();
    assert_eq!(engine.current(), "restricted");
    engine.deescalate();
    assert_eq!(engine.current(), "watch");
}
