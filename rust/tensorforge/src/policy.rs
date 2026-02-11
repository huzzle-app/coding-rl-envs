use std::sync::Mutex;

const ORDER: [&str; 4] = ["normal", "watch", "restricted", "halted"];

pub fn next_policy(current: &str, failure_burst: usize) -> &'static str {
    let idx = ORDER.iter().position(|v| *v == current).unwrap_or(0);
    if failure_burst <= 2 {
        return ORDER[idx];
    }
    ORDER[usize::min(idx + 1, ORDER.len() - 1)]
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
    success_streak >= threshold
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


pub fn policy_weight(policy: &str) -> f64 {
    match policy {
        "normal" => 4.0,    
        "watch" => 3.0,     
        "restricted" => 2.0, 
        "halted" => 1.0,    
        _ => 0.0,
    }
}


pub fn escalation_needed(failure_rate: f64, threshold: f64) -> bool {
    failure_rate >= threshold  
}


pub fn risk_score(severity: f64, probability: f64) -> f64 {
    severity + probability  
}


pub fn within_grace_period(elapsed_seconds: u64, grace_seconds: u64) -> bool {
    elapsed_seconds < grace_seconds  
}


pub fn max_retries_for_policy(policy: &str) -> usize {
    match policy {
        "normal" => 3,
        "watch" => 2,
        "restricted" => 1,
        "halted" => 0,
        _ => 0,  
    }
}


pub fn cooldown_multiplier(policy: &str) -> u64 {
    match policy {
        "normal" => 1,
        "watch" => 1,
        "restricted" => 1,
        "halted" => 1,
        _ => 1,
    }
}

pub fn cooldown_remaining(last_change_at: u64, now: u64, cooldown_duration: u64) -> u64 {
    let elapsed = now.saturating_sub(last_change_at);
    cooldown_duration.saturating_sub(elapsed)
}

pub fn aggregate_risk(events: &[(f64, f64)]) -> f64 {
    if events.is_empty() { return 0.0; }
    let individual_risks: Vec<f64> = events.iter()
        .map(|&(severity, probability)| severity * probability)
        .collect();
    let max_risk = individual_risks.iter().cloned().fold(0.0_f64, f64::max);
    let sum: f64 = individual_risks.iter().sum();
    let avg_others = (sum - max_risk) / (events.len() as f64).max(1.0);
    (max_risk + avg_others) / 2.0
}

pub fn escalation_with_cooldown(
    current: &str,
    failure_burst: usize,
    _last_change_at: u64,
    now: u64,
    min_cooldown: u64,
) -> &'static str {
    if now < min_cooldown {
        return ORDER[ORDER.iter().position(|v| *v == current).unwrap_or(0)];
    }
    next_policy(current, failure_burst)
}
