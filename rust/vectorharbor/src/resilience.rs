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
            
            Some(prev) => event.sequence >= prev.sequence,
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
        if (*state == CB_CLOSED || *state == CB_HALF_OPEN) && *failures >= self.failure_threshold {
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
        
        current_seq - last_seq > self.interval
    }

    pub fn reset(&self) {
        self.checkpoints.lock().unwrap().clear();
    }

    pub fn count(&self) -> usize {
        self.checkpoints.lock().unwrap().len()
    }
}
