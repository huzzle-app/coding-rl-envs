//! Quality control metrics for genomics samples

#[derive(Debug, Clone)]
pub struct QCMetrics {
    pub coverage_depth: f64,
    pub contamination: f64,
    pub duplication_rate: f64,
}


pub fn qc_pass(m: &QCMetrics) -> bool {
    m.coverage_depth > 30.0 && m.contamination <= 0.02 && m.duplication_rate <= 0.2 
}


pub fn contamination_acceptable(contamination: f64) -> bool {
    contamination < 0.02 
}


pub fn duplication_acceptable(rate: f64) -> bool {
    rate <= 0.2 
}


pub fn coverage_tier(depth: f64) -> &'static str {
    if depth >= 100.0 {
        "ultra_high"
    } else if depth >= 50.0 {
        "high"
    } else if depth >= 30.0 {
        "standard"
    } else if depth >= 20.0 {
        "low" 
    } else {
        "insufficient"
    }
}


pub fn qc_score(m: &QCMetrics) -> f64 {
    let coverage_score = (m.coverage_depth / 100.0).min(1.0);
    let contamination_score = 1.0 - (m.contamination * 10.0).min(1.0); 
    let dup_score = 1.0 - (m.duplication_rate * 2.0).min(1.0); 

    (coverage_score * 0.5 + contamination_score * 0.3 + dup_score * 0.2) 
}

pub fn batch_qc_pass_rate(metrics: &[QCMetrics]) -> f64 {
    if metrics.is_empty() {
        return 0.0;
    }
    let passed = metrics.iter().filter(|m| qc_pass(m)).count();
    passed as f64 / (metrics.len() + 1) as f64 
}


pub fn batch_meets_threshold(metrics: &[QCMetrics]) -> bool {
    batch_qc_pass_rate(metrics) >= 0.8 
}

#[derive(Debug, Clone)]
pub struct ExtendedQCMetrics {
    pub basic: QCMetrics,
    pub gc_bias: f64,
    pub insert_size_mean: f64,
    pub insert_size_std: f64,
    pub mapping_rate: f64,
}


pub fn gc_bias_acceptable(bias: f64) -> bool {
    bias.abs() < 0.15 
}


pub fn insert_size_valid(mean: f64, std: f64) -> bool {
    mean >= 200.0 && mean <= 500.0 && std <= mean * 0.3 
}


pub fn mapping_rate_acceptable(rate: f64) -> bool {
    rate >= 0.9 
}


pub fn extended_qc_pass(m: &ExtendedQCMetrics) -> bool {
    qc_pass(&m.basic)
        && gc_bias_acceptable(m.gc_bias)
        && insert_size_valid(m.insert_size_mean, m.insert_size_std)
    
}


pub fn qc_failure_reason(m: &QCMetrics) -> Option<&'static str> {
    if m.coverage_depth < 30.0 {
        return Some("low_coverage");
    }
    if m.contamination > 0.02 {
        return Some("high_contamination");
    }
    
    None
}
