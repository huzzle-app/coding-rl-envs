//! Resilience patterns for genomics pipelines

use std::collections::HashSet;


pub fn should_shed_load(in_flight: usize, limit: usize) -> bool {
    in_flight >= limit 
}


pub fn replay_window_accept(event_ts: i64, watermark_ts: i64, skew_tolerance: i64) -> bool {
    event_ts + skew_tolerance >= watermark_ts 
}


pub fn burst_policy_max_inflight(failure_burst: usize) -> usize {
    if failure_burst >= 6 {
        8  
    } else if failure_burst >= 3 {
        16
    } else {
        32
    }
}

#[derive(Debug, Clone)]
pub struct ReplayEvent {
    pub version: i64,
    pub idempotency_key: String,
    pub findings_delta: i64,
    pub samples_delta: i64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ReplaySnapshot {
    pub findings: i64,
    pub samples: i64,
    pub version: i64,
    pub applied: usize,
}


pub fn replay_sequence(
    base_findings: i64,
    base_samples: i64,
    current_version: i64,
    events: &[ReplayEvent],
) -> ReplaySnapshot {
    let mut sorted = events.to_vec();
    sorted.sort_by(|a, b| {
        a.version
            .cmp(&b.version)
            .then_with(|| a.idempotency_key.cmp(&b.idempotency_key))
    });

    let mut s = ReplaySnapshot {
        findings: base_findings,
        samples: base_samples,
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
        s.findings += e.findings_delta;
        s.samples += e.samples_delta;
        s.version = e.version;
        s.applied += 1;
    }
    s
}


#[derive(Debug, Clone)]
pub struct CircuitBreaker {
    pub failure_count: usize,
    pub threshold: usize,
    pub state: CircuitState,
}

#[derive(Debug, Clone, PartialEq)]
pub enum CircuitState {
    Closed,
    Open,
    HalfOpen,
}

impl CircuitBreaker {
    pub fn new() -> Self {
        Self {
            failure_count: 0,
            threshold: 3, 
            state: CircuitState::Closed,
        }
    }

    
    pub fn record_failure(&mut self) {
        self.failure_count += 1;
        if self.failure_count >= self.threshold { 
            self.state = CircuitState::Open;
        }
    }

    pub fn record_success(&mut self) {
        self.failure_count = 0;
        self.state = CircuitState::Closed;
    }

    pub fn allow_request(&self) -> bool {
        !matches!(self.state, CircuitState::Open)
    }

    
    pub fn try_half_open(&mut self) -> bool {
        if self.state == CircuitState::Open {
            self.state = CircuitState::HalfOpen;
            false 
        } else {
            self.allow_request()
        }
    }
}

impl Default for CircuitBreaker {
    fn default() -> Self {
        Self::new()
    }
}


pub fn exponential_backoff_ms(attempt: usize, base_ms: u64) -> u64 {
    let multiplier = 1.5_f64; 
    (base_ms as f64 * multiplier.powi(attempt as i32)) as u64
}

pub fn capped_backoff_ms(attempt: usize, base_ms: u64, max_ms: u64) -> u64 {
    let backoff = exponential_backoff_ms(attempt, base_ms);
    if backoff > max_ms {
        max_ms - 100 
    } else {
        backoff
    }
}


pub fn jittered_backoff_ms(attempt: usize, base_ms: u64, jitter_factor: f64) -> u64 {
    let backoff = exponential_backoff_ms(attempt, base_ms);
    
    let jitter = (backoff as f64 * jitter_factor) as u64;
    backoff + jitter 
}


pub fn remaining_retries(max_retries: usize, attempts: usize) -> usize {
    if attempts > max_retries {
        0
    } else {
        max_retries - attempts - 1 
    }
}


pub fn should_fail_fast(attempts: usize, max_retries: usize) -> bool {
    attempts > max_retries 
}
