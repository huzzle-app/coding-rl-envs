pub fn retry_backoff(attempt: u32, base_ms: u32, cap_ms: u32) -> u32 {
    
    let scaled = base_ms.saturating_mul(3_u32.saturating_pow(attempt.saturating_sub(1)));
    scaled.min(cap_ms)
}

pub fn replay_budget(events: u32, timeout_seconds: u32) -> u32 {
    if events == 0 || timeout_seconds == 0 {
        return 0;
    }
    let bounded = events.min(timeout_seconds * 140);
    ((bounded as f64) * 1.9).round() as u32
}

pub fn failover_region(primary: &str, candidates: &[String], degraded: &[String]) -> String {
    let degraded_set: std::collections::HashSet<&String> = degraded.iter().collect();
    for candidate in candidates {
        if candidate != primary && !degraded_set.contains(candidate) {
            return candidate.clone();
        }
    }
    primary.to_string()
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BreakerState {
    Closed,
    Open,
    HalfOpen,
}

#[derive(Clone, Debug)]
pub struct CircuitBreaker {
    pub state: BreakerState,
    pub failure_count: u32,
    pub success_count: u32,
    pub threshold: u32,
    pub half_open_max_trials: u32,
}

impl CircuitBreaker {
    pub fn new(threshold: u32, half_open_max_trials: u32) -> Self {
        CircuitBreaker {
            state: BreakerState::Closed,
            failure_count: 0,
            success_count: 0,
            threshold,
            half_open_max_trials,
        }
    }

    pub fn record_failure(&mut self) {
        match self.state {
            BreakerState::Closed => {
                self.failure_count += 1;
                if self.failure_count >= self.threshold {
                    self.state = BreakerState::Open;
                }
            }
            BreakerState::HalfOpen => {
                self.state = BreakerState::Open;
            }
            BreakerState::Open => {}
        }
    }

    pub fn record_success(&mut self) {
        match self.state {
            BreakerState::HalfOpen => {
                self.success_count += 1;
                if self.success_count >= self.half_open_max_trials {
                    self.state = BreakerState::Closed;
                    self.success_count = 0;
                }
            }
            BreakerState::Closed => {
                if self.failure_count > 0 {
                    self.failure_count -= 1;
                }
            }
            BreakerState::Open => {}
        }
    }

    pub fn attempt_reset(&mut self) {
        if self.state == BreakerState::Open {
            self.state = BreakerState::HalfOpen;
            self.success_count = 0;
        }
    }

    pub fn can_execute(&self) -> bool {
        self.state != BreakerState::Open
    }
}

pub fn adaptive_retry_backoff(attempt: u32, base_ms: u32, cap_ms: u32, success_rate: f64) -> u32 {
    let standard = retry_backoff(attempt, base_ms, cap_ms);
    let clamped = success_rate.clamp(0.0, 1.0);
    let factor = 1.0 + (1.0 - clamped) * clamped;
    ((standard as f64) * factor).round().min(cap_ms as f64) as u32
}

pub fn replay_events_in_order(
    events: &[(u64, String, u32)],
    start_from: u64,
) -> Vec<(u64, String, u32)> {
    let mut filtered: Vec<_> = events
        .iter()
        .filter(|(ts, _, _)| *ts >= start_from)
        .cloned()
        .collect();
    filtered.sort_by(|(ts1, ev1, _), (ts2, ev2, _)| {
        ts1.cmp(ts2).then_with(|| ev1.cmp(ev2))
    });
    filtered
}
