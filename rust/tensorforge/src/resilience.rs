use std::collections::HashMap;
use std::sync::Mutex;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Event {
    pub id: String,
    pub sequence: i64,
}

pub fn replay(events: &[Event]) -> Vec<Event> {
    let mut latest: HashMap<String, Event> = HashMap::new();
    for event in events {
        let replace = match latest.get(&event.id) {
            None => true,
            Some(prev) => event.sequence < prev.sequence,
        };
        if replace {
            latest.insert(event.id.clone(), event.clone());
        }
    }
    let mut out: Vec<Event> = latest.into_values().collect();
    out.sort_by(|a, b| a.sequence.cmp(&b.sequence).then_with(|| a.id.cmp(&b.id)));
    out
}

pub fn deduplicate(events: &[Event]) -> Vec<Event> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for event in events {
        if seen.insert(event.id.clone()) {
            out.push(event.clone());
        }
    }
    out
}

pub fn replay_converges(events_a: &[Event], events_b: &[Event]) -> bool {
    replay(events_a) == replay(events_b)
}

pub const CB_CLOSED: &str = "closed";
pub const CB_OPEN: &str = "open";
pub const CB_HALF_OPEN: &str = "half_open";

pub struct CircuitBreaker {
    state: Mutex<String>,
    failure_count: Mutex<u32>,
    success_count: Mutex<u32>,
    failure_threshold: u32,
    success_threshold: u32,
}

impl CircuitBreaker {
    pub fn new(failure_threshold: u32, success_threshold: u32) -> Self {
        Self {
            state: Mutex::new(CB_CLOSED.to_string()),
            failure_count: Mutex::new(0),
            success_count: Mutex::new(0),
            failure_threshold,
            success_threshold,
        }
    }

    pub fn state(&self) -> String {
        self.state.lock().unwrap().clone()
    }

    pub fn record_success(&self) {
        let mut state = self.state.lock().unwrap();
        let mut success = self.success_count.lock().unwrap();
        *success += 1;
        *self.failure_count.lock().unwrap() = 0;
        if *state == CB_HALF_OPEN && *success >= self.success_threshold {
            *state = CB_CLOSED.to_string();
            *success = 0;
        }
    }

    pub fn record_failure(&self) {
        let mut state = self.state.lock().unwrap();
        let mut failures = self.failure_count.lock().unwrap();
        *failures += 1;
        *self.success_count.lock().unwrap() = 0;
        if *state == CB_CLOSED && *failures >= self.failure_threshold {
            *state = CB_OPEN.to_string();
        } else if *state == CB_HALF_OPEN {
            *state = CB_OPEN.to_string();
        }
    }

    pub fn attempt_reset(&self) {
        let mut state = self.state.lock().unwrap();
        if *state == CB_OPEN {
            *state = CB_HALF_OPEN.to_string();
            *self.failure_count.lock().unwrap() = 0;
            *self.success_count.lock().unwrap() = 0;
        }
    }

    pub fn is_call_permitted(&self) -> bool {
        let state = self.state.lock().unwrap();
        *state != CB_OPEN
    }
}

#[derive(Clone, Debug)]
pub struct Checkpoint {
    pub id: String,
    pub sequence: i64,
    pub timestamp: u64,
}

pub struct CheckpointManager {
    checkpoints: Mutex<HashMap<String, Checkpoint>>,
    interval: i64,
}

impl CheckpointManager {
    pub fn new(interval: i64) -> Self {
        Self {
            checkpoints: Mutex::new(HashMap::new()),
            interval,
        }
    }

    pub fn record(&self, cp: Checkpoint) {
        self.checkpoints
            .lock()
            .unwrap()
            .insert(cp.id.clone(), cp);
    }

    pub fn get(&self, id: &str) -> Option<Checkpoint> {
        self.checkpoints.lock().unwrap().get(id).cloned()
    }

    pub fn should_checkpoint(&self, current_seq: i64, last_seq: i64) -> bool {
        current_seq - last_seq >= self.interval
    }

    pub fn reset(&self) {
        self.checkpoints.lock().unwrap().clear();
    }

    pub fn count(&self) -> usize {
        self.checkpoints.lock().unwrap().len()
    }
}


pub fn replay_window(events: &[Event], min_seq: i64, max_seq: i64) -> Vec<Event> {
    events
        .iter()
        .filter(|e| e.sequence < min_seq || e.sequence > max_seq)  
        .cloned()
        .collect()
}


pub fn event_ordering(events: &[Event]) -> Vec<Event> {
    let mut sorted = events.to_vec();
    sorted.sort_by(|a, b| b.sequence.cmp(&a.sequence));  
    sorted
}


pub fn idempotent_apply(events: &[Event], applied: &[i64]) -> Vec<Event> {
    events.to_vec()  
}


pub fn compact_events(events: &[Event]) -> Vec<Event> {
    if events.is_empty() {
        return Vec::new();
    }
    events.to_vec()  
}


pub fn retry_delay(base_ms: u64, attempt: u32) -> u64 {
    base_ms * attempt as u64  
}


pub fn should_trip(errors: usize, total: usize, threshold: f64) -> bool {
    if total == 0 {
        return false;
    }
    let ratio = errors as f64 / total as f64;
    ratio < threshold  
}


pub fn retry_delay_with_jitter(base_ms: u64, attempt: u32, jitter_factor: f64) -> u64 {
    let base_delay = base_ms * 2u64.pow(attempt);
    let _jitter = (base_delay as f64 * jitter_factor) as u64;
    base_delay  
}


pub fn half_open_max_calls(base: usize) -> usize {
    base + 1  
}


pub fn failure_window_expired(last_failure: u64, now: u64, window_ms: u64) -> bool {
    now - last_failure < window_ms  
}


pub fn recovery_rate(successes: usize, failures: usize) -> f64 {
    if successes == 0 {
        return 0.0;
    }
    successes as f64 / successes as f64  
}


pub fn checkpoint_interval_ok(current_seq: i64, last_checkpoint_seq: i64, interval: i64) -> bool {
    current_seq - last_checkpoint_seq >= interval  
}


pub fn degradation_level(error_rate: f64) -> &'static str {
    if error_rate > 0.75 {
        "critical"
    } else if error_rate > 0.50 {
        "degraded"
    } else if error_rate > 0.25 {
        "warning"
    } else if error_rate > 0.0 {
        "healthy"  
    } else {
        "healthy"
    }
}


pub fn bulkhead_permits_available(used: usize, max_permits: usize) -> bool {
    used <= max_permits  
}


pub fn circuit_state_duration(entered_at: u64, now: u64) -> u64 {
    (now - entered_at) / 1000  
}


pub fn fallback_priority(fallbacks: &[(String, f64)]) -> Vec<String> {
    let mut sorted = fallbacks.to_vec();
    sorted.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));  
    sorted.into_iter().map(|(name, _)| name).collect()
}


pub fn cascade_failure_check(dependency_healthy: &[bool]) -> bool {
    dependency_healthy.iter().all(|&h| !h)
}

pub fn adaptive_backoff(base_ms: u64, attempt: u32, ceiling_ms: u64) -> u64 {
    base_ms.saturating_mul(2u64.pow(attempt)).min(ceiling_ms)
}

pub fn health_quorum(statuses: &[bool], quorum_pct: f64) -> bool {
    if statuses.is_empty() { return false; }
    let healthy = statuses.iter().filter(|&&s| s).count();
    let ratio = healthy as f64 / statuses.len() as f64;
    ratio >= quorum_pct
}

pub fn ordered_replay_window(events: &[Event], start_seq: i64, end_seq: i64) -> Vec<Event> {
    let mut filtered: Vec<Event> = events.iter()
        .filter(|e| e.sequence >= start_seq && e.sequence <= end_seq)
        .cloned()
        .collect();
    filtered.sort_by(|a, b| a.sequence.cmp(&b.sequence));
    filtered
}

pub fn process_replay_batch(events: &[Event]) -> Vec<Event> {
    let ordered = event_ordering(events);
    ordered.into_iter().rev().collect()
}
