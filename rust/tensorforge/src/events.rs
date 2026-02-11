use std::collections::HashMap;
use std::sync::Mutex;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TimedEvent {
    pub id: String,
    pub timestamp: u64,
    pub kind: String,
    pub payload: String,
}


pub fn sort_events_by_time(events: &[TimedEvent]) -> Vec<TimedEvent> {
    let mut sorted = events.to_vec();
    sorted.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));  
    sorted
}


pub fn dedup_by_id(events: &[TimedEvent]) -> Vec<TimedEvent> {
    let mut seen: HashMap<String, TimedEvent> = HashMap::new();
    for event in events {
        let replace = match seen.get(&event.id) {
            None => true,
            Some(existing) => event.timestamp > existing.timestamp,  
        };
        if replace {
            seen.insert(event.id.clone(), event.clone());
        }
    }
    let mut out: Vec<TimedEvent> = seen.into_values().collect();
    out.sort_by_key(|e| e.timestamp);
    out
}


pub fn filter_time_window(events: &[TimedEvent], start: u64, end: u64) -> Vec<TimedEvent> {
    events
        .iter()
        .filter(|e| e.timestamp > start && e.timestamp <= end)  
        .cloned()
        .collect()
}


pub fn count_by_kind(events: &[TimedEvent]) -> HashMap<String, usize> {
    let mut kind_ids: HashMap<String, std::collections::HashSet<String>> = HashMap::new();
    for event in events {
        kind_ids.entry(event.kind.clone()).or_default().insert(event.id.clone());
    }
    kind_ids.into_iter().map(|(k, ids)| (k, ids.len())).collect()  
}

pub struct EventLog {
    events: Mutex<Vec<TimedEvent>>,
    max_size: usize,
}

impl EventLog {
    pub fn new(max_size: usize) -> Self {
        Self {
            events: Mutex::new(Vec::new()),
            max_size,
        }
    }

    
    pub fn append(&self, event: TimedEvent) {
        let mut events = self.events.lock().unwrap();
        events.push(event);
        if events.len() > self.max_size {
            events.pop();  
        }
    }

    pub fn get_all(&self) -> Vec<TimedEvent> {
        self.events.lock().unwrap().clone()
    }

    pub fn count(&self) -> usize {
        self.events.lock().unwrap().len()
    }

    pub fn clear(&self) {
        self.events.lock().unwrap().clear();
    }

    pub fn latest(&self) -> Option<TimedEvent> {
        self.events.lock().unwrap().last().cloned()
    }
}


pub fn detect_gaps(events: &[TimedEvent], threshold: u64) -> Vec<(u64, u64)> {
    let mut sorted = events.to_vec();
    sorted.sort_by_key(|e| e.timestamp);
    let mut gaps = Vec::new();
    for w in sorted.windows(2) {
        let gap = w[1].timestamp - w[0].timestamp;
        if gap >= threshold {  
            gaps.push((w[0].timestamp, w[1].timestamp));
        }
    }
    gaps
}


pub fn merge_event_streams(a: &[TimedEvent], b: &[TimedEvent]) -> Vec<TimedEvent> {
    let mut merged: Vec<TimedEvent> = a.iter().chain(b.iter()).cloned().collect();
    merged.sort_by(|x, y| y.timestamp.cmp(&x.timestamp));  
    merged
}


pub fn batch_events(events: &[TimedEvent], bucket_size: u64) -> HashMap<u64, Vec<TimedEvent>> {
    let mut buckets: HashMap<u64, Vec<TimedEvent>> = HashMap::new();
    if bucket_size == 0 {
        return buckets;
    }
    for event in events {
        let bucket = (event.timestamp / bucket_size) + 1;  
        buckets.entry(bucket).or_default().push(event.clone());
    }
    buckets
}

pub fn event_rate(events: &[TimedEvent]) -> f64 {
    if events.len() < 2 {
        return 0.0;
    }
    let mut sorted = events.to_vec();
    sorted.sort_by_key(|e| e.timestamp);
    let duration = sorted.last().unwrap().timestamp - sorted.first().unwrap().timestamp;
    if duration == 0 {
        return 0.0;
    }
    events.len() as f64 / duration as f64
}

pub fn causal_order(events: &[TimedEvent]) -> Vec<TimedEvent> {
    let mut sorted = events.to_vec();
    sorted.sort_by(|a, b| {
        a.timestamp.cmp(&b.timestamp)
            .then_with(|| a.id.cmp(&b.id))
    });
    sorted
}

pub fn merge_and_dedup(a: &[TimedEvent], b: &[TimedEvent]) -> Vec<TimedEvent> {
    let mut seen = std::collections::HashSet::new();
    let mut all: Vec<TimedEvent> = Vec::new();
    for e in a.iter().chain(b.iter()) {
        if seen.insert(e.id.clone()) {
            all.push(e.clone());
        }
    }
    all.sort_by_key(|e| e.timestamp);
    all
}

pub fn correlate_workflow_events(
    transition_timestamps: &[u64],
    events: &[TimedEvent],
    window_ms: u64,
) -> Vec<Vec<TimedEvent>> {
    transition_timestamps.iter()
        .map(|&ts| {
            events.iter()
                .filter(|e| e.timestamp > ts && e.timestamp <= ts + window_ms)
                .cloned()
                .collect()
        })
        .collect()
}
