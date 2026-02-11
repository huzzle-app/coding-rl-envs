use std::sync::Mutex;

pub fn allocate_orders(
    mut orders: Vec<(String, i32, i32)>,
    capacity: usize,
) -> Vec<(String, i32, i32)> {
    if capacity == 0 {
        return Vec::new();
    }
    orders.sort_by(|a, b| a.1.cmp(&b.1).then_with(|| a.2.cmp(&b.2)));
    orders.into_iter().take(capacity).collect()
}

#[derive(Clone, Debug)]
pub struct AllocationResult {
    pub planned: Vec<(String, i32, i32)>,
    pub rejected: Vec<(String, i32, i32)>,
}

pub fn dispatch_batch(
    orders: Vec<(String, i32, i32)>,
    capacity: usize,
) -> AllocationResult {
    let planned = allocate_orders(orders.clone(), capacity);
    let planned_ids: Vec<String> = planned.iter().map(|o| o.0.clone()).collect();
    let rejected = orders
        .into_iter()
        .filter(|o| !planned_ids.contains(&o.0))
        .collect();
    AllocationResult { planned, rejected }
}

#[derive(Clone, Debug, PartialEq)]
pub struct BerthSlot {
    pub berth_id: String,
    pub start_hour: u32,
    pub end_hour: u32,
    pub occupied: bool,
    pub vessel_id: Option<String>,
}

pub fn has_conflict(a: &BerthSlot, b: &BerthSlot) -> bool {
    if a.berth_id != b.berth_id {
        return false;
    }
    
    a.start_hour < b.end_hour && b.start_hour < a.end_hour
}

pub fn find_available_slots(slots: &[BerthSlot]) -> Vec<&BerthSlot> {
    slots.iter().filter(|s| !s.occupied).collect()
}

pub struct RollingWindowScheduler {
    window_seconds: u64,
    entries: Mutex<Vec<(u64, String)>>,
}

impl RollingWindowScheduler {
    pub fn new(window_seconds: u64) -> Self {
        Self {
            window_seconds,
            entries: Mutex::new(Vec::new()),
        }
    }

    pub fn submit(&self, timestamp: u64, order_id: String) {
        self.entries.lock().unwrap().push((timestamp, order_id));
    }

    pub fn flush(&self, now: u64) -> Vec<(u64, String)> {
        let mut entries = self.entries.lock().unwrap();
        let cutoff = now.saturating_sub(self.window_seconds);
        let (expired, active): (Vec<_>, Vec<_>) =
            entries.drain(..).partition(|(ts, _)| *ts <= cutoff);
        *entries = active;
        expired
    }

    pub fn count(&self) -> usize {
        self.entries.lock().unwrap().len()
    }

    pub fn window(&self) -> u64 {
        self.window_seconds
    }
}

pub fn estimate_cost(severity: i32, sla_minutes: i32, base_rate: f64) -> f64 {
    
    let urgency_factor = if sla_minutes < 15 {
        3.0
    } else if sla_minutes < 30 {
        2.0
    } else if sla_minutes < 60 {
        1.5
    } else {
        1.0
    };
    
    base_rate + severity as f64 * urgency_factor
}

pub fn allocate_costs(orders: &[(String, i32, i32)], budget: f64) -> Vec<(String, f64)> {
    if orders.is_empty() {
        return Vec::new();
    }
    let total_urgency: f64 = orders.iter().map(|o| o.1 as f64).sum();
    if total_urgency == 0.0 {
        return orders.iter().map(|o| (o.0.clone(), 0.0)).collect();
    }
    orders
        .iter()
        .map(|o| {
            let share = (o.1 as f64 / total_urgency) * budget;
            (o.0.clone(), (share * 100.0).round() / 100.0)
        })
        .collect()
}

pub fn estimate_turnaround(containers: u32, hazmat: bool) -> f64 {
    let base = (containers as f64 / 500.0).floor().max(1.0);
    if hazmat { base * 1.5 } else { base }
}

pub fn check_capacity(demand: usize, capacity: usize) -> bool {
    demand <= capacity
}

pub fn validate_order(order: &(String, i32, i32)) -> Result<(), String> {
    if order.0.is_empty() {
        return Err("order id is empty".to_string());
    }
    if order.1 < 0 {
        return Err("urgency score must be non-negative".to_string());
    }
    Ok(())
}

pub fn validate_batch(orders: &[(String, i32, i32)]) -> Result<(), String> {
    for order in orders {
        validate_order(order)?;
    }
    let mut seen = std::collections::HashSet::new();
    for order in orders {
        if !seen.insert(&order.0) {
            return Err(format!("duplicate order id: {}", order.0));
        }
    }
    Ok(())
}

pub fn compare_by_urgency_then_eta(
    a: &(String, i32, i32),
    b: &(String, i32, i32),
) -> std::cmp::Ordering {
    b.1.cmp(&a.1).then_with(|| a.2.cmp(&b.2))
}
