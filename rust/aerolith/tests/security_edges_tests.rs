use aerolith::auth::authorize_command;

#[test]
fn auth_observer_limits() {
    assert!(authorize_command("observer", "cluster", "read_telemetry"));
    assert!(!authorize_command("observer", "cluster", "fire_thruster"));
}

#[test]
fn auth_flight_operator_scope() {
    assert!(authorize_command("flight_operator", "cluster", "fire_thruster"));
}

#[test]
fn auth_admin_allows() {
    assert!(authorize_command("admin", "cluster", "fire_thruster"));
}
