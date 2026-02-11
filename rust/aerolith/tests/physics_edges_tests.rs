use aerolith::orbit::{correction_delta, is_station_keeping_stable, OrbitState};
use aerolith::planner::{validate_plan, BurnPlan};

#[test]
fn correction_delta_precision() {
    let current = OrbitState { altitude_km: 500.0, inclination_deg: 50.0, drift_mps: 0.0 };
    let target = OrbitState { altitude_km: 500.26, inclination_deg: 50.14, drift_mps: 0.0 };
    let (da, di) = correction_delta(&current, &target);
    assert_eq!(da, 0.3);
    assert_eq!(di, 0.1);
}

#[test]
fn station_keeping_bounds() {
    let stable = OrbitState { altitude_km: 400.0, inclination_deg: 55.0, drift_mps: 4.0 };
    assert!(is_station_keeping_stable(&stable));

    let unstable = OrbitState { altitude_km: 400.0, inclination_deg: 55.0, drift_mps: 4.1 };
    assert!(!is_station_keeping_stable(&unstable));
}

#[test]
fn burn_plan_limits() {
    let good = BurnPlan { delta_v_mps: 120.0, burn_seconds: 2.0, fuel_margin_kg: 5.0 };
    assert!(validate_plan(&good));

    let bad = BurnPlan { delta_v_mps: 130.0, burn_seconds: 2.0, fuel_margin_kg: 5.0 };
    assert!(!validate_plan(&bad));
}
