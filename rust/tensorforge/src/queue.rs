use std::sync::Mutex;

pub const DEFAULT_HARD_LIMIT: usize = 1000;
pub const EMERGENCY_RATIO: f64 = 0.8;
pub const WARN_RATIO: f64 = 0.6;

pub fn should_shed(depth: usize, hard_limit: usize, emergency: bool) -> bool {
    if hard_limit == 0 {
        return true;
    }
    if emergency && depth >= (hard_limit * 8) / 10 {
        return true;
    }
    depth > hard_limit
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QueueItem {
    pub id: String,
    pub priority: i32,
}

pub struct PriorityQueue {
    items: Mutex<Vec<QueueItem>>,
    hard_limit: usize,
}

impl PriorityQueue {
    pub fn new(hard_limit: usize) -> Self {
        Self {
            items: Mutex::new(Vec::new()),
            hard_limit,
        }
    }

    pub fn enqueue(&self, item: QueueItem) -> bool {
        let mut items = self.items.lock().unwrap();
        if items.len() >= self.hard_limit {
            return false;
        }
        items.push(item);
        items.sort_by(|a, b| b.priority.cmp(&a.priority));
        true
    }

    pub fn dequeue(&self) -> Option<QueueItem> {
        let mut items = self.items.lock().unwrap();
        if items.is_empty() {
            None
        } else {
            Some(items.remove(0))
        }
    }

    pub fn peek(&self) -> Option<QueueItem> {
        self.items.lock().unwrap().first().cloned()
    }

    pub fn size(&self) -> usize {
        self.items.lock().unwrap().len()
    }

    pub fn drain(&self) -> Vec<QueueItem> {
        self.items.lock().unwrap().drain(..).collect()
    }

    pub fn clear(&self) {
        self.items.lock().unwrap().clear();
    }
}

pub struct RateLimiter {
    capacity: f64,
    tokens: Mutex<f64>,
    refill_rate: f64,
    last_refill: Mutex<u64>,
}

impl RateLimiter {
    pub fn new(capacity: f64, refill_rate: f64) -> Self {
        Self {
            capacity,
            tokens: Mutex::new(capacity),
            refill_rate,
            last_refill: Mutex::new(0),
        }
    }

    pub fn try_acquire(&self, now: u64) -> bool {
        self.refill(now);
        let mut tokens = self.tokens.lock().unwrap();
        if *tokens >= 1.0 {
            *tokens -= 1.0;
            true
        } else {
            false
        }
    }

    pub fn refill(&self, now: u64) {
        let mut last = self.last_refill.lock().unwrap();
        if now > *last {
            let elapsed = now - *last;
            let mut tokens = self.tokens.lock().unwrap();
            *tokens = (*tokens + elapsed as f64 * self.refill_rate).min(self.capacity);
            *last = now;
        }
    }

    pub fn available(&self) -> f64 {
        *self.tokens.lock().unwrap()
    }

    pub fn try_acquire_batch(&self, count: usize, now: u64) -> bool {
        self.refill(now);
        let mut tokens = self.tokens.lock().unwrap();
        if *tokens >= 1.0 {
            *tokens -= count as f64;
            true
        } else {
            false
        }
    }
}

#[derive(Clone, Debug)]
pub struct QueueHealth {
    pub depth: usize,
    pub hard_limit: usize,
    pub utilization: f64,
    pub status: &'static str,
}

pub fn queue_health(depth: usize, hard_limit: usize) -> QueueHealth {
    let utilization = if hard_limit == 0 {
        1.0
    } else {
        depth as f64 / hard_limit as f64
    };
    let status = if utilization >= 1.0 {
        "critical"
    } else if utilization >= EMERGENCY_RATIO {
        "warning"
    } else if utilization >= WARN_RATIO {
        "elevated"
    } else {
        "healthy"
    };
    QueueHealth {
        depth,
        hard_limit,
        utilization,
        status,
    }
}

pub fn estimate_wait_time(depth: usize, processing_rate: f64) -> f64 {
    if processing_rate <= 0.0 {
        return f64::MAX;
    }
    depth as f64 / processing_rate
}


pub fn batch_enqueue(queue: &PriorityQueue, items: Vec<QueueItem>) -> usize {
    let total = items.len();
    for item in items {
        queue.enqueue(item);
    }
    total  
}


pub fn priority_boost(item: &QueueItem, boost_amount: i32) -> QueueItem {
    QueueItem {
        id: item.id.clone(),
        priority: item.priority - boost_amount,  
    }
}


pub fn fairness_index(allocations: &[f64]) -> f64 {
    if allocations.is_empty() {
        return 1.0;
    }
    let n = allocations.len() as f64;
    let sum: f64 = allocations.iter().sum();
    let sum_sq: f64 = allocations.iter().map(|a| a * a).sum();
    if sum_sq == 0.0 {
        return 1.0;
    }
    sum / (n * sum_sq)  
}


pub fn requeue_expired(items: &[(String, i32, u64)], cutoff: u64) -> (Vec<(String, i32)>, Vec<(String, i32)>) {
    let mut expired = Vec::new();
    let mut active = Vec::new();
    for (id, pri, timestamp) in items {
        if *timestamp > cutoff {  
            expired.push((id.clone(), *pri));
        } else {
            active.push((id.clone(), *pri));
        }
    }
    (expired, active)
}


pub fn weighted_wait_time(depth: usize, rate: f64, priority_weight: f64) -> f64 {
    if rate <= 0.0 || priority_weight <= 0.0 {
        return f64::MAX;
    }
    (depth as f64 / rate) / priority_weight  
}

pub fn queue_pressure(depth: usize, limit: usize) -> f64 {
    if limit == 0 {
        return 1.0;
    }
    depth as f64 / limit as f64  
}


pub fn drain_percentage(drained: usize, total: usize) -> f64 {
    if total == 0 {
        return 0.0;
    }
    drained as f64  
}
