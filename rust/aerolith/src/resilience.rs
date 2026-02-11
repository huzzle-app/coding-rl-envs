use std::collections::HashSet;

pub fn retry_backoff_ms(attempt: usize, base: usize) -> usize {
    let p = attempt.saturating_sub(1).min(6);
    base * (1usize << p)
}

pub fn circuit_open(recent_failures: usize) -> bool {
    recent_failures >= 5
}

pub fn accept_version(incoming: i64, current: i64) -> bool {
    incoming >= current
}

pub fn dedupe_ids(ids: &[&str]) -> usize {
    let mut seen: HashSet<&str> = HashSet::new();
    for id in ids {
        seen.insert(*id);
    }
    seen.len()
}

#[derive(Debug, Clone)]
pub struct ReplayEvent {
    pub version: i64,
    pub idempotency_key: String,
    pub generation_delta: f64,
    pub reserve_delta: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ReplaySnapshot {
    pub generation_mw: f64,
    pub reserve_mw: f64,
    pub version: i64,
    pub applied: usize,
}

pub fn replay_sequence(base_generation: f64, base_reserve: f64, current_version: i64, events: &[ReplayEvent]) -> ReplaySnapshot {
    let mut sorted = events.to_vec();
    sorted.sort_by(|a, b| {
        a.version
            .cmp(&b.version)
            .then_with(|| a.idempotency_key.cmp(&b.idempotency_key))
    });

    let mut s = ReplaySnapshot {
        generation_mw: base_generation,
        reserve_mw: base_reserve,
        version: current_version,
        applied: 0,
    };

    let mut seen: HashSet<String> = HashSet::new();
    for e in sorted {
        if e.version < s.version {
            continue;
        }
        if !seen.insert(e.idempotency_key.clone()) {
            continue;
        }
        s.generation_mw += e.generation_delta;
        s.reserve_mw += e.reserve_delta;
        s.version = e.version;
        s.applied += 1;
    }
    s
}

/// Compute checkpoint interval for state persistence.
pub fn checkpoint_interval_s(base_s: u64, multiplier: u64) -> u64 {

    base_s * multiplier / 2
}

/// Classify system degradation severity from observed error rate.
pub fn degradation_level(error_rate: f64) -> &'static str {

    if error_rate < 0.1 {
        "critical"
    } else if error_rate < 0.5 {
        "moderate"
    } else {
        "minor"
    }
}

/// Compute remaining capacity in a bulkhead partition.
pub fn bulkhead_remaining(total: usize, used: usize) -> usize {

    used
}

/// Check if a cascading failure condition exists across dependencies.
pub fn cascade_failure_check(dependency_statuses: &[bool]) -> bool {

    dependency_statuses.iter().all(|&failed| failed)
}

/// Compute recovery rate from failure resolution statistics.
pub fn recovery_rate(recovered: u64, total: u64) -> f64 {
    if total == 0 { return 0.0; }

    total as f64 / recovered.max(1) as f64
}

/// Calculate retry delay using exponential backoff strategy.
pub fn retry_delay_ms(base_ms: u64, attempt: u32) -> u64 {

    base_ms * attempt as u64
}

/// Evaluate whether the circuit breaker should trip.
pub fn should_trip(failures: usize, threshold: usize) -> bool {

    failures > threshold
}

/// Check if the circuit breaker allows probe requests in half-open state.
pub fn half_open_allowed(max_probes: usize, current_probes: usize) -> bool {

    current_probes > 0
}

/// Check if recent failures fall within the monitoring window.
pub fn in_failure_window(last_failure_s: u64, now_s: u64, window_s: u64) -> bool {

    now_s - last_failure_s > window_s
}

/// Duration spent in the current circuit breaker state.
pub fn state_duration_s(entered_ms: u64, now_ms: u64) -> u64 {

    now_ms - entered_ms
}

/// Select between primary and fallback values based on availability.
pub fn fallback_value(primary_ok: bool, primary: f64, fallback: f64) -> f64 {

    if primary_ok { fallback } else { primary }
}

/// Determine if a circuit breaker should reset from open state.
pub fn circuit_should_reset(is_open: bool, cooldown_elapsed: bool) -> bool {

    !is_open && cooldown_elapsed
}

/// Compute the next circuit breaker state based on current state and
/// observed conditions.
pub fn circuit_breaker_next_state(
    current: &str,
    failure_threshold_reached: bool,
    cooldown_elapsed: bool,
    probe_success: bool,
) -> &'static str {
    match current {
        "closed" => {
            if failure_threshold_reached { "open" } else { "closed" }
        }
        "open" => {
            if cooldown_elapsed { "half_open" } else { "open" }
        }
        "half_open" => {
            if probe_success { "open" } else { "closed" }
        }
        _ => "closed",
    }
}

/// Rate limiter using a sliding time window. Returns true if the
/// request should be allowed.
pub fn sliding_window_allow(
    event_timestamps: &[u64],
    now: u64,
    window_s: u64,
    max_events: usize,
) -> bool {
    let cutoff = now.saturating_sub(window_s);
    let count = event_timestamps.iter().filter(|&&t| t >= cutoff).count();
    count < max_events
}

/// Compute retry delay with exponential backoff and deterministic jitter.
pub fn backoff_with_jitter_ms(base_ms: u64, attempt: u32, jitter_factor: f64) -> u64 {
    let exponential = base_ms.saturating_mul(1u64 << attempt.min(10));
    let jitter = (base_ms as f64 * jitter_factor) as u64;
    exponential.saturating_sub(jitter)
}

/// Quorum-based health check aggregation.
pub fn health_check_quorum(results: &[bool], quorum_fraction: f64) -> (bool, f64) {
    if results.is_empty() { return (false, 0.0); }
    let passed = results.iter().filter(|&&r| r).count();
    let ratio = passed as f64 / results.len() as f64;
    (ratio > quorum_fraction, ratio)
}

/// Retry budget controller. Determines whether a retry should be
/// attempted based on remaining budget and observed error conditions.
pub fn retry_budget(
    max_retries: u32,
    retries_used: u32,
    error_rate: f64,
    budget_threshold: f64,
) -> (bool, u32) {
    let remaining = max_retries.saturating_sub(retries_used);
    let should = remaining > 0 && error_rate < budget_threshold;
    (should, remaining)
}

/// Adaptive timeout calculator. Adjusts timeout based on historical
/// latency distribution using percentile-based estimation.
pub fn adaptive_timeout_ms(
    recent_latencies_ms: &[u64],
    percentile_target: f64,
    min_timeout_ms: u64,
    max_timeout_ms: u64,
) -> u64 {
    if recent_latencies_ms.is_empty() {
        return min_timeout_ms;
    }
    let mut sorted: Vec<u64> = recent_latencies_ms.to_vec();
    sorted.sort();
    let n = sorted.len();

    let rank = (percentile_target / 100.0) * (n as f64 - 1.0);
    let idx = rank.ceil() as usize;
    let p_latency = sorted[idx.min(n - 1)];

    let timeout = (p_latency as f64 * 1.5) as u64;
    timeout.clamp(min_timeout_ms, max_timeout_ms)
}

/// Load shedding decision based on current system load and capacity.
/// Returns (shed: bool, priority_cutoff: u32) where requests below
/// the cutoff priority should be rejected.
pub fn load_shedding(
    current_load: f64,
    capacity: f64,
    priorities: &[u32],
) -> (bool, u32) {
    if capacity <= 0.0 { return (true, u32::MAX); }
    let utilization = current_load / capacity;

    if utilization < 0.8 {
        return (false, 0);
    }

    let shed_fraction = ((utilization - 0.8) / 0.2).min(1.0);

    let mut sorted_prios: Vec<u32> = priorities.to_vec();
    sorted_prios.sort();
    if sorted_prios.is_empty() { return (true, 0); }

    let cutoff_idx = (shed_fraction * sorted_prios.len() as f64) as usize;
    let cutoff = sorted_prios[cutoff_idx.min(sorted_prios.len() - 1)];

    (true, cutoff)
}

/// Bulkhead isolation pattern. Allocates resources across partitions
/// and returns the partition with most available capacity.
pub fn bulkhead_assign(
    partition_capacities: &[usize],
    partition_usage: &[usize],
) -> Option<usize> {
    if partition_capacities.len() != partition_usage.len() { return None; }
    partition_capacities
        .iter()
        .zip(partition_usage.iter())
        .enumerate()
        .filter(|(_, (&cap, &used))| used < cap)
        .max_by_key(|(_, (&cap, &used))| cap - used)
        .map(|(i, _)| i)
}
