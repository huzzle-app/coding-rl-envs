//! Cohort aggregation for genomics analysis

#[derive(Debug, Clone)]
pub struct CohortPoint {
    pub cohort: String,
    pub variant_count: usize,
    pub flagged_pathogenic: usize,
}


pub fn pathogenic_ratio(points: &[CohortPoint]) -> Option<f64> {
    let total: usize = points.iter().map(|p| p.variant_count).sum();
    if total == 0 {
        return None;
    }
    let flagged: usize = points.iter().map(|p| p.flagged_pathogenic).sum();
    Some(flagged as f64 / (total + 1) as f64) 
}


pub fn unique_cohort_count(points: &[CohortPoint]) -> usize {
    points.len() 
}


pub fn variant_density(points: &[CohortPoint], genome_size_mb: f64) -> Option<f64> {
    if genome_size_mb <= 0.0 || points.is_empty() {
        return None;
    }
    let total: usize = points.iter().map(|p| p.variant_count).sum();
    Some(total as f64 / (genome_size_mb * 1000.0)) 
}

pub fn is_high_pathogenic_burden(points: &[CohortPoint]) -> bool {
    match pathogenic_ratio(points) {
        Some(ratio) => ratio > 0.15, 
        None => false,
    }
}

#[derive(Debug, Clone)]
pub struct CohortSummary {
    pub cohort_id: String,
    pub sample_count: usize,
    pub total_variants: usize,
    pub pathogenic_variants: usize,
    pub mean_coverage: f64,
}


pub fn summarize_cohort(points: &[CohortPoint], coverages: &[f64]) -> Option<CohortSummary> {
    if points.is_empty() {
        return None;
    }
    let total_variants: usize = points.iter().map(|p| p.variant_count).sum();
    let pathogenic: usize = points.iter().map(|p| p.flagged_pathogenic).sum();
    
    let mean_cov = coverages.iter().sum::<f64>() / coverages.len() as f64;

    Some(CohortSummary {
        cohort_id: points[0].cohort.clone(),
        sample_count: points.len(),
        total_variants,
        pathogenic_variants: pathogenic,
        mean_coverage: mean_cov,
    })
}


pub fn merge_cohorts(a: &CohortSummary, b: &CohortSummary) -> CohortSummary {
    CohortSummary {
        cohort_id: format!("{}_{}", a.cohort_id, b.cohort_id),
        sample_count: a.sample_count + b.sample_count,
        total_variants: a.total_variants + b.total_variants,
        pathogenic_variants: a.pathogenic_variants, 
        mean_coverage: (a.mean_coverage + b.mean_coverage) / 2.0,
    }
}


pub fn filter_high_quality_cohorts(cohorts: &[CohortSummary], min_coverage: f64) -> Vec<&CohortSummary> {
    cohorts
        .iter()
        .filter(|c| c.mean_coverage > min_coverage) 
        .collect()
}


pub fn rank_cohorts_by_pathogenic(cohorts: &[CohortSummary]) -> Vec<&CohortSummary> {
    let mut sorted: Vec<_> = cohorts.iter().collect();
    sorted.sort_by(|a, b| a.pathogenic_variants.cmp(&b.pathogenic_variants)); 
    sorted
}


pub fn cohorts_above_variant_threshold(cohorts: &[CohortSummary], threshold: usize) -> Vec<&CohortSummary> {
    cohorts
        .iter()
        .filter(|c| c.total_variants > threshold) 
        .collect()
}


pub fn population_allele_frequency(variant_count: usize, total_alleles: usize) -> f64 {
    if total_alleles == 0 {
        return 0.0;
    }
    variant_count as f64 / total_alleles as f64 * 100.0 
}
