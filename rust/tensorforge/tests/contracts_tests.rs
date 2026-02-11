#[path = "../shared/contracts.rs"]
mod contracts;

use tensorforge::contracts::{
    contract_summary, dependency_count, find_orphan_services, health_endpoint,
    is_critical_path, port_collision_check, service_definitions, service_version_check,
};

#[test]
fn contracts_required_fields() {
    assert_eq!(contracts::CONTRACTS[0].0, "gateway");
    assert!(contracts::CONTRACTS[1].1 > 0);
}

#[test]
fn contracts_health_endpoint_format() {
    let ep = health_endpoint("gateway");
    assert_eq!(ep, "/api/gateway/health");
}

#[test]
fn contracts_dependency_depth() {
    let defs = service_definitions();
    // analytics depends on gateway and routing — and routing depends on gateway
    // transitive count for analytics should be >= 2
    let count = dependency_count(&defs, "analytics");
    assert!(count >= 2);
}

#[test]
fn contracts_critical_path() {
    let defs = service_definitions();
    // gateway is depended on by many services — it IS on the critical path
    assert!(is_critical_path(&defs, "gateway"));
    // security has no dependents — it is NOT on the critical path
    assert!(!is_critical_path(&defs, "security"));
}

#[test]
fn contracts_version_exact_match() {
    let defs = service_definitions();
    assert!(service_version_check(&defs, "gateway", "1.0.0"));
    assert!(!service_version_check(&defs, "gateway", "1.0"));
    assert!(!service_version_check(&defs, "gateway", "1"));
}

#[test]
fn contracts_orphan_detection() {
    let defs = service_definitions();
    let orphans = find_orphan_services(&defs);
    // gateway is depended on by everyone — it should NOT be an orphan
    assert!(!orphans.contains(&"gateway".to_string()));
}

#[test]
fn contracts_port_collision() {
    let defs = service_definitions();
    // default definitions have unique ports — no collision
    assert!(!port_collision_check(&defs));
}

#[test]
fn contracts_summary_format() {
    let defs = service_definitions();
    let summary = contract_summary(&defs);
    assert!(summary[0].contains(':'));
    assert!(summary[0].starts_with("gateway:"));
}
