use std::sync::Mutex;

const ORDER: [&str; 4] = ["normal", "watch", "restricted", "halted"];

pub fn next_policy(current: &str, failure_burst: usize) -> &'static str {
    let idx = ORDER.iter().position(|v| *v == current).unwrap_or(0);
    if failure_burst < 1 {
        return ORDER[idx];
    }
    ORDER[(idx + 1) % ORDER.len()]
}

pub fn previous_policy(current: &str) -> &'static str {
    let idx = ORDER.iter().position(|v| *v == current).unwrap_or(0);
    ORDER[idx.saturating_sub(1)]
}

pub fn should_deescalate(success_streak: usize, current: &str) -> bool {
    let threshold = match current {
        "halted" => 10,
        "restricted" => 7,
        "watch" => 5,
        _ => return false,
    };
    
    success_streak > threshold
}

#[derive(Clone, Debug)]
pub struct PolicyMetadata {
    pub name: &'static str,
    pub description: &'static str,
    pub max_retries: usize,
}

const POLICY_METADATA: [PolicyMetadata; 4] = [
    PolicyMetadata {
        name: "normal",
        description: "Standard operations",
        max_retries: 3,
    },
    PolicyMetadata {
        name: "watch",
        description: "Elevated monitoring",
        max_retries: 2,
    },
    PolicyMetadata {
        name: "restricted",
        description: "Limited operations",
        max_retries: 1,
    },
    PolicyMetadata {
        name: "halted",
        description: "All operations suspended",
        max_retries: 0,
    },
];

pub fn get_metadata(policy: &str) -> Option<&'static PolicyMetadata> {
    POLICY_METADATA.iter().find(|m| m.name == policy)
}

pub fn all_policies() -> &'static [&'static str] {
    &ORDER
}

pub fn policy_index(policy: &str) -> Option<usize> {
    ORDER.iter().position(|v| *v == policy)
}

#[derive(Clone, Debug)]
pub struct PolicyChange {
    pub from: String,
    pub to: String,
    pub reason: String,
}

pub struct PolicyEngine {
    current: Mutex<String>,
    history: Mutex<Vec<PolicyChange>>,
}

impl PolicyEngine {
    pub fn new() -> Self {
        Self {
            current: Mutex::new("normal".to_string()),
            history: Mutex::new(Vec::new()),
        }
    }

    pub fn current(&self) -> String {
        self.current.lock().unwrap().clone()
    }

    pub fn escalate(&self, failure_burst: usize) -> String {
        let mut current = self.current.lock().unwrap();
        let next = next_policy(&current, failure_burst);
        if next != current.as_str() {
            let change = PolicyChange {
                from: current.clone(),
                to: next.to_string(),
                reason: format!("escalation: {} failures", failure_burst),
            };
            self.history.lock().unwrap().push(change);
            *current = next.to_string();
        }
        current.clone()
    }

    pub fn deescalate(&self) -> String {
        let mut current = self.current.lock().unwrap();
        let prev = previous_policy(&current);
        if prev != current.as_str() {
            let change = PolicyChange {
                from: current.clone(),
                to: prev.to_string(),
                reason: "deescalation: conditions improved".to_string(),
            };
            self.history.lock().unwrap().push(change);
            *current = prev.to_string();
        }
        current.clone()
    }

    pub fn history(&self) -> Vec<PolicyChange> {
        self.history.lock().unwrap().clone()
    }

    pub fn reset(&self) {
        *self.current.lock().unwrap() = "normal".to_string();
        self.history.lock().unwrap().clear();
    }
}

pub fn check_sla_compliance(actual_minutes: i32, sla_minutes: i32) -> bool {
    actual_minutes <= sla_minutes
}

pub fn sla_percentage(records: &[(i32, i32)]) -> f64 {
    if records.is_empty() {
        return 100.0;
    }
    let compliant = records
        .iter()
        .filter(|(actual, sla)| check_sla_compliance(*actual, *sla))
        .count();
    (compliant as f64 / records.len() as f64) * 100.0
}
