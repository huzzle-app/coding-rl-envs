use aerolith::auth::authorize_command;
use aerolith::orbit::{correction_delta, is_station_keeping_stable, OrbitState};
use aerolith::planner::{validate_plan, BurnPlan};
use aerolith::safety::{classify_collision_risk, CollisionInput, SafetyAction};
use aerolith::sequencing::{is_strictly_ordered, Command};
use aerolith::telemetry::{health_score, TelemetrySample};

#[test]
fn orbit_delta_is_computed() {
    let current = OrbitState { altitude_km: 550.0, inclination_deg: 53.2, drift_mps: 1.2 };
    let target = OrbitState { altitude_km: 549.7, inclination_deg: 53.4, drift_mps: 0.0 };
    let (da, di) = correction_delta(&current, &target);
    assert_eq!(da, -0.3);
    assert_eq!(di, 0.2);
}

#[test]
fn stable_station_keeping_bounds() {
    let state = OrbitState { altitude_km: 700.0, inclination_deg: 97.6, drift_mps: 3.2 };
    assert!(is_station_keeping_stable(&state));
}

#[test]
fn collision_risk_classification() {
    let input = CollisionInput { nearest_object_distance_km: 0.4, relative_velocity_kmps: 5.5, confidence: 0.88 };
    assert_eq!(classify_collision_risk(&input), SafetyAction::EmergencyBurn);
}

#[test]
fn command_authorization() {
    assert!(!authorize_command("observer", "cluster", "fire_thruster"));
    assert!(authorize_command("flight_operator", "cluster", "fire_thruster"));
    assert!(authorize_command("observer", "cluster", "read_telemetry"));
}

#[test]
fn telemetry_health_score() {
    let sample = TelemetrySample { battery_pct: 82.0, thermal_c: 63.0, attitude_jitter: 0.8 };
    let score = health_score(&sample);
    assert!(score > 0.65);
}

#[test]
fn command_sequence_ordering() {
    let cmds = vec![
        Command { id: "c1".into(), epoch: 100, critical: false },
        Command { id: "c2".into(), epoch: 101, critical: true },
        Command { id: "c3".into(), epoch: 102, critical: true },
    ];
    assert!(is_strictly_ordered(&cmds));
}

#[test]
fn burn_plan_validation() {
    let plan = BurnPlan { delta_v_mps: 44.5, burn_seconds: 310.0, fuel_margin_kg: 8.0 };
    assert!(validate_plan(&plan));
}

#[test]
fn migration_files_include_core_tables() {
    let core = include_str!("../migrations/001_core.sql");
    assert!(core.contains("CREATE TABLE IF NOT EXISTS mission_commands"));
    assert!(core.contains("CREATE TABLE IF NOT EXISTS mission_events"));

    let safety = include_str!("../migrations/002_safety.sql");
    assert!(safety.contains("CREATE TABLE IF NOT EXISTS collision_decisions"));
}
