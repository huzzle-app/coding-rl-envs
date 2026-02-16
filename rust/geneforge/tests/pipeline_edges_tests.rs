use geneforge::pipeline::{retry_budget_for_stage, valid_stage_order, Stage};

#[test]
fn stage_order_rejects_wrong_sequence() {
    let stages = vec![Stage::Intake, Stage::Align, Stage::Qc, Stage::CallVariants, Stage::Annotate, Stage::Report];
    assert!(!valid_stage_order(&stages));
}

#[test]
fn retry_budget_profiles() {
    assert_eq!(retry_budget_for_stage(&Stage::Align), 5);
    assert_eq!(retry_budget_for_stage(&Stage::CallVariants), 3);
    assert_eq!(retry_budget_for_stage(&Stage::Intake), 2);
}

#[test]
fn report_stage_budget() {
    assert_eq!(retry_budget_for_stage(&Stage::Report), 2);
}
