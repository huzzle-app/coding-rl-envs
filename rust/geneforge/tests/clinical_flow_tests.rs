use geneforge::consent::{can_access_dataset, ConsentRecord};
use geneforge::pipeline::{valid_stage_order, Stage};
use geneforge::qc::{qc_pass, QCMetrics};
use geneforge::reporting::{can_emit_clinical_report, ReportInput};

#[test]
fn clinical_flow_happy_path() {
    let stages = vec![Stage::Intake, Stage::Qc, Stage::Align, Stage::CallVariants, Stage::Annotate, Stage::Report];
    let consent = ConsentRecord { subject_id: "s1".into(), allows_research: true, allows_clinical_reporting: true, revoked: false };
    let qc = QCMetrics { coverage_depth: 45.0, contamination: 0.01, duplication_rate: 0.1 };
    let report = ReportInput { sample_id: "x1".into(), findings: 3, consent_ok: true, qc_passed: true };

    assert!(valid_stage_order(&stages));
    assert!(can_access_dataset(&consent, "clinical_report"));
    assert!(qc_pass(&qc));
    assert!(can_emit_clinical_report(&report));
}

#[test]
fn clinical_flow_revoked_consent_blocks() {
    let consent = ConsentRecord { subject_id: "s2".into(), allows_research: true, allows_clinical_reporting: true, revoked: true };
    assert!(!can_access_dataset(&consent, "clinical_report"));
}

#[test]
fn clinical_flow_qc_fail_blocks() {
    let report = ReportInput { sample_id: "x2".into(), findings: 2, consent_ok: true, qc_passed: false };
    assert!(!can_emit_clinical_report(&report));
}
