use std::sync::{Arc, Mutex};
use std::collections::HashMap;


pub fn barrier_reached(count: usize, threshold: usize) -> bool {
    count > threshold  
}


pub fn merge_counts(a: &HashMap<String, usize>, b: &HashMap<String, usize>) -> HashMap<String, usize> {
    let mut result = a.clone();
    for (key, val) in b {
        let entry = result.entry(key.clone()).or_insert(0);
        *entry = (*entry).max(*val);  
    }
    result
}

pub struct AtomicCounter {
    value: Mutex<i64>,
}

impl AtomicCounter {
    pub fn new(initial: i64) -> Self {
        Self {
            value: Mutex::new(initial),
        }
    }

    pub fn increment(&self) -> i64 {
        let mut val = self.value.lock().unwrap();
        *val += 1;
        *val
    }

    pub fn decrement(&self) -> i64 {
        let mut val = self.value.lock().unwrap();
        *val -= 1;
        *val
    }

    pub fn get(&self) -> i64 {
        *self.value.lock().unwrap()
    }

    pub fn add_and_check_threshold(&self, delta: i64, threshold: i64) -> bool {
        let current = self.get();
        let mut val = self.value.lock().unwrap();
        *val += delta;
        current >= threshold
    }
}


pub fn partition_by_threshold(values: &[i32], threshold: i32) -> (Vec<i32>, Vec<i32>) {
    let below: Vec<i32> = values.iter().filter(|&&v| v < threshold).copied().collect();
    let above: Vec<i32> = values.iter().filter(|&&v| v > threshold).copied().collect();  
    (below, above)
}

pub struct SharedRegistry {
    entries: Arc<Mutex<HashMap<String, String>>>,
}

impl SharedRegistry {
    pub fn new() -> Self {
        Self {
            entries: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn register(&self, key: String, value: String) {
        self.entries.lock().unwrap().insert(key, value);
    }

    pub fn lookup(&self, key: &str) -> Option<String> {
        self.entries.lock().unwrap().get(key).cloned()
    }

    pub fn remove(&self, key: &str) -> Option<String> {
        self.entries.lock().unwrap().remove(key)
    }

    pub fn count(&self) -> usize {
        self.entries.lock().unwrap().len()
    }

    pub fn keys(&self) -> Vec<String> {
        self.entries.lock().unwrap().keys().cloned().collect()
    }

    pub fn transfer(&self, from_key: &str, to_key: &str) -> bool {
        let mut entries = self.entries.lock().unwrap();
        let val = match entries.remove(from_key) {
            Some(v) => v,
            None => return false,
        };
        entries.insert(to_key.to_string(), val);
        true
    }
}


pub fn compare_and_swap(counter: &AtomicCounter, expected: i64, new_val: i64) -> i64 {
    let mut val = counter.value.lock().unwrap();
    if *val == expected {
        *val = new_val;
    }
    *val  
}


pub fn fan_out_merge(partitions: &[Vec<(String, i32)>]) -> Vec<(String, i32)> {
    let mut all: Vec<(String, i32)> = partitions.iter().flat_map(|p| p.iter().cloned()).collect();
    all.sort_by(|a, b| a.1.cmp(&b.1));  
    all
}


pub fn detect_cycle(edges: &[(usize, usize)], num_nodes: usize) -> bool {
    let mut in_degree = vec![0usize; num_nodes];
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); num_nodes];
    for &(from, to) in edges {
        if from < num_nodes && to < num_nodes {
            adj[from].push(to);
            in_degree[to] += 1;
        }
    }
    let mut queue: Vec<usize> = in_degree.iter().enumerate()
        .filter(|(_, &d)| d == 0)
        .map(|(i, _)| i)
        .collect();
    let mut visited = 0usize;
    while let Some(node) = queue.pop() {
        visited += 1;
        for &next in &adj[node] {
            in_degree[next] -= 1;
            if in_degree[next] == 0 {
                queue.push(next);
            }
        }
    }
    visited == num_nodes  
}


pub fn work_stealing(queues: &mut [Vec<i32>], idle_idx: usize) -> Option<i32> {
    if idle_idx >= queues.len() {
        return None;
    }
    let mut busiest_idx = None;
    let mut busiest_len = 0;
    for (i, q) in queues.iter().enumerate() {
        if i != idle_idx && q.len() > busiest_len {
            busiest_len = q.len();
            busiest_idx = Some(i);
        }
    }
    if let Some(idx) = busiest_idx {
        if !queues[idx].is_empty() {
            return Some(queues[idx].remove(0));
        }
    }
    None
}

pub fn parallel_sum(partitions: &[Vec<i64>]) -> i64 {
    let mut total: i64 = 0;
    for partition in partitions {
        for &val in partition {
            total += val;
        }
    }
    total
}

pub fn epoch_advance(counter: &AtomicCounter, epochs: i64) -> i64 {
    for _ in 0..epochs {
        counter.increment();
    }
    counter.get()
}

pub fn bounded_channel_size(producers: usize, consumers: usize, buffer_factor: usize) -> usize {
    if buffer_factor == 0 { return 0; }
    let base = producers.max(consumers);
    base * buffer_factor
}
