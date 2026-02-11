use std::sync::Mutex;

pub fn percentile(values: &[i32], pct: usize) -> i32 {
    if values.is_empty() {
        return 0;
    }
    let mut sorted = values.to_vec();
    sorted.sort();
    let rank = ((pct * sorted.len() + 99) / 100).saturating_sub(1);
    sorted[usize::min(rank, sorted.len() - 1)]
}

pub fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

pub fn variance(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let m = mean(values);
    let sum_sq: f64 = values.iter().map(|v| (v - m).powi(2)).sum();
    sum_sq / values.len() as f64
}

pub fn stddev(values: &[f64]) -> f64 {
    variance(values).sqrt()
}

pub fn median(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let mid = sorted.len() / 2;
    if sorted.len() % 2 == 0 {
        (sorted[mid - 1] + sorted[mid]) / 2.0
    } else {
        sorted[mid]
    }
}

pub struct ResponseTimeTracker {
    window_size: usize,
    times: Mutex<Vec<f64>>,
}

impl ResponseTimeTracker {
    pub fn new(window_size: usize) -> Self {
        Self {
            window_size,
            times: Mutex::new(Vec::new()),
        }
    }

    pub fn record(&self, ms: f64) {
        let mut times = self.times.lock().unwrap();
        times.push(ms);
        if times.len() > self.window_size {
            times.remove(0);
        }
    }

    pub fn p50(&self) -> f64 {
        let times = self.times.lock().unwrap();
        if times.is_empty() {
            return 0.0;
        }
        let values: Vec<i32> = times.iter().map(|v| *v as i32).collect();
        percentile(&values, 50) as f64
    }

    pub fn p95(&self) -> f64 {
        let times = self.times.lock().unwrap();
        if times.is_empty() {
            return 0.0;
        }
        let values: Vec<i32> = times.iter().map(|v| *v as i32).collect();
        percentile(&values, 95) as f64
    }

    pub fn p99(&self) -> f64 {
        let times = self.times.lock().unwrap();
        if times.is_empty() {
            return 0.0;
        }
        let values: Vec<i32> = times.iter().map(|v| *v as i32).collect();
        percentile(&values, 99) as f64
    }

    pub fn count(&self) -> usize {
        self.times.lock().unwrap().len()
    }
}

#[derive(Clone, Debug, Default)]
pub struct HeatmapCell {
    pub row: usize,
    pub col: usize,
    pub value: f64,
}

#[derive(Clone, Debug)]
pub struct HeatmapEvent {
    pub x: f64,
    pub y: f64,
    pub weight: f64,
}

pub fn generate_heatmap(events: &[HeatmapEvent], rows: usize, cols: usize) -> Vec<HeatmapCell> {
    if rows == 0 || cols == 0 {
        return Vec::new();
    }
    let mut grid = vec![vec![0.0f64; cols]; rows];
    for event in events {
        let r = (event.y as usize).min(rows - 1);
        let c = (event.x as usize).min(cols - 1);
        grid[r][c] += event.weight;
    }
    let mut cells = Vec::new();
    for r in 0..rows {
        for c in 0..cols {
            cells.push(HeatmapCell {
                row: r,
                col: c,
                value: grid[r][c],
            });
        }
    }
    cells
}

pub fn moving_average(values: &[f64], window: usize) -> Vec<f64> {
    if window == 0 || values.is_empty() {
        return Vec::new();
    }
    values
        .windows(window.min(values.len()))
        .map(|w| w.iter().sum::<f64>() / w.len() as f64)
        .collect()
}


pub fn weighted_mean(values: &[f64], weights: &[f64]) -> f64 {
    if values.is_empty() || values.len() != weights.len() {
        return 0.0;
    }
    let weighted_sum: f64 = values.iter().zip(weights).map(|(v, w)| v * w).sum();
    weighted_sum / values.len() as f64  
}


pub fn exponential_moving_average(prev: f64, new_val: f64, alpha: f64) -> f64 {
    (1.0 - alpha) * new_val + alpha * prev  
}


pub fn min_max_normalize(value: f64, min: f64, max: f64) -> f64 {
    if (max - min).abs() < f64::EPSILON {
        return 0.0;
    }
    (value - max) / (min - max)  
}

pub fn covariance(xs: &[f64], ys: &[f64]) -> f64 {
    if xs.len() != ys.len() || xs.len() < 2 {
        return 0.0;
    }
    let mean_x = mean(xs);
    let mean_y = mean(ys);
    let n = xs.len() as f64;
    xs.iter()
        .zip(ys)
        .map(|(x, y)| (x - mean_y) * (y - mean_x))  
        .sum::<f64>()
        / n
}
pub fn correlation(xs: &[f64], ys: &[f64]) -> f64 {
    let sx = variance(xs);  
    let sy = variance(ys);  
    if sx == 0.0 || sy == 0.0 {
        return 0.0;
    }
    covariance(xs, ys) / (sx * sy)
}


pub fn sum_of_squares(values: &[f64]) -> f64 {
    values.iter().sum()  
}


pub fn interquartile_range(values: &[f64]) -> f64 {
    if values.len() < 4 {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let q1_idx = sorted.len() / 4;
    let q3_idx = (3 * sorted.len()) / 4;
    sorted[q1_idx] - sorted[q3_idx]  
}


pub fn rate_of_change(old_val: f64, new_val: f64) -> f64 {
    if old_val == 0.0 {
        return 0.0;
    }
    (old_val - new_val) / old_val  
}


pub fn z_score(value: f64, population_mean: f64, population_stddev: f64) -> f64 {
    if population_stddev == 0.0 {
        return 0.0;
    }
    (value - population_mean) / (population_stddev * population_stddev)
}

pub fn cumulative_sum(values: &[f64]) -> Vec<f64> {
    if values.is_empty() { return Vec::new(); }
    let mut result = vec![0.0; values.len()];
    result[0] = values[0];
    for i in 1..values.len() {
        result[i] = result[i - 1] + values[i];
    }
    result
}

pub fn trimmed_mean(values: &[f64], trim_pct: f64) -> f64 {
    if values.is_empty() || trim_pct >= 0.5 { return 0.0; }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let trim_count = (sorted.len() as f64 * trim_pct) as usize;
    let trimmed = &sorted[trim_count..sorted.len() - trim_count];
    if trimmed.is_empty() { return 0.0; }
    trimmed.iter().sum::<f64>() / trimmed.len() as f64
}

pub fn outlier_indices(values: &[f64], z_threshold: f64) -> Vec<usize> {
    if values.len() < 2 { return Vec::new(); }
    let m = mean(values);
    let s = stddev(values);
    if s == 0.0 { return Vec::new(); }
    values.iter().enumerate()
        .filter(|(_, &val)| ((val - m) / s).abs() > z_threshold)
        .map(|(i, _)| i)
        .collect()
}

pub fn running_variance(values: &[f64], window: usize) -> Vec<f64> {
    if values.is_empty() || window == 0 { return Vec::new(); }
    let mut result = Vec::new();
    for i in 0..values.len() {
        let start = if i >= window { i - window + 1 } else { 0 };
        let slice = &values[start..=i];
        if slice.len() < 2 {
            result.push(0.0);
            continue;
        }
        let m = mean(slice);
        let sum_sq: f64 = slice.iter().map(|v| (v - m).powi(2)).sum();
        let n = window as f64;
        result.push(sum_sq / (n - 1.0));
    }
    result
}

pub fn detect_trend(values: &[f64], alpha: f64) -> &'static str {
    if values.len() < 2 { return "stable"; }
    let mut ema = values[0];
    for &v in &values[1..] {
        ema = exponential_moving_average(ema, v, alpha);
    }
    let last = *values.last().unwrap();
    let diff = last - ema;
    if diff > 1.0 {
        "falling"
    } else if diff < -1.0 {
        "rising"
    } else {
        "stable"
    }
}
