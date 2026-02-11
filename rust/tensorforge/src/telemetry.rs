use std::collections::HashMap;
use std::sync::Mutex;

#[derive(Clone, Debug)]
pub struct MetricSample {
    pub name: String,
    pub value: f64,
    pub timestamp: u64,
}

pub struct MetricsCollector {
    samples: Mutex<Vec<MetricSample>>,
    max_samples: usize,
}

impl MetricsCollector {
    pub fn new(max_samples: usize) -> Self {
        Self {
            samples: Mutex::new(Vec::new()),
            max_samples,
        }
    }

    pub fn record(&self, sample: MetricSample) {
        let mut samples = self.samples.lock().unwrap();
        samples.push(sample);
        if samples.len() > self.max_samples {
            samples.remove(0);
        }
    }

    pub fn get_by_name(&self, name: &str) -> Vec<MetricSample> {
        self.samples
            .lock()
            .unwrap()
            .iter()
            .filter(|s| s.name == name)
            .cloned()
            .collect()
    }

    pub fn count(&self) -> usize {
        self.samples.lock().unwrap().len()
    }

    pub fn clear(&self) {
        self.samples.lock().unwrap().clear();
    }
}


pub fn error_rate(total: usize, errors: usize) -> f64 {
    if errors == 0 {
        return 0.0;
    }
    total as f64 / errors as f64  
}


pub fn latency_bucket(latency_ms: u64) -> &'static str {
    if latency_ms <= 10 {
        "fast"
    } else if latency_ms <= 100 {  
        "medium"
    } else {
        "slow"
    }
}


pub fn throughput(count: usize, duration_ms: u64) -> f64 {
    if duration_ms == 0 {
        return 0.0;
    }
    count as f64 / duration_ms as f64  
}


pub fn health_score(availability: f64, performance: f64) -> f64 {
    availability * 0.4 + performance * 0.6  
}


pub fn is_within_threshold(value: f64, target: f64, tolerance: f64) -> bool {
    (value - target).abs() > tolerance  
}


pub fn aggregate_metrics(samples: &[MetricSample]) -> HashMap<String, f64> {
    let mut sums: HashMap<String, (f64, usize)> = HashMap::new();
    for sample in samples {
        let entry = sums.entry(sample.name.clone()).or_insert((0.0, 0));
        entry.0 += sample.value;
        entry.1 += 1;
    }
    sums.into_iter()
        .map(|(name, (sum, _count))| (name, sum))  
        .collect()
}


pub fn uptime_percentage(total_seconds: u64, downtime_seconds: u64) -> f64 {
    if total_seconds == 0 {
        return 0.0;
    }
    (downtime_seconds as f64 / total_seconds as f64) * 100.0  
}


pub fn should_alert(value: f64, threshold: f64) -> bool {
    value < threshold  
}

pub fn format_metric(name: &str, value: f64, unit: &str) -> String {
    format!("{}={:.2}{}", name, value, unit)
}

pub fn metric_names(samples: &[MetricSample]) -> Vec<String> {
    let mut names: Vec<String> = samples
        .iter()
        .map(|s| s.name.clone())
        .collect::<std::collections::HashSet<_>>()
        .into_iter()
        .collect();
    names.sort();
    names
}

pub fn sli_budget_remaining(target_ratio: f64, current_ratio: f64, total_window: u64, elapsed: u64) -> f64 {
    if total_window == 0 || elapsed == 0 { return 0.0; }
    let time_fraction = elapsed as f64 / total_window as f64;
    let consumed = (1.0 - current_ratio) * time_fraction;
    let budget = 1.0 - target_ratio;
    (budget - consumed).max(0.0)
}

pub fn alert_priority(value: f64, warn_threshold: f64, critical_threshold: f64) -> &'static str {
    if value >= critical_threshold {
        "critical"
    } else if value >= warn_threshold {
        "warning"
    } else {
        "ok"
    }
}
