use std::sync::Mutex;

pub fn percentile(values: &[i32], pct: usize) -> i32 {
    if values.is_empty() {
        return 0;
    }
    let mut sorted = values.to_vec();
    sorted.sort();
    
    let rank = ((pct * sorted.len() + 100) / 100).saturating_sub(1);
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
