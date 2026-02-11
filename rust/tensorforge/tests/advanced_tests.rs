use tensorforge::workflow::{reachable_from, can_resume, is_stale, compact_history,
    validate_and_transition, batch_transition_atomic, WorkflowEngine, TransitionRecord};
use tensorforge::concurrency::{parallel_sum, epoch_advance, bounded_channel_size,
    AtomicCounter, SharedRegistry};
use tensorforge::resilience::{adaptive_backoff, health_quorum, ordered_replay_window,
    process_replay_batch, Event};
use tensorforge::events::{causal_order, merge_and_dedup, correlate_workflow_events, TimedEvent};
use tensorforge::routing::{congestion_adjusted_latency, route_reliability, optimal_stop_count};
use tensorforge::allocator::{surplus_berth_hours, allocation_efficiency, demand_spike,
    berth_schedule_conflict_window, BerthSlot};
use tensorforge::statistics::{cumulative_sum, trimmed_mean, outlier_indices,
    running_variance, detect_trend};
use tensorforge::security::{token_needs_refresh, audit_log_monotonic};
use tensorforge::policy::{cooldown_remaining, aggregate_risk, escalation_with_cooldown};
use tensorforge::telemetry::{sli_budget_remaining, alert_priority};
use tensorforge::models::{effective_sla, time_adjusted_urgency};
use tensorforge::queue::RateLimiter;

// ==== Fixed function tests (should PASS) ====

#[test]
fn fixed_parallel_sum_basic() {
    assert_eq!(parallel_sum(&[vec![1, 2, 3], vec![4, 5]]), 15);
}

#[test]
fn fixed_parallel_sum_empty() {
    assert_eq!(parallel_sum(&[]), 0);
    assert_eq!(parallel_sum(&[vec![]]), 0);
}

#[test]
fn fixed_epoch_advance() {
    let counter = AtomicCounter::new(0);
    assert_eq!(epoch_advance(&counter, 5), 5);
    let counter2 = AtomicCounter::new(10);
    assert_eq!(epoch_advance(&counter2, 1), 11);
}

#[test]
fn fixed_bounded_channel() {
    assert_eq!(bounded_channel_size(4, 2, 3), 12);
    assert_eq!(bounded_channel_size(2, 4, 3), 12);
    assert_eq!(bounded_channel_size(3, 3, 2), 6);
}

#[test]
fn fixed_adaptive_backoff() {
    assert_eq!(adaptive_backoff(100, 3, 5000), 800);
    assert_eq!(adaptive_backoff(100, 10, 5000), 5000);
    assert_eq!(adaptive_backoff(100, 0, 5000), 100);
}

#[test]
fn fixed_health_quorum_exact() {
    assert!(health_quorum(&[true, true, true, false], 0.75));
}

#[test]
fn fixed_health_quorum_below() {
    assert!(!health_quorum(&[true, false, false, false], 0.75));
}

#[test]
fn fixed_ordered_replay() {
    let events = vec![
        Event { id: "c".into(), sequence: 3 },
        Event { id: "a".into(), sequence: 1 },
        Event { id: "b".into(), sequence: 2 },
    ];
    let result = ordered_replay_window(&events, 1, 3);
    assert_eq!(result[0].sequence, 1);
    assert_eq!(result[1].sequence, 2);
    assert_eq!(result[2].sequence, 3);
}

#[test]
fn fixed_causal_order_tiebreak() {
    let events = vec![
        TimedEvent { id: "b".into(), timestamp: 100, kind: "X".into(), payload: "".into() },
        TimedEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "".into() },
    ];
    let ordered = causal_order(&events);
    assert_eq!(ordered[0].id, "a");
    assert_eq!(ordered[1].id, "b");
}

#[test]
fn fixed_merge_dedup_by_id() {
    let a = vec![
        TimedEvent { id: "e1".into(), timestamp: 100, kind: "A".into(), payload: "first".into() },
    ];
    let b = vec![
        TimedEvent { id: "e1".into(), timestamp: 200, kind: "A".into(), payload: "second".into() },
        TimedEvent { id: "e2".into(), timestamp: 150, kind: "B".into(), payload: "".into() },
    ];
    let result = merge_and_dedup(&a, &b);
    assert_eq!(result.len(), 2);
    let e1 = result.iter().find(|e| e.id == "e1").unwrap();
    assert_eq!(e1.payload, "first");
}

#[test]
fn fixed_congestion_latency() {
    assert_eq!(congestion_adjusted_latency(100, 0.5), 150);
    assert_eq!(congestion_adjusted_latency(100, 0.0), 100);
    assert_eq!(congestion_adjusted_latency(100, 1.0), 200);
}

#[test]
fn fixed_route_reliability() {
    assert!((route_reliability(8, 10) - 0.8).abs() < 0.01);
    assert!((route_reliability(10, 10) - 1.0).abs() < 0.01);
    assert_eq!(route_reliability(0, 0), 0.0);
}

#[test]
fn fixed_optimal_stops() {
    assert_eq!(optimal_stop_count(1000.0, 300.0), 4);
    assert_eq!(optimal_stop_count(900.0, 300.0), 3);
}

#[test]
fn fixed_surplus_berth_hours() {
    let slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 0, end_hour: 10, occupied: true, vessel_id: None },
        BerthSlot { berth_id: "B2".into(), start_hour: 0, end_hour: 8, occupied: false, vessel_id: None },
        BerthSlot { berth_id: "B3".into(), start_hour: 0, end_hour: 6, occupied: false, vessel_id: None },
    ];
    assert_eq!(surplus_berth_hours(&slots), 14);
}

#[test]
fn fixed_allocation_efficiency() {
    assert!((allocation_efficiency(8, 10) - 0.8).abs() < 0.01);
    assert!((allocation_efficiency(10, 10) - 1.0).abs() < 0.01);
}

#[test]
fn fixed_demand_spike() {
    assert!(demand_spike(150.0, 100.0, 25.0));
    assert!(!demand_spike(110.0, 100.0, 25.0));
}

#[test]
fn fixed_cumulative_sum() {
    let result = cumulative_sum(&[1.0, 2.0, 3.0]);
    assert!((result[0] - 1.0).abs() < 0.01);
    assert!((result[1] - 3.0).abs() < 0.01);
    assert!((result[2] - 6.0).abs() < 0.01);
}

#[test]
fn fixed_trimmed_mean() {
    let values: Vec<f64> = (1..=10).map(|v| v as f64).collect();
    let tm = trimmed_mean(&values, 0.2);
    assert!((tm - 5.5).abs() < 0.01);
}

#[test]
fn fixed_trimmed_mean_outliers() {
    let tm = trimmed_mean(&[1.0, 2.0, 3.0, 4.0, 100.0], 0.2);
    assert!((tm - 3.0).abs() < 0.01);
}

#[test]
fn fixed_outlier_detection() {
    let indices = outlier_indices(&[1.0, 2.0, 3.0, 4.0, 5.0, 100.0], 2.0);
    assert!(indices.contains(&5));
    assert!(!indices.contains(&0));
}

#[test]
fn fixed_audit_log_ordered() {
    assert!(audit_log_monotonic(&[100, 200, 300]));
}

#[test]
fn fixed_audit_log_unordered() {
    assert!(!audit_log_monotonic(&[100, 300, 200]));
}

#[test]
fn fixed_audit_log_last_pair() {
    assert!(!audit_log_monotonic(&[100, 200, 150]));
}

#[test]
fn fixed_cooldown_remaining() {
    assert_eq!(cooldown_remaining(100, 200, 300), 200);
    assert_eq!(cooldown_remaining(100, 600, 300), 0);
    assert_eq!(cooldown_remaining(100, 100, 300), 300);
}

#[test]
fn fixed_alert_priority() {
    assert_eq!(alert_priority(95.0, 80.0, 90.0), "critical");
    assert_eq!(alert_priority(85.0, 80.0, 90.0), "warning");
    assert_eq!(alert_priority(50.0, 80.0, 90.0), "ok");
}

#[test]
fn fixed_sli_budget_healthy() {
    let remaining = sli_budget_remaining(0.99, 0.999, 100, 50);
    assert!(remaining > 0.0);
}

#[test]
fn fixed_can_resume() {
    assert!(can_resume("queued"));
    assert!(can_resume("allocated"));
    assert!(!can_resume("arrived"));
    assert!(!can_resume("cancelled"));
}

#[test]
fn fixed_is_stale() {
    assert!(is_stale(100, 600, 300));
    assert!(!is_stale(100, 200, 300));
    assert!(!is_stale(100, 400, 300));
}

// ==== LATENT BUGS (own tests pass loosely, downstream precise tests fail) ====

// running_variance uses window size as divisor instead of actual slice.len() during warmup
// When slice.len() == window (no warmup), result is correct → PASSES
#[test]
fn lat_running_variance_full_window() {
    let rv = running_variance(&[10.0, 20.0], 2);
    assert_eq!(rv.len(), 2);
    // window=2, slice.len()=2 at i=1, no warmup → correct sample variance
    assert!((rv[1] - 50.0).abs() < 0.01);
}

// During warmup (slice.len() < window), uses window as divisor → wrong
// [10.0, 20.0, 30.0] window=5: at i=1, slice=[10,20], len=2
// sum_sq=50, buggy: 50/(5-1)=12.5, correct: 50/(2-1)=50.0
#[test]
fn lat_running_variance_warmup_exact() {
    let rv = running_variance(&[10.0, 20.0, 30.0], 5);
    assert_eq!(rv.len(), 3);
    assert!((rv[1] - 50.0).abs() < 0.01);
}

// [2.0, 4.0, 6.0] window=10: at i=2, slice=[2,4,6], len=3
// mean=4, sum_sq=8, buggy: 8/(10-1)=0.888, correct: 8/(3-1)=4.0
#[test]
fn lat_running_variance_warmup_three() {
    let rv = running_variance(&[2.0, 4.0, 6.0], 10);
    let expected_sample_var = 4.0;
    assert!((rv[2] - expected_sample_var).abs() < 0.01);
}

// compact_history keeps FIRST per entity instead of LAST
// This test has unique entities so it passes
#[test]
fn lat_compact_history_unique_entities() {
    let history = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 1 },
        TransitionRecord { entity_id: "e2".into(), from: "queued".into(), to: "allocated".into(), timestamp: 2 },
    ];
    let compacted = compact_history(&history);
    assert_eq!(compacted.len(), 2);
}

// This test has multiple transitions per entity and FAILS
#[test]
fn lat_compact_history_keeps_latest() {
    let history = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 1 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: 2 },
        TransitionRecord { entity_id: "e1".into(), from: "departed".into(), to: "arrived".into(), timestamp: 3 },
    ];
    let compacted = compact_history(&history);
    assert_eq!(compacted.len(), 1);
    assert_eq!(compacted[0].to, "arrived");
}

#[test]
fn lat_compact_history_mixed() {
    let history = vec![
        TransitionRecord { entity_id: "e1".into(), from: "queued".into(), to: "allocated".into(), timestamp: 1 },
        TransitionRecord { entity_id: "e2".into(), from: "queued".into(), to: "cancelled".into(), timestamp: 2 },
        TransitionRecord { entity_id: "e1".into(), from: "allocated".into(), to: "departed".into(), timestamp: 3 },
    ];
    let compacted = compact_history(&history);
    assert_eq!(compacted.len(), 2);
    let e1 = compacted.iter().find(|r| r.entity_id == "e1").unwrap();
    assert_eq!(e1.to, "departed");
}

// ==== DOMAIN LOGIC BUGS ====

// berth_schedule_conflict_window applies buffer asymmetrically (departure only, not arrival)
// Departure-side overlap with buffer works correctly → PASSES
#[test]
fn dl_berth_departure_buffer_works() {
    let slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 10, end_hour: 14, occupied: true, vessel_id: None },
    ];
    // new [14,18] after slot [10,14]: departure buffer catches it (14 < 14+2=16)
    assert!(berth_schedule_conflict_window(&slots, 14, 18, "B1", 2));
}

#[test]
fn dl_berth_conflict_no_buffer_no_overlap() {
    let slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 10, end_hour: 14, occupied: true, vessel_id: None },
    ];
    assert!(!berth_schedule_conflict_window(&slots, 14, 18, "B1", 0));
}

// Arrival-side overlap with buffer should detect conflict but doesn't → FAILS
#[test]
fn dl_berth_arrival_buffer_missing() {
    let slots = vec![
        BerthSlot { berth_id: "B1".into(), start_hour: 10, end_hour: 14, occupied: true, vessel_id: None },
    ];
    // new [6,10] before slot [10,14] with buffer=2: should conflict (10-2=8 < 10)
    // Bug: new_end(10) > slot.start(10) is false (strict >), arrival buffer not applied
    assert!(berth_schedule_conflict_window(&slots, 6, 10, "B1", 2));
}

// effective_sla uses parallel redundancy formula 1-(1-a)(1-b) instead of serial a*b
#[test]
fn dl_effective_sla_cascaded() {
    let sla = effective_sla(0.999, 0.999);
    // Correct serial: 0.999 * 0.999 = 0.998001
    // Buggy parallel: 1 - (0.001 * 0.001) = 0.999999
    assert!((sla - 0.998001).abs() < 0.0001);
}

#[test]
fn dl_effective_sla_different() {
    let sla = effective_sla(0.99, 0.999);
    // Correct serial: 0.99 * 0.999 = 0.98901
    // Buggy parallel: 1 - (0.01 * 0.001) = 0.99999
    assert!((sla - 0.98901).abs() < 0.0001);
}

// time_adjusted_urgency decreases near deadline instead of increasing
#[test]
fn dl_urgency_increases_near_deadline() {
    let urg_start = time_adjusted_urgency(10.0, 0.0, 60.0);
    let urg_near_end = time_adjusted_urgency(10.0, 55.0, 60.0);
    assert!(urg_near_end > urg_start);
}

#[test]
fn dl_urgency_at_deadline() {
    let urg = time_adjusted_urgency(10.0, 60.0, 60.0);
    assert!((urg - 20.0).abs() < 0.01);
}

#[test]
fn dl_urgency_at_start() {
    let urg = time_adjusted_urgency(10.0, 0.0, 60.0);
    assert!((urg - 10.0).abs() < 0.01);
}

// ==== MULTI-STEP BUGS ====

// process_replay_batch: compensating bug with event_ordering
// Currently PASSES because event_ordering (desc) + reverse = asc
// When event_ordering is fixed to asc, this breaks
#[test]
fn ms_process_replay_ascending() {
    let events = vec![
        Event { id: "c".into(), sequence: 3 },
        Event { id: "a".into(), sequence: 1 },
        Event { id: "b".into(), sequence: 2 },
    ];
    let result = process_replay_batch(&events);
    assert_eq!(result[0].sequence, 1);
    assert_eq!(result[1].sequence, 2);
    assert_eq!(result[2].sequence, 3);
}

#[test]
fn ms_process_replay_single() {
    let events = vec![Event { id: "a".into(), sequence: 42 }];
    let result = process_replay_batch(&events);
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].sequence, 42);
}

// detect_trend: swapped labels + depends on bugged EMA
#[test]
fn ms_detect_trend_rising() {
    assert_eq!(detect_trend(&[1.0, 2.0, 3.0, 4.0, 5.0], 0.3), "rising");
}

#[test]
fn ms_detect_trend_falling() {
    assert_eq!(detect_trend(&[5.0, 4.0, 3.0, 2.0, 1.0], 0.3), "falling");
}

#[test]
fn ms_detect_trend_stable() {
    assert_eq!(detect_trend(&[5.0, 5.0, 5.0, 5.0], 0.5), "stable");
}

// ==== STATE MACHINE BUGS ====

// validate_and_transition: validates AFTER transitioning
#[test]
fn sm_validate_rejects_but_state_unchanged() {
    let engine = WorkflowEngine::new();
    engine.register("e1");
    let result = validate_and_transition(&engine, "e1", "allocated", 1, &["departed"]);
    assert!(!result.success);
    assert_eq!(engine.get_state("e1").unwrap(), "queued");
}

#[test]
fn sm_validate_accepts_valid_target() {
    let engine = WorkflowEngine::new();
    engine.register("e1");
    let result = validate_and_transition(&engine, "e1", "allocated", 1, &["allocated", "cancelled"]);
    assert!(result.success);
    assert_eq!(engine.get_state("e1").unwrap(), "allocated");
}

// batch_transition_atomic: no rollback on partial failure
#[test]
fn sm_batch_atomic_rollback() {
    let engine = WorkflowEngine::new();
    engine.register("e1");
    engine.register("e2");
    let (ok, _results) = batch_transition_atomic(&engine, &[
        ("e1", "allocated", 1),
        ("e2", "arrived", 2),
    ]);
    assert!(!ok);
    assert_eq!(engine.get_state("e1").unwrap(), "queued");
    assert_eq!(engine.get_state("e2").unwrap(), "queued");
}

#[test]
fn sm_batch_atomic_all_succeed() {
    let engine = WorkflowEngine::new();
    engine.register("e1");
    engine.register("e2");
    let (ok, _) = batch_transition_atomic(&engine, &[
        ("e1", "allocated", 1),
        ("e2", "allocated", 2),
    ]);
    assert!(ok);
    assert_eq!(engine.get_state("e1").unwrap(), "allocated");
    assert_eq!(engine.get_state("e2").unwrap(), "allocated");
}

// escalation_with_cooldown: compares now vs absolute instead of elapsed
#[test]
fn sm_escalation_cooldown_blocks() {
    let result = escalation_with_cooldown("normal", 5, 900, 1000, 200);
    assert_eq!(result, "normal");
}

#[test]
fn sm_escalation_cooldown_allows() {
    let result = escalation_with_cooldown("normal", 5, 500, 1000, 200);
    assert_eq!(result, "watch");
}

#[test]
fn sm_escalation_cooldown_within_period() {
    // now=1000, last_change=850, elapsed=150 < cooldown=200 → should block
    // Bug: compares now(1000) < min_cooldown(200) → false → allows → "restricted"
    let result = escalation_with_cooldown("watch", 5, 850, 1000, 200);
    assert_eq!(result, "watch");
}

// ==== CONCURRENCY BUGS ====

// try_acquire_batch: checks >= 1.0 instead of >= count
#[test]
fn conc_batch_acquire_insufficient_tokens() {
    let limiter = RateLimiter::new(5.0, 1.0);
    assert!(limiter.try_acquire_batch(3, 0));
    assert_eq!(limiter.available(), 2.0);
    assert!(!limiter.try_acquire_batch(3, 0));
}

#[test]
fn conc_batch_acquire_exact() {
    let limiter = RateLimiter::new(3.0, 0.0);
    assert!(limiter.try_acquire_batch(3, 0));
    assert!(!limiter.try_acquire_batch(1, 0));
}

// transfer: silently overwrites existing destination key (data loss)
// Transfer with no existing destination works correctly → PASSES
#[test]
fn conc_transfer_no_conflict() {
    let reg = SharedRegistry::new();
    reg.register("src".into(), "data".into());
    assert!(reg.transfer("src", "dst"));
    assert!(reg.lookup("src").is_none());
    assert_eq!(reg.lookup("dst").unwrap(), "data");
    assert_eq!(reg.count(), 1);
}

// Transfer to existing destination should fail to prevent data loss
// Bug: silently overwrites destination → FAILS
#[test]
fn conc_transfer_refuses_overwrite() {
    let reg = SharedRegistry::new();
    reg.register("src".into(), "data_src".into());
    reg.register("dst".into(), "data_dst".into());
    assert!(!reg.transfer("src", "dst"));
    assert_eq!(reg.lookup("dst").unwrap(), "data_dst");
    assert_eq!(reg.count(), 2);
}

#[test]
fn conc_transfer_preserves_existing() {
    let reg = SharedRegistry::new();
    reg.register("a".into(), "val_a".into());
    reg.register("b".into(), "val_b".into());
    reg.register("c".into(), "val_c".into());
    // Transfer a→b should fail (b exists, would lose data)
    assert!(!reg.transfer("a", "b"));
    assert_eq!(reg.lookup("b").unwrap(), "val_b");
    assert_eq!(reg.count(), 3);
}

// add_and_check_threshold: TOCTOU (uses pre-addition value)
#[test]
fn conc_threshold_check_post_add() {
    let counter = AtomicCounter::new(8);
    let crossed = counter.add_and_check_threshold(3, 10);
    assert!(crossed);
    assert_eq!(counter.get(), 11);
}

#[test]
fn conc_threshold_exactly_at() {
    let counter = AtomicCounter::new(7);
    let crossed = counter.add_and_check_threshold(3, 10);
    assert!(crossed);
}

// ==== INTEGRATION BUGS ====

// correlate_workflow_events: looks AFTER transition instead of BEFORE
#[test]
fn int_correlate_finds_preceding_events() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 90, kind: "alert".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 110, kind: "log".into(), payload: "".into() },
    ];
    let correlated = correlate_workflow_events(&[100], &events, 20);
    assert_eq!(correlated.len(), 1);
    assert_eq!(correlated[0].len(), 1);
    assert_eq!(correlated[0][0].id, "e1");
}

#[test]
fn int_correlate_multiple_transitions() {
    let events = vec![
        TimedEvent { id: "e1".into(), timestamp: 45, kind: "A".into(), payload: "".into() },
        TimedEvent { id: "e2".into(), timestamp: 95, kind: "B".into(), payload: "".into() },
        TimedEvent { id: "e3".into(), timestamp: 150, kind: "C".into(), payload: "".into() },
    ];
    let correlated = correlate_workflow_events(&[50, 100], &events, 10);
    assert_eq!(correlated[0].len(), 1);
    assert_eq!(correlated[0][0].id, "e1");
    assert_eq!(correlated[1].len(), 1);
    assert_eq!(correlated[1][0].id, "e2");
}

// ==== KEPT BUGS (from original round) ====

// reachable_from: missing transitive closure
#[test]
fn kept_reachable_from_queued_transitive() {
    let reachable = reachable_from("queued");
    assert!(reachable.contains(&"arrived".to_string()));
    assert!(reachable.contains(&"departed".to_string()));
    assert!(reachable.contains(&"allocated".to_string()));
    assert!(reachable.contains(&"cancelled".to_string()));
}

#[test]
fn kept_reachable_from_departed() {
    let reachable = reachable_from("departed");
    assert!(reachable.contains(&"arrived".to_string()));
    assert_eq!(reachable.len(), 1);
}

// token_needs_refresh: checks after expiry+window instead of before expiry
#[test]
fn kept_token_refresh_needed() {
    assert!(token_needs_refresh(1000, 4400, 3600, 300));
}

#[test]
fn kept_token_refresh_not_needed() {
    assert!(!token_needs_refresh(1000, 4200, 3600, 300));
}

#[test]
fn kept_token_refresh_boundary() {
    assert!(!token_needs_refresh(1000, 4300, 3600, 300));
}

// aggregate_risk: max-weighted aggregation instead of straight average
// Buggy: (max_risk + avg_others) / 2 where avg_others = (sum-max)/len
// Correct: sum of individual risks / len
#[test]
fn kept_aggregate_risk_basic() {
    let risk = aggregate_risk(&[(10.0, 0.8), (5.0, 0.4)]);
    // individual = [8.0, 2.0], correct avg = 5.0
    // buggy: max=8, avg_others=(10-8)/2=1.0, result=(8+1)/2=4.5
    assert!((risk - 5.0).abs() < 0.01);
}

#[test]
fn kept_aggregate_risk_certain() {
    let risk = aggregate_risk(&[(10.0, 1.0)]);
    // individual = [10.0], correct avg = 10.0
    // buggy: max=10, avg_others=0/1=0, result=(10+0)/2=5.0
    assert!((risk - 10.0).abs() < 0.01);
}
