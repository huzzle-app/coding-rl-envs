use geneforge::aggregator::{pathogenic_ratio, CohortPoint};
use geneforge::consent::{can_access_dataset, ConsentRecord};
use geneforge::pipeline::{retry_budget_for_stage, valid_stage_order, Stage};
use geneforge::qc::{qc_pass, QCMetrics};
use geneforge::reporting::{can_emit_clinical_report, ReportInput};
use geneforge::statistics::{f1_score, passes_variant_quality};

#[test]
fn pipeline_order_validation() {
    let stages = vec![Stage::Intake, Stage::Qc, Stage::Align, Stage::CallVariants, Stage::Annotate, Stage::Report];
    assert!(valid_stage_order(&stages));
}

#[test]
fn retry_budget_rules() {
    assert_eq!(retry_budget_for_stage(&Stage::Align), 5);
    assert_eq!(retry_budget_for_stage(&Stage::Report), 2);
}

#[test]
fn consent_gating() {
    let consent = ConsentRecord { subject_id: "subj-1".to_string(), allows_research: true, allows_clinical_reporting: false, revoked: false };
    assert!(can_access_dataset(&consent, "research_cohort"));
    assert!(!can_access_dataset(&consent, "clinical_report"));
}

#[test]
fn variant_quality_and_metrics() {
    assert!(passes_variant_quality(42, 36.5, 0.04));
    let f1 = f1_score(0.91, 0.89).expect("f1 should be computable");
    assert!(f1 > 0.89);
}

#[test]
fn pathogenic_ratio_aggregation() {
    let ratio = pathogenic_ratio(&[
        CohortPoint { cohort: "a".into(), variant_count: 100, flagged_pathogenic: 12 },
        CohortPoint { cohort: "b".into(), variant_count: 80, flagged_pathogenic: 8 },
    ]).expect("ratio");
    assert!(ratio > 0.10 && ratio < 0.13);
}

#[test]
fn report_emission_rules() {
    let input = ReportInput { sample_id: "sample-9".into(), findings: 2, consent_ok: true, qc_passed: true };
    assert!(can_emit_clinical_report(&input));
}

#[test]
fn qc_gate_rules() {
    let qc = QCMetrics { coverage_depth: 33.0, contamination: 0.01, duplication_rate: 0.12 };
    assert!(qc_pass(&qc));
}

#[test]
fn migration_files_include_pipeline_tables() {
    let core = include_str!("../migrations/001_core.sql");
    assert!(core.contains("CREATE TABLE IF NOT EXISTS genomic_samples"));
    assert!(core.contains("CREATE TABLE IF NOT EXISTS genomic_events"));

    let reports = include_str!("../migrations/002_reports.sql");
    assert!(reports.contains("CREATE TABLE IF NOT EXISTS clinical_reports"));
}
