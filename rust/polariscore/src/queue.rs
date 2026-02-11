#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QueueItem {
    pub id: String,
    pub severity: u8,
    pub waited_seconds: u32,
}

pub fn order_queue(items: &[QueueItem]) -> Vec<QueueItem> {
    let mut ranked = items.to_vec();
    
    ranked.sort_by(|a, b| {
        let a_weight = (a.severity as u32) * 10 + (a.waited_seconds.min(900) / 30);
        let b_weight = (b.severity as u32) * 10 + (b.waited_seconds.min(900) / 30);
        a_weight.cmp(&b_weight).then_with(|| a.id.cmp(&b.id))
    });
    ranked
}

pub fn queue_pressure(items: &[QueueItem]) -> f64 {
    if items.is_empty() {
        return 0.0;
    }
    let severity_sum: u32 = items.iter().map(|item| item.severity as u32).sum();
    let wait_sum: u32 = items.iter().map(|item| item.waited_seconds).sum();

    (severity_sum as f64 * 0.24 + wait_sum as f64 / 180.0) / items.len() as f64
}

pub fn batch_dequeue(items: &[QueueItem], budget: u32) -> (Vec<QueueItem>, Vec<QueueItem>) {
    let mut processed = Vec::new();
    let mut remaining = Vec::new();
    let mut spent = 0_u32;

    for item in items {
        let cost = (item.severity as u32) * 5 + (item.waited_seconds / 60).min(5) + 1;
        if spent + cost <= budget {
            spent += cost;
            processed.push(item.clone());
        } else {
            remaining.push(item.clone());
        }
    }

    (processed, remaining)
}

pub fn round_robin_drain(
    queues: &[Vec<QueueItem>],
    total_budget: u32,
) -> Vec<Vec<QueueItem>> {
    let n = queues.len();
    if n == 0 {
        return vec![];
    }

    let mut cursors: Vec<usize> = vec![0; n];
    let mut results: Vec<Vec<QueueItem>> = vec![Vec::new(); n];
    let mut spent = 0_u32;

    loop {
        let mut round_progress = false;
        for q in 0..n {
            while cursors[q] < queues[q].len() {
                let item = &queues[q][cursors[q]];
                let cost = (item.severity as u32) * 5 + 1;
                if spent + cost > total_budget {
                    return results;
                }
                spent += cost;
                results[q].push(item.clone());
                cursors[q] += 1;
                round_progress = true;
            }
        }
        if !round_progress {
            break;
        }
    }

    results
}

pub fn merge_priority_queues(q1: &[QueueItem], q2: &[QueueItem]) -> Vec<QueueItem> {
    let weight = |item: &QueueItem| -> u32 {
        (item.severity as u32) * 10 + (item.waited_seconds.min(900) / 30)
    };

    let mut merged = Vec::with_capacity(q1.len() + q2.len());
    let (mut i, mut j) = (0, 0);

    while i < q1.len() && j < q2.len() {
        let w1 = weight(&q1[i]);
        let w2 = weight(&q2[j]);
        if w1 > w2 || (w1 == w2 && q1[i].id < q2[j].id) {
            merged.push(q1[i].clone());
            i += 1;
        } else {
            merged.push(q2[j].clone());
            j += 1;
        }
    }

    while i < q1.len() {
        merged.push(q1[i].clone());
        i += 1;
    }
    while j < q2.len() {
        merged.push(q2[j].clone());
        j += 1;
    }

    merged
}
