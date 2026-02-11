use aerolith::auth::authorize_command;
use aerolith::orbit::{correction_delta, OrbitState};
use aerolith::planner::{validate_plan, BurnPlan};
use aerolith::safety::{classify_collision_risk, CollisionInput, SafetyAction};

#[test]
fn mission_flow_emergency_path() {
    let current = OrbitState { altitude_km: 560.0, inclination_deg: 53.0, drift_mps: 1.8 };
    let target = OrbitState { altitude_km: 559.4, inclination_deg: 53.4, drift_mps: 0.0 };
    let (da, di) = correction_delta(&current, &target);
    let plan = BurnPlan { delta_v_mps: (da.abs() + di.abs()) * 60.0, burn_seconds: 280.0, fuel_margin_kg: 9.0 };
    let risk = classify_collision_risk(&CollisionInput { nearest_object_distance_km: 0.35, relative_velocity_kmps: 5.8, confidence: 0.9 });
    assert_eq!(risk, SafetyAction::EmergencyBurn);
    assert!(validate_plan(&plan));
    assert!(authorize_command("flight_operator", "cluster", "fire_thruster"));
}

#[test]
fn mission_flow_monitor_path() {
    let risk = classify_collision_risk(&CollisionInput { nearest_object_distance_km: 2.0, relative_velocity_kmps: 1.2, confidence: 0.8 });
    assert_eq!(risk, SafetyAction::Monitor);
}

#[test]
fn mission_flow_authorization_denied() {
    assert!(!authorize_command("observer", "cluster", "fire_thruster"));
}
