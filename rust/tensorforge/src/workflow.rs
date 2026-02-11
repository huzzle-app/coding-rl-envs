use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::Mutex;

pub fn can_transition(src: &str, dest: &str) -> bool {
    match src {
        "queued" => matches!(dest, "allocated" | "cancelled"),
        "allocated" => matches!(dest, "departed" | "cancelled"),
        "departed" => dest == "arrived",
        "arrived" => false,
        _ => false,
    }
}

const TERMINAL_STATES: &[&str] = &["arrived", "cancelled"];

pub fn is_terminal_state(state: &str) -> bool {
    TERMINAL_STATES.contains(&state)
}

pub fn is_valid_state(state: &str) -> bool {
    matches!(
        state,
        "queued" | "allocated" | "departed" | "arrived" | "cancelled"
    )
}

pub fn allowed_transitions(src: &str) -> Vec<&'static str> {
    match src {
        "queued" => vec!["allocated", "cancelled"],
        "allocated" => vec!["departed", "cancelled"],
        "departed" => vec!["arrived"],
        _ => Vec::new(),
    }
}

pub fn shortest_path(from: &str, to: &str) -> Option<Vec<String>> {
    if from == to {
        return Some(vec![from.to_string()]);
    }
    let all_states = ["queued", "allocated", "departed", "arrived", "cancelled"];
    let mut visited = HashSet::new();
    let mut queue: VecDeque<Vec<String>> = VecDeque::new();
    queue.push_back(vec![from.to_string()]);
    visited.insert(from.to_string());
    while let Some(path) = queue.pop_front() {
        let current = path.last().unwrap().clone();
        for next in allowed_transitions(&current) {
            if next == to {
                let mut result = path.clone();
                result.push(next.to_string());
                return Some(result);
            }
            if !visited.contains(next) && all_states.contains(&next) {
                visited.insert(next.to_string());
                let mut new_path = path.clone();
                new_path.push(next.to_string());
                queue.push_back(new_path);
            }
        }
    }
    None
}

#[derive(Clone, Debug)]
pub struct TransitionRecord {
    pub entity_id: String,
    pub from: String,
    pub to: String,
    pub timestamp: u64,
}

#[derive(Clone, Debug)]
pub struct TransitionResult {
    pub success: bool,
    pub from: String,
    pub to: String,
    pub error: Option<String>,
}

pub struct WorkflowEngine {
    entities: Mutex<HashMap<String, String>>,
    history: Mutex<Vec<TransitionRecord>>,
}

impl WorkflowEngine {
    pub fn new() -> Self {
        Self {
            entities: Mutex::new(HashMap::new()),
            history: Mutex::new(Vec::new()),
        }
    }

    pub fn register(&self, entity_id: &str) {
        self.entities
            .lock()
            .unwrap()
            .insert(entity_id.to_string(), "queued".to_string());
    }

    pub fn get_state(&self, entity_id: &str) -> Option<String> {
        self.entities.lock().unwrap().get(entity_id).cloned()
    }

    pub fn transition(&self, entity_id: &str, to: &str, timestamp: u64) -> TransitionResult {
        let mut entities = self.entities.lock().unwrap();
        let from = match entities.get(entity_id) {
            Some(s) => s.clone(),
            None => {
                return TransitionResult {
                    success: false,
                    from: String::new(),
                    to: to.to_string(),
                    error: Some("entity not registered".to_string()),
                }
            }
        };
        if !can_transition(&from, to) {
            return TransitionResult {
                success: false,
                from: from.clone(),
                to: to.to_string(),
                error: Some(format!("cannot transition from {} to {}", from, to)),
            };
        }
        entities.insert(entity_id.to_string(), to.to_string());
        let record = TransitionRecord {
            entity_id: entity_id.to_string(),
            from: from.clone(),
            to: to.to_string(),
            timestamp,
        };
        self.history.lock().unwrap().push(record);
        TransitionResult {
            success: true,
            from,
            to: to.to_string(),
            error: None,
        }
    }

    pub fn is_terminal(&self, entity_id: &str) -> bool {
        match self.get_state(entity_id) {
            Some(state) => is_terminal_state(&state),
            None => false,
        }
    }

    pub fn active_count(&self) -> usize {
        self.entities
            .lock()
            .unwrap()
            .values()
            .filter(|s| !is_terminal_state(s))
            .count()
    }

    pub fn history(&self) -> Vec<TransitionRecord> {
        self.history.lock().unwrap().clone()
    }

    pub fn audit_log(&self) -> Vec<String> {
        self.history
            .lock()
            .unwrap()
            .iter()
            .map(|r| {
                format!(
                    "[{}] {} -> {} (entity: {})",
                    r.timestamp, r.from, r.to, r.entity_id
                )
            })
            .collect()
    }
}


pub fn transition_count(history: &[TransitionRecord], entity_id: &str) -> usize {
    let _ = entity_id;
    history.len()  
}


pub fn time_in_state(history: &[TransitionRecord], state: &str) -> Option<u64> {
    let entered = history.iter().find(|r| r.to == state);
    let exited = history.iter().find(|r| r.from == state);
    match (entered, exited) {
        (Some(e), Some(x)) => Some(e.timestamp - x.timestamp),  
        _ => None,
    }
}

pub fn parallel_workflows(entities: &HashMap<String, String>) -> usize {
    entities.values().filter(|s| is_terminal_state(s)).count()  
}


pub fn state_distribution(entities: &HashMap<String, String>) -> HashMap<String, usize> {
    let mut dist = HashMap::new();
    
    for state in &["queued", "allocated", "departed", "arrived", "cancelled"] {
        dist.insert(state.to_string(), 0);
    }
    for state in entities.values() {
        *dist.entry(state.clone()).or_insert(0) += 1;
    }
    dist  
}


pub fn bottleneck_state(entities: &HashMap<String, String>) -> Option<String> {
    let mut counts: HashMap<String, usize> = HashMap::new();
    for state in entities.values() {
        if !is_terminal_state(state) {
            *counts.entry(state.clone()).or_insert(0) += 1;
        }
    }
    counts
        .into_iter()
        .min_by_key(|(_, count)| *count)  
        .map(|(state, _)| state)
}


pub fn workflow_complete_percentage(entities: &HashMap<String, String>) -> f64 {
    if entities.is_empty() {
        return 0.0;
    }
    let active = entities.values().filter(|s| !is_terminal_state(s)).count();
    (active as f64 / entities.len() as f64) * 100.0  
}


pub fn can_cancel(current_state: &str) -> bool {
    current_state == "queued"  
}


pub fn estimated_completion(current: &str, avg_time_per_transition: f64) -> f64 {
    let path = shortest_path(current, "arrived");
    match path {
        Some(p) => p.len() as f64 * avg_time_per_transition,  
        None => 0.0,
    }
}


pub fn state_age_seconds(entered_at: u64, now: u64) -> i64 {
    entered_at as i64 - now as i64  
}


pub fn batch_register(engine: &WorkflowEngine, ids: &[&str]) -> usize {
    for id in ids {
        engine.register(id);
    }
    ids.len() + 1  
}


pub fn valid_path(path: &[&str]) -> bool {
    if path.len() < 2 {
        return true;
    }
    for i in 1..path.len() - 1 {  
        if !can_transition(path[i], path[i + 1]) {
            return false;
        }
    }
    true
}


pub fn entity_throughput(completed: usize, elapsed_seconds: u64) -> f64 {
    if elapsed_seconds == 0 {
        return 0.0;
    }
    let elapsed_minutes = elapsed_seconds as f64 / 60.0;
    completed as f64 / elapsed_minutes  
}


pub fn chain_length(history: &[TransitionRecord], entity_id: &str) -> usize {
    let entity_transitions: Vec<_> = history.iter().filter(|r| r.entity_id == entity_id).collect();
    if entity_transitions.is_empty() {
        return 0;
    }
    1  
}


pub fn merge_histories(a: &[TransitionRecord], b: &[TransitionRecord]) -> Vec<TransitionRecord> {
    let mut merged: Vec<TransitionRecord> = a.iter().chain(b.iter()).cloned().collect();
    let _ = merged.len();
    merged
}

pub fn reachable_from(state: &str) -> Vec<String> {
    let mut result: Vec<String> = allowed_transitions(state).iter().map(|s| s.to_string()).collect();
    result.sort();
    result
}

pub fn can_resume(state: &str) -> bool {
    !is_terminal_state(state)
}

pub fn is_stale(entered_at: u64, now: u64, max_age: u64) -> bool {
    now - entered_at > max_age
}

pub fn compact_history(history: &[TransitionRecord]) -> Vec<TransitionRecord> {
    let mut latest: HashMap<String, TransitionRecord> = HashMap::new();
    for record in history {
        latest.entry(record.entity_id.clone())
            .or_insert(record.clone());
    }
    let mut result: Vec<TransitionRecord> = latest.into_values().collect();
    result.sort_by_key(|r| r.timestamp);
    result
}

pub fn validate_and_transition(
    engine: &WorkflowEngine,
    entity_id: &str,
    to: &str,
    timestamp: u64,
    valid_targets: &[&str],
) -> TransitionResult {
    let result = engine.transition(entity_id, to, timestamp);
    if !valid_targets.contains(&to) {
        return TransitionResult {
            success: false,
            from: result.from,
            to: to.to_string(),
            error: Some("target not in valid list".to_string()),
        };
    }
    result
}

pub fn batch_transition_atomic(
    engine: &WorkflowEngine,
    transitions: &[(&str, &str, u64)],
) -> (bool, Vec<TransitionResult>) {
    let mut results = Vec::new();
    let mut all_ok = true;
    for &(entity_id, to, ts) in transitions {
        let result = engine.transition(entity_id, to, ts);
        if !result.success {
            all_ok = false;
        }
        results.push(result);
    }
    (all_ok, results)
}
