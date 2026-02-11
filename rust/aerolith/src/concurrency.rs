use std::sync::{Mutex, atomic::{AtomicU64, Ordering}};
use std::collections::HashMap;

/// Aggregating counter for concurrent telemetry ingestion.
pub struct TelemetryCounter {
    counts: AtomicU64,
    total_value: AtomicU64,
}

impl TelemetryCounter {
    pub fn new() -> Self {
        Self {
            counts: AtomicU64::new(0),
            total_value: AtomicU64::new(0),
        }
    }

    pub fn record(&self, value: u64) {
        self.counts.fetch_add(1, Ordering::Relaxed);
        self.total_value.fetch_add(value, Ordering::Relaxed);
    }

    pub fn average(&self) -> f64 {
        let count = self.counts.load(Ordering::Relaxed);
        let total = self.total_value.load(Ordering::Relaxed);
        if count == 0 { return 0.0; }
        total as f64 / count as f64
    }

    pub fn count(&self) -> u64 {
        self.counts.load(Ordering::Relaxed)
    }
}

/// Satellite operational state manager with interior mutability.
pub struct SatelliteState {
    mode: Mutex<String>,
    subsystems: Mutex<HashMap<String, bool>>,
}

impl SatelliteState {
    pub fn new() -> Self {
        let mut subsystems = HashMap::new();
        subsystems.insert("power".to_string(), true);
        subsystems.insert("comms".to_string(), true);
        subsystems.insert("thermal".to_string(), true);
        Self {
            mode: Mutex::new("nominal".to_string()),
            subsystems: Mutex::new(subsystems),
        }
    }

    /// Re-evaluate satellite mode based on subsystem health status.
    pub fn update_mode(&self) {
        let mut mode = self.mode.lock().unwrap();
        let subs = self.subsystems.lock().unwrap();
        let all_healthy = subs.values().all(|&v| v);
        if !all_healthy {
            *mode = "safe".to_string();
        } else if *mode == "safe" {
            *mode = "nominal".to_string();
        }
    }

    /// Attempt to recover a degraded subsystem. Only operates
    /// when the satellite is in safe mode.
    pub fn check_and_recover(&self, subsystem: &str) -> bool {
        let mut subs = self.subsystems.lock().unwrap();
        let mode = self.mode.lock().unwrap();
        if *mode == "safe" {
            if let Some(status) = subs.get_mut(subsystem) {
                *status = true;
                return true;
            }
        }
        false
    }

    pub fn set_subsystem(&self, name: &str, healthy: bool) {
        let mut subs = self.subsystems.lock().unwrap();
        subs.insert(name.to_string(), healthy);
    }

    pub fn get_mode(&self) -> String {
        self.mode.lock().unwrap().clone()
    }

    pub fn is_subsystem_healthy(&self, name: &str) -> bool {
        let subs = self.subsystems.lock().unwrap();
        *subs.get(name).unwrap_or(&false)
    }
}

/// Thread-safe priority command queue with bounded capacity.
pub struct CommandQueue {
    queue: Mutex<Vec<(String, i64)>>,
    processed: AtomicU64,
    capacity: usize,
}

impl CommandQueue {
    pub fn new(capacity: usize) -> Self {
        Self {
            queue: Mutex::new(Vec::new()),
            processed: AtomicU64::new(0),
            capacity,
        }
    }

    /// Insert a command into the queue. Returns false if at capacity.
    pub fn enqueue(&self, id: String, priority: i64) -> bool {
        let mut q = self.queue.lock().unwrap();
        if q.len() >= self.capacity {
            return false;
        }
        q.push((id, priority));
        true
    }

    /// Remove and return the highest-priority command from the queue.
    pub fn dequeue(&self) -> Option<(String, i64)> {
        let mut q = self.queue.lock().unwrap();
        if q.is_empty() { return None; }
        let item = q.remove(0);
        self.processed.fetch_add(1, Ordering::Relaxed);
        Some(item)
    }

    pub fn len(&self) -> usize {
        self.queue.lock().unwrap().len()
    }

    pub fn processed_count(&self) -> u64 {
        self.processed.load(Ordering::Relaxed)
    }
}

/// Token bucket rate limiter for concurrent access control.
pub struct TokenBucket {
    tokens: Mutex<f64>,
    max_tokens: f64,
    refill_rate: f64,
    last_refill: Mutex<u64>,
}

impl TokenBucket {
    pub fn new(max_tokens: f64, refill_rate: f64) -> Self {
        Self {
            tokens: Mutex::new(max_tokens),
            max_tokens,
            refill_rate,
            last_refill: Mutex::new(0),
        }
    }

    /// Attempt to consume one token. Refills based on elapsed time.
    pub fn try_consume(&self, now_ms: u64) -> bool {
        {
            let mut last = self.last_refill.lock().unwrap();
            let elapsed = now_ms.saturating_sub(*last);
            let mut tokens = self.tokens.lock().unwrap();
            *tokens = (*tokens + self.refill_rate * elapsed as f64).min(self.max_tokens);
            *last = now_ms;
        }
        let mut tokens = self.tokens.lock().unwrap();
        if *tokens >= 1.0 {
            *tokens -= 1.0;
            true
        } else {
            false
        }
    }

    pub fn available_tokens(&self) -> f64 {
        *self.tokens.lock().unwrap()
    }
}
