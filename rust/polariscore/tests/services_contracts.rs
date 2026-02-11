use polariscore::statistics::rolling_sla;

#[test]
fn service_contract_baseline() {
    let availability = rolling_sla(&[90, 110, 130, 85], 120);
    assert!(availability >= 0.75);
}
