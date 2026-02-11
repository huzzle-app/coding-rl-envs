use crate::orbit;
use crate::safety;
use crate::power;
use crate::telemetry;
use crate::scheduling;
use crate::routing;
use crate::auth;

/// Conjunction assessment pipeline. Evaluates collision risk by
/// computing relative velocity and feeding it into the safety classifier.
pub fn conjunction_assessment_pipeline(
    altitude_km: f64,
    other_altitude_km: f64,
    miss_distance_km: f64,
    confidence: f64,
) -> (u32, &'static str) {
    let v1 = orbit::velocity_at_altitude(altitude_km);
    let v2 = orbit::velocity_at_altitude(other_altitude_km);
    let rel_v = orbit::relative_velocity(v1, v2);

    let risk = safety::classify_collision_risk(&safety::CollisionInput {
        nearest_object_distance_km: miss_distance_km,
        relative_velocity_kmps: rel_v,
        confidence,
    });

    let prob = safety::collision_probability(10.0, miss_distance_km);
    let threat = safety::threat_level(prob);

    let action = match risk {
        safety::SafetyAction::EmergencyBurn => "execute_burn",
        safety::SafetyAction::Alert => "raise_alert",
        safety::SafetyAction::Monitor => "continue_monitoring",
    };

    (threat, action)
}

/// Determine if a communication contact window is power-feasible
/// given solar generation, battery state, and comms load.
pub fn power_aware_contact_feasible(
    contact_start_s: f64,
    contact_duration_s: f64,
    solar_watts: f64,
    battery_wh: f64,
    battery_capacity_wh: f64,
    comms_power_watts: f64,
) -> bool {
    let contact_end = scheduling::contact_window_end(contact_start_s, contact_duration_s);
    let _duration_h = (contact_end - contact_start_s) / 3600.0;

    let soc = power::battery_soc(battery_wh, battery_capacity_wh);
    let budget = power::power_budget_watts(solar_watts, comms_power_watts);

    if budget < 0.0 && soc < 0.2 {
        return false;
    }
    true
}

/// Map telemetry health score to operational mode.
pub fn telemetry_mode_decision(
    battery_pct: f64,
    thermal_c: f64,
    jitter: f64,
) -> &'static str {
    let sample = telemetry::TelemetrySample {
        battery_pct,
        thermal_c,
        attitude_jitter: jitter,
    };
    let score = telemetry::health_score(&sample);

    if score > 0.8 {
        "nominal"
    } else if score > 0.5 {
        "degraded"
    } else {
        "safe_mode"
    }
}

/// Plan a downlink session: select the optimal ground station,
/// compute link budget, and verify operator authorization.
pub fn plan_downlink(
    stations: &[(String, f64)],
    operator_role: &str,
    tx_power_db: f64,
    antenna_gain_db: f64,
) -> Option<(String, f64, bool)> {
    let best = routing::best_ground_station(stations)?;

    let _station_latency = stations
        .iter()
        .find(|(n, _)| *n == best)
        .map(|(_, l)| *l)?;

    let budget = routing::link_budget_db(tx_power_db, antenna_gain_db, 3.0);
    let authorized = auth::authorize_command(operator_role, "ground", "downlink_data");

    Some((best, budget, authorized))
}

/// Orbit maintenance assessment: evaluate station-keeping stability,
/// compute required corrections, and validate the resulting burn plan.
pub fn orbit_maintenance_check(
    current_alt: f64,
    current_inc: f64,
    current_drift: f64,
    target_alt: f64,
    target_inc: f64,
) -> (bool, f64, bool) {
    let current = orbit::OrbitState {
        altitude_km: current_alt,
        inclination_deg: current_inc,
        drift_mps: current_drift,
    };
    let target = orbit::OrbitState {
        altitude_km: target_alt,
        inclination_deg: target_inc,
        drift_mps: 0.0,
    };

    let stable = orbit::is_station_keeping_stable(&current);
    let (da, di) = orbit::correction_delta(&current, &target);

    let delta_v = (da.abs() + di.abs()) * 50.0;

    let plan = crate::planner::BurnPlan {
        delta_v_mps: delta_v,
        burn_seconds: delta_v * 3.0,
        fuel_margin_kg: 6.0,
    };
    let plan_valid = crate::planner::validate_plan(&plan);

    (stable, delta_v, plan_valid)
}

/// Composite pass execution decision combining visibility, power, and auth.
pub fn should_execute_pass(
    elevation_deg: f64,
    min_elevation_deg: f64,
    battery_soc: f64,
    operator_role: &str,
) -> (bool, &'static str) {
    let visible = routing::ground_station_visible(elevation_deg, min_elevation_deg);
    let los = routing::is_line_of_sight(elevation_deg);
    let mode = power::power_mode(battery_soc);
    let auth = auth::authorize_command(operator_role, "pass", "read_telemetry");

    if !visible || !los {
        return (false, "no_visibility");
    }
    if mode == "critical" {
        return (false, "low_power");
    }
    if !auth {
        return (false, "unauthorized");
    }
    (true, "execute")
}

/// Full orbit propagation and decay prediction pipeline.
/// Chains mean motion, J2 perturbation, and atmospheric drag
/// to predict orbital state evolution.
pub fn predict_orbit_evolution(
    altitude_km: f64,
    inclination_deg: f64,
    days_ahead: f64,
) -> (f64, f64, f64) {
    let sma = orbit::semi_major_axis_km(altitude_km);
    let raan_rate = orbit::j2_raan_drift_deg_per_day(sma, inclination_deg);
    let raan_shift = raan_rate * days_ahead;

    let n = orbit::mean_motion_rad_s(sma);
    let period_s = std::f64::consts::TAU / n;
    let period_min = period_s / 60.0;

    let decay = orbit::altitude_decay_rate_km_per_day(2.2, 0.001);
    let alt_change = decay * days_ahead;
    let new_altitude = altitude_km + alt_change;

    (new_altitude, raan_shift, period_min)
}

/// End-to-end safety assessment for a conjunction event, combining
/// miss distance computation, threat prioritization, and maneuver feasibility.
pub fn full_conjunction_response(
    own_pos: (f64, f64, f64),
    threat_pos: (f64, f64, f64),
    threat_vel: (f64, f64, f64),
    fuel_kg: f64,
    max_fuel_kg: f64,
) -> (&'static str, f64) {
    let miss = safety::miss_distance_3d(
        own_pos.0, own_pos.1, own_pos.2,
        threat_pos.0, threat_pos.1, threat_pos.2,
    );

    let tca = safety::time_to_closest_approach(
        threat_pos.0 - own_pos.0,
        threat_pos.1 - own_pos.1,
        threat_pos.2 - own_pos.2,
        threat_vel.0, threat_vel.1, threat_vel.2,
    );

    let prob = safety::collision_probability(10.0, miss);
    let threat = safety::threat_level(prob);

    let response = if threat >= 3 {
        "maneuver"
    } else if threat >= 1 {
        "monitor_closely"
    } else {
        "nominal"
    };

    (response, tca)
}
