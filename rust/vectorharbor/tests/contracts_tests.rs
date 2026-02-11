#[path = "../shared/contracts.rs"]
mod contracts;

#[test]
fn contracts_required_fields() {
    assert_eq!(contracts::CONTRACTS[0].0, "gateway");
    assert!(contracts::CONTRACTS[1].1 > 0);
}
