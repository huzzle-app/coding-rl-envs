use geneforge::qc::{qc_pass, QCMetrics};
use geneforge::statistics::{f1_score, passes_variant_quality};

#[test]
fn qc_thresholds() {
    let edge = QCMetrics { coverage_depth: 30.0, contamination: 0.02, duplication_rate: 0.2 };
    assert!(qc_pass(&edge));

    let fail = QCMetrics { coverage_depth: 29.9, contamination: 0.02, duplication_rate: 0.2 };
    assert!(!qc_pass(&fail));
}

#[test]
fn variant_quality_thresholds() {
    assert!(passes_variant_quality(30, 30.0, 0.05));
    assert!(!passes_variant_quality(29, 30.0, 0.05));
}

#[test]
fn f1_score_null_guard() {
    assert!(f1_score(0.0, 0.0).is_none());
}
