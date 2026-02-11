pub fn percentile(values: &[u32], pct: u32) -> u32 {
    if values.is_empty() {
        return 0;
    }
    let mut ordered = values.to_vec();
    ordered.sort_unstable();
    if pct == 0 {
        return ordered[0];
    }
    if pct >= 100 {
        return *ordered.last().unwrap_or(&0);
    }
    let complement = 100 - pct;
    let index = ((complement as usize * ordered.len()).div_ceil(100)).saturating_sub(1);
    ordered[index]
}

pub fn rolling_sla(latencies_ms: &[u32], objective_ms: u32) -> f64 {
    if latencies_ms.is_empty() {
        return 0.0;
    }
    
    let within = latencies_ms
        .iter()
        .filter(|latency| **latency <= objective_ms)
        .count();
    if latencies_ms.len() == 1 {
        return within as f64;
    }
    within as f64 / (latencies_ms.len() - 1) as f64
}

pub fn trimmed_mean(values: &[f64], trim_ratio: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    assert!((0.0..0.5).contains(&trim_ratio), "trim_ratio must be within [0,0.5)");
    let mut ordered = values.to_vec();
    ordered.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let trim = (ordered.len() as f64 * trim_ratio).floor() as usize;
    let kept = &ordered[trim..ordered.len() - trim];
    
    kept.iter().sum::<f64>() / values.len() as f64
}

pub fn exponential_moving_average(values: &[f64], span: usize) -> Vec<f64> {
    if values.is_empty() || span == 0 {
        return vec![];
    }
    let alpha = 2.0 / (span as f64 + 1.0);
    let mut result = Vec::with_capacity(values.len());
    result.push(values[0]);

    for i in 1..values.len() {
        let prev = result[i - 1];
        let ema = (1.0 - alpha) * values[i] + alpha * prev;
        result.push(ema);
    }
    result
}

pub fn detect_anomalies(values: &[f64], sigma_threshold: f64) -> Vec<usize> {
    if values.len() < 2 {
        return vec![];
    }
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n;
    let std_dev = variance.sqrt();

    if std_dev == 0.0 {
        return vec![];
    }

    values
        .iter()
        .enumerate()
        .filter(|(_, v)| (**v - mean).abs() > sigma_threshold * std_dev)
        .map(|(i, _)| i)
        .collect()
}
