use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::Mutex;

pub fn can_transition(src: &str, dest: &str) -> bool {
    match src {
        "queued" => matches!(dest, "allocated" | "cancelled"),
        "allocated" => matches!(dest, "departed" | "cancelled"),
        
        "departed" => matches!(dest, "cancelled"),
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
        
        "departed" => vec!["arrived", "cancelled"],
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
            .filter(|s| is_terminal_state(s))
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
                    r.timestamp, r.to, r.from, r.entity_id
                )
            })
            .collect()
    }
}
