//! Anti-tampering tests for GeneForge
//! These tests verify source code structural integrity to prevent reward hacking.
//! They ensure functions exist, maintain correct signatures, and aren't hardcoded.

// ============================================================================
// Source file existence and structure checks
// ============================================================================

#[test]
fn source_files_exist() {
    let src = include_str!("../src/lib.rs");
    assert!(src.contains("pub mod pipeline;"), "lib.rs must declare pipeline module");
    assert!(src.contains("pub mod qc;"), "lib.rs must declare qc module");
    assert!(src.contains("pub mod consent;"), "lib.rs must declare consent module");
    assert!(src.contains("pub mod statistics;"), "lib.rs must declare statistics module");
    assert!(src.contains("pub mod resilience;"), "lib.rs must declare resilience module");
    assert!(src.contains("pub mod reporting;"), "lib.rs must declare reporting module");
    assert!(src.contains("pub mod aggregator;"), "lib.rs must declare aggregator module");
}

// ============================================================================
// Pipeline module integrity
// ============================================================================

#[test]
fn pipeline_source_integrity() {
    let src = include_str!("../src/pipeline.rs");

    // Function signatures must exist
    assert!(src.contains("pub fn valid_stage_order"), "valid_stage_order must exist");
    assert!(src.contains("pub fn retry_budget_for_stage"), "retry_budget_for_stage must exist");
    assert!(src.contains("pub fn is_critical_stage"), "is_critical_stage must exist");
    assert!(src.contains("pub fn stage_index"), "stage_index must exist");
    assert!(src.contains("pub fn can_transition"), "can_transition must exist");
    assert!(src.contains("pub fn estimate_duration_minutes"), "estimate_duration_minutes must exist");
    assert!(src.contains("pub fn total_pipeline_duration"), "total_pipeline_duration must exist");
    assert!(src.contains("pub fn parallel_factor"), "parallel_factor must exist");

    // Stage enum must have all variants
    assert!(src.contains("Intake"), "Stage must have Intake");
    assert!(src.contains("Qc"), "Stage must have Qc");
    assert!(src.contains("Align"), "Stage must have Align");
    assert!(src.contains("CallVariants"), "Stage must have CallVariants");
    assert!(src.contains("Annotate"), "Stage must have Annotate");
    assert!(src.contains("Report"), "Stage must have Report");

    // Must use match expressions (not hardcoded returns)
    assert!(src.contains("match stage"), "stage_index must use match on stage");
    assert!(src.contains("Stage::Align =>"), "retry_budget must match on Align");

    // valid_stage_order must compare stages against STAGE_ORDER (not just length)
    // After fix, it should iterate and compare each element
    let valid_fn_start = src.find("fn valid_stage_order").unwrap();
    let valid_fn_body = &src[valid_fn_start..valid_fn_start + 300];
    assert!(
        valid_fn_body.contains("STAGE_ORDER") || valid_fn_body.contains("stages["),
        "valid_stage_order must check stage elements, not just length"
    );

    // PipelineRun must exist and have advance method
    assert!(src.contains("pub struct PipelineRun"), "PipelineRun struct must exist");
    assert!(src.contains("pub fn advance"), "PipelineRun::advance must exist");
    assert!(src.contains("pub fn can_retry"), "PipelineRun::can_retry must exist");
}

#[test]
fn pipeline_valid_stage_order_not_trivial() {
    // Verify valid_stage_order actually validates order, not just length
    use geneforge::pipeline::{valid_stage_order, Stage};

    let correct = vec![Stage::Intake, Stage::Qc, Stage::Align, Stage::CallVariants, Stage::Annotate, Stage::Report];
    assert!(valid_stage_order(&correct), "Correct order must pass");

    let wrong_order = vec![Stage::Report, Stage::Qc, Stage::Align, Stage::CallVariants, Stage::Annotate, Stage::Intake];
    assert!(!valid_stage_order(&wrong_order), "Wrong order with correct length must fail");

    let swapped = vec![Stage::Intake, Stage::Align, Stage::Qc, Stage::CallVariants, Stage::Annotate, Stage::Report];
    assert!(!valid_stage_order(&swapped), "Swapped stages must fail");
}

// ============================================================================
// QC module integrity
// ============================================================================

#[test]
fn qc_source_integrity() {
    let src = include_str!("../src/qc.rs");

    assert!(src.contains("pub fn qc_pass"), "qc_pass must exist");
    assert!(src.contains("pub fn contamination_acceptable"), "contamination_acceptable must exist");
    assert!(src.contains("pub fn coverage_tier"), "coverage_tier must exist");
    assert!(src.contains("pub fn qc_score"), "qc_score must exist");
    assert!(src.contains("pub fn batch_qc_pass_rate"), "batch_qc_pass_rate must exist");

    // QCMetrics must have all fields
    assert!(src.contains("coverage_depth"), "QCMetrics must have coverage_depth");
    assert!(src.contains("contamination"), "QCMetrics must have contamination");
    assert!(src.contains("duplication_rate"), "QCMetrics must have duplication_rate");

    // qc_pass must check all three metrics (not hardcoded)
    let qc_fn_start = src.find("fn qc_pass").unwrap();
    let qc_fn_body = &src[qc_fn_start..qc_fn_start + 200];
    assert!(qc_fn_body.contains("coverage_depth"), "qc_pass must check coverage_depth");
    assert!(qc_fn_body.contains("contamination"), "qc_pass must check contamination");
    assert!(qc_fn_body.contains("duplication_rate"), "qc_pass must check duplication_rate");
}

#[test]
fn qc_boundary_behavior() {
    use geneforge::qc::{qc_pass, QCMetrics};

    // Boundary test: coverage_depth exactly at threshold
    let at_boundary = QCMetrics { coverage_depth: 30.0, contamination: 0.02, duplication_rate: 0.2 };
    assert!(qc_pass(&at_boundary), "QC at exact boundary should pass (>=)");

    // Just below boundary
    let below = QCMetrics { coverage_depth: 29.99, contamination: 0.02, duplication_rate: 0.2 };
    assert!(!qc_pass(&below), "QC below boundary should fail");
}

// ============================================================================
// Statistics module integrity
// ============================================================================

#[test]
fn statistics_source_integrity() {
    let src = include_str!("../src/statistics.rs");

    assert!(src.contains("pub fn mean"), "mean must exist");
    assert!(src.contains("pub fn variance"), "variance must exist");
    assert!(src.contains("pub fn median"), "median must exist");
    assert!(src.contains("pub fn f1_score"), "f1_score must exist");
    assert!(src.contains("pub fn percentile"), "percentile must exist");
    assert!(src.contains("pub fn confidence_interval_95"), "confidence_interval_95 must exist");
    assert!(src.contains("pub fn bonferroni_threshold"), "bonferroni_threshold must exist");
    assert!(src.contains("pub fn z_score"), "z_score must exist");
    assert!(src.contains("pub fn cohens_d"), "cohens_d must exist");

    // Mean must use iter/sum pattern (not hardcoded)
    let mean_fn_start = src.find("fn mean").unwrap();
    let mean_fn_body = &src[mean_fn_start..mean_fn_start + 200];
    assert!(mean_fn_body.contains("sum") || mean_fn_body.contains("iter"), "mean must compute from values");

    // F1 score must use both precision and recall
    let f1_fn_start = src.find("fn f1_score").unwrap();
    let f1_fn_body = &src[f1_fn_start..f1_fn_start + 200];
    assert!(f1_fn_body.contains("precision") && f1_fn_body.contains("recall"), "f1_score must use both inputs");
}

#[test]
fn statistics_mean_not_hardcoded() {
    use geneforge::statistics::mean;

    // These values make it impossible to hardcode — the function must actually compute
    let m1 = mean(&[1.0, 2.0, 3.0]).unwrap();
    let m2 = mean(&[10.0, 20.0, 30.0]).unwrap();
    let m3 = mean(&[7.0, 14.0, 21.0]).unwrap();

    // If mean is correctly implemented, m2 = 10 * m1 and m3 = 7 * m1
    assert!((m2 / m1 - 10.0).abs() < 0.01, "Mean must scale linearly");
    assert!((m3 / m1 - 7.0).abs() < 0.01, "Mean must scale linearly");
}

#[test]
fn statistics_f1_symmetry() {
    use geneforge::statistics::f1_score;

    // F1 is symmetric: f1(p, r) == f1(r, p)
    let f1a = f1_score(0.8, 0.6).unwrap();
    let f1b = f1_score(0.6, 0.8).unwrap();
    assert!((f1a - f1b).abs() < 0.001, "F1 score must be symmetric");

    // F1 for equal p and r: f1(x, x) = x (only with correct 2*p*r/(p+r) formula)
    let f1c = f1_score(0.7, 0.7).unwrap();
    assert!((f1c - 0.7).abs() < 0.01, "F1(x,x) should equal x");
}

// ============================================================================
// Consent module integrity
// ============================================================================

#[test]
fn consent_source_integrity() {
    let src = include_str!("../src/consent.rs");

    assert!(src.contains("pub fn can_access_dataset"), "can_access_dataset must exist");
    assert!(src.contains("pub fn consent_level"), "consent_level must exist");
    assert!(src.contains("pub fn merge_consents"), "merge_consents must exist");
    assert!(src.contains("pub fn validate_consent"), "validate_consent must exist");

    // ConsentRecord must have all fields
    assert!(src.contains("allows_research"), "ConsentRecord must have allows_research");
    assert!(src.contains("allows_clinical_reporting"), "ConsentRecord must have allows_clinical_reporting");
    assert!(src.contains("revoked"), "ConsentRecord must have revoked");
}

#[test]
fn consent_revocation_always_blocks() {
    use geneforge::consent::{can_access_dataset, ConsentRecord};

    // Revoked consent should NEVER allow access
    let revoked = ConsentRecord {
        subject_id: "test".into(),
        allows_research: true,
        allows_clinical_reporting: true,
        revoked: true,
    };
    assert!(!can_access_dataset(&revoked, "research_cohort"), "Revoked must block research");
    assert!(!can_access_dataset(&revoked, "clinical_report"), "Revoked must block clinical");
}

// ============================================================================
// Resilience module integrity
// ============================================================================

#[test]
fn resilience_source_integrity() {
    let src = include_str!("../src/resilience.rs");

    assert!(src.contains("pub fn should_shed_load"), "should_shed_load must exist");
    assert!(src.contains("pub fn exponential_backoff_ms"), "exponential_backoff_ms must exist");
    assert!(src.contains("pub fn remaining_retries"), "remaining_retries must exist");
    assert!(src.contains("pub fn should_fail_fast"), "should_fail_fast must exist");
    assert!(src.contains("pub struct CircuitBreaker"), "CircuitBreaker must exist");
    assert!(src.contains("pub fn replay_sequence"), "replay_sequence must exist");

    // exponential_backoff must use power/multiplication (not hardcoded)
    let backoff_fn_start = src.find("fn exponential_backoff_ms").unwrap();
    let backoff_fn_body = &src[backoff_fn_start..backoff_fn_start + 200];
    assert!(
        backoff_fn_body.contains("powi") || backoff_fn_body.contains("pow") || backoff_fn_body.contains("*"),
        "exponential_backoff must use exponentiation"
    );
}

#[test]
fn resilience_backoff_is_exponential() {
    use geneforge::resilience::exponential_backoff_ms;

    // Verify exponential growth pattern: each step should be 2x previous
    let b0 = exponential_backoff_ms(0, 100);
    let b1 = exponential_backoff_ms(1, 100);
    let b2 = exponential_backoff_ms(2, 100);

    assert_eq!(b0, 100, "backoff(0) should equal base");
    assert_eq!(b1, b0 * 2, "backoff(1) should be 2x base");
    assert_eq!(b2, b0 * 4, "backoff(2) should be 4x base");
}

// ============================================================================
// Reporting module integrity
// ============================================================================

#[test]
fn reporting_source_integrity() {
    let src = include_str!("../src/reporting.rs");

    assert!(src.contains("pub fn can_emit_clinical_report"), "can_emit_clinical_report must exist");
    assert!(src.contains("pub fn report_priority"), "report_priority must exist");
    assert!(src.contains("pub fn pending_reports_count"), "pending_reports_count must exist");
    assert!(src.contains("pub fn report_age_hours"), "report_age_hours must exist");
    assert!(src.contains("pub struct ClinicalReport"), "ClinicalReport must exist");

    // report_priority must use is_urgent parameter
    let priority_fn_start = src.find("fn report_priority").unwrap();
    let priority_fn_body = &src[priority_fn_start..priority_fn_start + 300];
    assert!(priority_fn_body.contains("is_urgent") || priority_fn_body.contains("urgent"),
        "report_priority must use urgent parameter");
}

#[test]
fn reporting_priority_urgent_doubles() {
    use geneforge::reporting::report_priority;

    // Urgent should double the base priority, not just add 1
    let base = report_priority(3, false);  // base = 1
    let urgent = report_priority(3, true);
    assert_eq!(urgent, base * 2, "Urgent priority should be 2x base");

    let base2 = report_priority(8, false);  // base = 2
    let urgent2 = report_priority(8, true);
    assert_eq!(urgent2, base2 * 2, "Urgent priority should be 2x base");
}

#[test]
fn reporting_age_hours_correct_unit() {
    use geneforge::reporting::report_age_hours;

    // 3600 seconds = 1 hour
    let age = report_age_hours(0, 3600);
    assert!((age - 1.0).abs() < 0.01, "3600 seconds should be 1 hour");

    // 7200 seconds = 2 hours
    let age2 = report_age_hours(0, 7200);
    assert!((age2 - 2.0).abs() < 0.01, "7200 seconds should be 2 hours");
}

// ============================================================================
// Aggregator module integrity
// ============================================================================

#[test]
fn aggregator_source_integrity() {
    let src = include_str!("../src/aggregator.rs");

    assert!(src.contains("pub fn pathogenic_ratio"), "pathogenic_ratio must exist");
    assert!(src.contains("pub fn rank_cohorts_by_pathogenic"), "rank_cohorts_by_pathogenic must exist");
    assert!(src.contains("pub fn merge_cohorts"), "merge_cohorts must exist");
    assert!(src.contains("pub struct CohortPoint"), "CohortPoint must exist");
    assert!(src.contains("pub struct CohortSummary"), "CohortSummary must exist");
}

#[test]
fn aggregator_pathogenic_ratio_correct_division() {
    use geneforge::aggregator::{pathogenic_ratio, CohortPoint};

    // Simple case: 10/100 = 0.1 exactly
    let points = vec![CohortPoint { cohort: "a".into(), variant_count: 100, flagged_pathogenic: 10 }];
    let ratio = pathogenic_ratio(&points).unwrap();
    assert!((ratio - 0.1).abs() < 0.001, "10/100 should be exactly 0.1, got {}", ratio);

    // 50/100 = 0.5 exactly
    let points2 = vec![CohortPoint { cohort: "b".into(), variant_count: 100, flagged_pathogenic: 50 }];
    let ratio2 = pathogenic_ratio(&points2).unwrap();
    assert!((ratio2 - 0.5).abs() < 0.001, "50/100 should be exactly 0.5, got {}", ratio2);
}

#[test]
fn aggregator_ranking_is_descending() {
    use geneforge::aggregator::{rank_cohorts_by_pathogenic, CohortSummary};

    let cohorts = vec![
        CohortSummary { cohort_id: "low".into(), total_variants: 100, sample_count: 10, pathogenic_variants: 5, mean_coverage: 30.0 },
        CohortSummary { cohort_id: "high".into(), total_variants: 100, sample_count: 10, pathogenic_variants: 50, mean_coverage: 30.0 },
        CohortSummary { cohort_id: "mid".into(), total_variants: 100, sample_count: 10, pathogenic_variants: 20, mean_coverage: 30.0 },
    ];

    let ranked = rank_cohorts_by_pathogenic(&cohorts);
    assert_eq!(ranked[0].cohort_id, "high", "Highest pathogenic should be first (descending)");
    assert_eq!(ranked[1].cohort_id, "mid", "Mid should be second");
    assert_eq!(ranked[2].cohort_id, "low", "Lowest should be last");
}

// ============================================================================
// Cross-module integration tests (prevent isolated hardcoding)
// ============================================================================

#[test]
fn cross_module_qc_and_report_integration() {
    use geneforge::qc::{qc_pass, QCMetrics};
    use geneforge::reporting::{can_emit_clinical_report, ReportInput};

    // QC pass should enable report emission
    let qc = QCMetrics { coverage_depth: 40.0, contamination: 0.01, duplication_rate: 0.1 };
    let qc_result = qc_pass(&qc);
    let report = ReportInput { sample_id: "s1".into(), findings: 5, consent_ok: true, qc_passed: qc_result };
    assert!(can_emit_clinical_report(&report), "Passing QC should allow report emission");

    // QC fail should block report emission
    let bad_qc = QCMetrics { coverage_depth: 20.0, contamination: 0.05, duplication_rate: 0.3 };
    let qc_result2 = qc_pass(&bad_qc);
    let report2 = ReportInput { sample_id: "s2".into(), findings: 5, consent_ok: true, qc_passed: qc_result2 };
    assert!(!can_emit_clinical_report(&report2), "Failing QC should block report emission");
}

#[test]
fn cross_module_consent_and_report_integration() {
    use geneforge::consent::{can_access_dataset, ConsentRecord};
    use geneforge::reporting::{can_emit_clinical_report, ReportInput};

    let consent = ConsentRecord {
        subject_id: "s1".into(),
        allows_research: true,
        allows_clinical_reporting: true,
        revoked: false,
    };
    let consent_ok = can_access_dataset(&consent, "clinical_report");
    let report = ReportInput { sample_id: "s1".into(), findings: 3, consent_ok, qc_passed: true };
    assert!(can_emit_clinical_report(&report), "Valid consent should allow report");

    let revoked = ConsentRecord {
        subject_id: "s2".into(),
        allows_research: true,
        allows_clinical_reporting: true,
        revoked: true,
    };
    let consent_revoked = can_access_dataset(&revoked, "clinical_report");
    let report2 = ReportInput { sample_id: "s2".into(), findings: 3, consent_ok: consent_revoked, qc_passed: true };
    assert!(!can_emit_clinical_report(&report2), "Revoked consent should block report");
}

// ============================================================================
// Test file integrity (prevent test deletion/modification)
// ============================================================================

#[test]
fn cargo_toml_test_targets_intact() {
    let cargo = include_str!("../Cargo.toml");

    // Must have all 7 explicit test targets
    assert!(cargo.contains("genomics_tests"), "Cargo.toml must list genomics_tests");
    assert!(cargo.contains("pipeline_edges_tests"), "Cargo.toml must list pipeline_edges_tests");
    assert!(cargo.contains("quality_edges_tests"), "Cargo.toml must list quality_edges_tests");
    assert!(cargo.contains("fault_injection_tests"), "Cargo.toml must list fault_injection_tests");
    assert!(cargo.contains("clinical_flow_tests"), "Cargo.toml must list clinical_flow_tests");
    assert!(cargo.contains("chaos_replay_tests"), "Cargo.toml must list chaos_replay_tests");
    assert!(cargo.contains("services_contracts"), "Cargo.toml must list services_contracts");

    let test_count = cargo.matches("[[test]]").count();
    assert!(test_count >= 7, "Cargo.toml must have at least 7 [[test]] entries, found {}", test_count);
}

#[test]
fn infrastructure_files_intact() {
    let setup = include_str!("../environment/setup.rs");
    // validate_action must block editing test files AND infrastructure files
    assert!(setup.contains("editing test files is not allowed"), "setup.rs must block test file edits");
    assert!(setup.contains("editing infrastructure files is not allowed"), "setup.rs must block infrastructure edits");
    assert!(setup.contains("environment/"), "setup.rs must check for environment/ path prefix");
    assert!(setup.contains("Cargo.toml"), "setup.rs must check for Cargo.toml edits");
}

#[test]
fn test_files_not_truncated() {
    let hyper = include_str!("hyper_matrix_test.rs");
    // Verify the test file has substantial content
    assert!(hyper.len() > 5000, "hyper_matrix_test.rs must not be truncated");
    assert!(hyper.contains("hyper_matrix_0001"), "First test must exist");
    assert!(hyper.contains("hyper_matrix_0050"), "Test 50 must exist");

    let generated = include_str!("stress/generated_tests.rs");
    assert!(generated.len() > 50000, "generated_tests.rs must not be truncated");
    assert!(generated.contains("hyper_matrix_0100"), "Test 100 must exist");
    assert!(generated.contains("hyper_matrix_1100"), "Test 1100 must exist");
}

#[test]
fn minimum_test_function_count() {
    let hyper = include_str!("hyper_matrix_test.rs");
    let generated = include_str!("stress/generated_tests.rs");
    let all = format!("{}{}", hyper, generated);

    let test_count = all.matches("#[test]").count();
    assert!(test_count >= 1100, "Must have at least 1100 test functions, found {}", test_count);
}
