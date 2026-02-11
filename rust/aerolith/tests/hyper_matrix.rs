use aerolith::config::{
    default_orbit_altitude, default_pool_size, validate_config, validate_endpoint,
    normalize_env_name, constellation_size, max_burn_duration, parse_feature_flags,
    is_operational, config_priority, build_connection_string, heartbeat_interval_ms,
};
use aerolith::orbit::{
    OrbitState, correction_delta, is_station_keeping_stable,
    semi_major_axis_km, velocity_at_altitude, relative_velocity,
    altitude_decay_rate_km_per_day, orbit_energy, apoapsis_from_elements,
    ground_track_shift_deg, time_to_node_s,
    j2_raan_drift_deg_per_day, mean_motion_rad_s, periapsis_velocity,
    ground_footprint_radius_km,
    nodal_precession_period_days, argument_of_latitude,
    atmospheric_density_kg_m3,
};
use aerolith::safety::{
    classify_collision_risk, CollisionInput, SafetyAction,
    collision_probability, in_keep_out_zone, debris_density, maneuver_risk,
    safe_separation_m, is_reentry, fragmentation_risk, threat_level,
    max_debris_count, exclusion_zone_radius_m, is_safe_for_eva, risk_matrix_score,
    miss_distance_3d, cumulative_collision_prob, prioritize_threats,
    mahalanobis_distance,
};
use aerolith::sequencing::{
    Command, is_strictly_ordered, command_in_window, is_critical_sequence,
    command_rate, execution_gap, command_timeout_ms, validate_epoch,
};
use aerolith::routing::{
    link_margin_db, ground_station_visible, best_ground_station,
    slant_range_km, doppler_shift_hz, link_budget_db, normalize_azimuth,
    is_line_of_sight, route_failover, eirp_dbw, select_best_antenna,
};
use aerolith::scheduling::{
    contact_window_end, next_pass_delta_s, mission_overlap,
    schedule_priority, optimal_downlink_elevation, contact_gap_s,
    recurring_passes,
};
use aerolith::power::{
    solar_panel_output_watts, battery_soc, power_budget_watts,
    depth_of_discharge, battery_health, solar_flux_w_per_m2,
    power_mode, total_power_watts, power_margin_pct,
    thermal_equilibrium_k, end_of_life_power,
};
use aerolith::telemetry::{
    TelemetrySample, health_score, is_anomaly, latency_bucket, error_rate,
    throughput, uptime_percentage, format_metric, should_alert,
    aggregate_mean, is_within_threshold, jitter_score, staleness_s,
    telemetry_summary,
};
use aerolith::resilience::{
    retry_backoff_ms, circuit_open, accept_version, dedupe_ids,
    checkpoint_interval_s, degradation_level, bulkhead_remaining,
    cascade_failure_check, recovery_rate, retry_delay_ms, should_trip,
    half_open_allowed, in_failure_window, state_duration_s,
    fallback_value, circuit_should_reset, circuit_breaker_next_state,
    health_check_quorum, adaptive_timeout_ms, load_shedding,
};
use aerolith::auth::{
    authorize_command, validate_token_format, password_strength,
    mask_sensitive, rate_limit_key, session_expired, sanitize_header,
    permission_check, ip_in_allowlist, hash_credential, token_expiry,
    scope_includes, role_hierarchy, validate_claims, mfa_check,
    rotate_key_index, evaluate_rbac,
};
use aerolith::events::{
    SatEvent, sort_events_by_time, dedup_events, filter_time_window,
    detect_gaps, count_by_kind, event_rate as ev_rate,
};
use aerolith::planner::{validate_plan, BurnPlan};

const TOTAL_CASES: usize = 1139;

fn run_case(idx: usize) -> bool {
    // ── config checks ──
    if default_orbit_altitude() != 550.0 { return false; }
    if default_pool_size() != 32 { return false; }
    if validate_config(0, "test") { return false; }
    if !validate_config(1, "test") { return false; }
    if !validate_endpoint("http://localhost") { return false; }
    if validate_endpoint("data:http://evil") { return false; }
    if normalize_env_name("Prod") != "prod" { return false; }
    if constellation_size() != 24 { return false; }
    if max_burn_duration() != 300.0 { return false; }
    if heartbeat_interval_ms() != 5000 { return false; }

    let flags = parse_feature_flags("a,b,c");
    if flags.len() != 3 { return false; }

    if !is_operational("operational") { return false; }
    if !is_operational("nominal") { return false; }

    if config_priority("production") <= config_priority("development") { return false; }

    let conn = build_connection_string("localhost", 5432, "aerolith");
    if !conn.contains("localhost:5432") { return false; }

    // ── existing orbit checks (must still pass) ──
    let alt_a = (idx % 8) as f64 * 50.0 + 200.0;
    let alt_b = alt_a + 10.0;
    let current = OrbitState { altitude_km: alt_a, inclination_deg: 53.0, drift_mps: 1.0 };
    let target = OrbitState { altitude_km: alt_b, inclination_deg: 53.2, drift_mps: 0.0 };
    let (da, _di) = correction_delta(&current, &target);
    if (da - 10.0).abs() > 0.1 { return false; }

    let state = OrbitState { altitude_km: 400.0, inclination_deg: 55.0, drift_mps: 3.0 };
    if !is_station_keeping_stable(&state) { return false; }

    // ── new orbit checks ──
    let sma = semi_major_axis_km(400.0);
    if (sma - 6771.0).abs() > 1.0 { return false; }

    let v = velocity_at_altitude(400.0);
    if v < 7000.0 || v > 8000.0 { return false; }

    let rel = relative_velocity(7700.0, 7600.0);
    if (rel - 100.0).abs() > 1.0 { return false; }

    let decay = altitude_decay_rate_km_per_day(2.2, 0.001);
    if decay >= 0.0 { return false; }

    let energy = orbit_energy(7000.0);
    if energy >= 0.0 { return false; }

    let ap = apoapsis_from_elements(7000.0, 0.1);
    if (ap - 7700.0).abs() > 1.0 { return false; }

    let shift = ground_track_shift_deg(1.5);
    if (shift - 22.56).abs() > 1.0 { return false; }

    let ttn = time_to_node_s(0.25, 5400.0);
    if (ttn - 1350.0).abs() > 1.0 { return false; }

    // ── safety checks ──
    let risk = classify_collision_risk(&CollisionInput {
        nearest_object_distance_km: 0.3,
        relative_velocity_kmps: 5.0,
        confidence: 0.9,
    });
    if risk != SafetyAction::EmergencyBurn { return false; }

    if !in_keep_out_zone(1.0, 1.0) { return false; }
    if in_keep_out_zone(1.1, 1.0) { return false; }

    if !is_reentry(119.0) { return false; }
    if is_reentry(120.0) { return false; }

    let tl = threat_level(0.75);
    if tl != 4 { return false; }
    let tl2 = threat_level(0.50);
    if tl2 != 3 { return false; }

    let sizes = vec![0.5, 1.0, 2.0, 5.0, 10.0];
    if max_debris_count(&sizes, 2.0) != 3 { return false; }

    let rm = risk_matrix_score(3, 2);
    if rm != 32 { return false; }

    let sep = safe_separation_m(1.5);
    if (sep - 1500.0).abs() > 1.0 { return false; }

    if fragmentation_risk(12.0, 150.0) != "high" { return false; }
    if fragmentation_risk(5.0, 150.0) != "low" { return false; }

    if !is_safe_for_eva(0, 0.9) { return false; }
    if is_safe_for_eva(100, 0.9) { return false; }

    let ez = exclusion_zone_radius_m(2.0, 3.0);
    if (ez - 3.0).abs() > 0.1 { return false; }

    // ── sequencing checks ──
    let cmds = vec![
        Command { id: "c1".into(), epoch: 100, critical: true },
        Command { id: "c2".into(), epoch: 101, critical: true },
    ];
    if !is_strictly_ordered(&cmds) { return false; }

    if !command_in_window(100, 100, 200) { return false; }
    if !command_in_window(200, 100, 200) { return false; }
    if command_in_window(201, 100, 200) { return false; }

    let gap = execution_gap(200, 100);
    if gap != 100 { return false; }

    if !validate_epoch(100, 100) { return false; }
    if validate_epoch(101, 100) { return false; }

    let timeout = command_timeout_ms(100, 3);
    if timeout != 300 { return false; }

    // ── routing checks ──
    let margin = link_margin_db(-70.0, -100.0);
    if (margin - 30.0).abs() > 0.01 { return false; }

    if !ground_station_visible(10.0, 10.0) { return false; }
    if ground_station_visible(5.0, 10.0) { return false; }

    let stations = vec![
        ("alpha".into(), 50.0),
        ("beta".into(), 10.0),
        ("gamma".into(), 30.0),
    ];
    if best_ground_station(&stations).unwrap() != "beta" { return false; }

    if !is_line_of_sight(5.0) { return false; }
    if is_line_of_sight(-5.0) { return false; }

    let az = normalize_azimuth(450.0);
    if (az - 90.0).abs() > 0.01 { return false; }

    let budget = link_budget_db(30.0, 10.0, 5.0);
    if (budget - 35.0).abs() > 0.01 { return false; }

    let all_stations = vec!["A".to_string(), "B".to_string(), "C".to_string()];
    let failover = route_failover(&all_stations, "A");
    if failover.contains(&"A".to_string()) { return false; }

    // ── scheduling checks ──
    let end = contact_window_end(1000.0, 300.0);
    if (end - 1300.0).abs() > 0.01 { return false; }

    let delta = next_pass_delta_s(100.0, 600.0);
    if (delta - 500.0).abs() > 0.01 { return false; }

    if !mission_overlap(0.0, 10.0, 5.0, 15.0) { return false; }
    if mission_overlap(0.0, 5.0, 10.0, 15.0) { return false; }

    let opt = optimal_downlink_elevation(&[10.0, 45.0, 30.0]);
    if (opt - 45.0).abs() > 0.01 { return false; }

    let gap_s = contact_gap_s(1000.0, 4600.0);
    if (gap_s - 3600.0).abs() > 0.01 { return false; }

    let passes = recurring_passes(0.0, 5400.0, 3);
    if passes.len() != 3 { return false; }
    if (passes[1] - 5400.0).abs() > 1.0 { return false; }
    if (passes[2] - 10800.0).abs() > 1.0 { return false; }

    // ── power checks ──
    let solar = solar_panel_output_watts(100.0, 0.0);
    if (solar - 100.0).abs() > 0.01 { return false; }

    let soc = battery_soc(50.0, 100.0);
    if (soc - 0.5).abs() > 0.01 { return false; }

    let budget_w = power_budget_watts(200.0, 150.0);
    if (budget_w - 50.0).abs() > 0.01 { return false; }

    let dod = depth_of_discharge(0.8);
    if (dod - 0.2).abs() > 0.01 { return false; }

    if battery_health(999) != "good" { return false; }
    if battery_health(1000) != "degraded" { return false; }

    if power_mode(0.05) != "critical" { return false; }
    if power_mode(0.2) != "low" { return false; }
    if power_mode(0.5) != "normal" { return false; }

    let flux = solar_flux_w_per_m2(1361.0, 1.0);
    if (flux - 1361.0).abs() > 1.0 { return false; }
    let flux2 = solar_flux_w_per_m2(1361.0, 2.0);
    if (flux2 - 340.25).abs() > 1.0 { return false; }

    let total = total_power_watts(100.0, 50.0);
    if (total - 150.0).abs() > 0.01 { return false; }

    // ── telemetry checks ──
    let sample = TelemetrySample { battery_pct: 82.0, thermal_c: 63.0, attitude_jitter: 0.8 };
    let hs = health_score(&sample);
    if hs < 0.65 { return false; }

    if !is_anomaly(100.0, 100.0) { return false; }
    if is_anomaly(99.0, 100.0) { return false; }

    if latency_bucket(49) != "fast" { return false; }
    if latency_bucket(50) != "normal" { return false; }
    if latency_bucket(200) != "slow" { return false; }

    let er = error_rate(100, 5);
    if (er - 0.05).abs() > 0.01 { return false; }

    let tp = throughput(1000, 500);
    if (tp - 2.0).abs() > 0.01 { return false; }

    let up = uptime_percentage(1000, 100);
    if (up - 90.0).abs() > 0.01 { return false; }

    let fmt = format_metric("cpu", 85.5);
    if !fmt.contains(":") { return false; }

    if !should_alert(95.0, 90.0) { return false; }
    if should_alert(80.0, 90.0) { return false; }

    let mean = aggregate_mean(&[10.0, 20.0, 30.0]);
    if (mean - 20.0).abs() > 0.01 { return false; }

    if !is_within_threshold(9.5, 10.0, 0.5) { return false; }
    if is_within_threshold(8.0, 10.0, 1.0) { return false; }

    let j = jitter_score(10.0, 8.0);
    if (j - 2.0).abs() > 0.01 { return false; }

    let st = staleness_s(1000, 800);
    if st != 200 { return false; }

    let summary = telemetry_summary(85.0, 23.5);
    if !summary.contains("%") { return false; }

    // ── resilience checks ──
    if retry_backoff_ms(1, 50) >= retry_backoff_ms(2, 50) { return false; }
    if !circuit_open(5) { return false; }
    if circuit_open(4) { return false; }
    if accept_version(9, 10) { return false; }
    if !accept_version(10, 10) { return false; }
    if dedupe_ids(&["a", "b", "a"]) != 2 { return false; }

    let ci = checkpoint_interval_s(10, 3);
    if ci != 30 { return false; }

    if degradation_level(0.05) != "minor" { return false; }
    if degradation_level(0.3) != "moderate" { return false; }
    if degradation_level(0.8) != "critical" { return false; }

    let br = bulkhead_remaining(10, 3);
    if br != 7 { return false; }

    if !cascade_failure_check(&[true, false, false]) { return false; }
    if cascade_failure_check(&[false, false]) { return false; }

    let rr = recovery_rate(8, 10);
    if (rr - 0.8).abs() > 0.01 { return false; }

    if retry_delay_ms(100, 0) != 100 { return false; }
    if retry_delay_ms(100, 1) != 200 { return false; }
    if retry_delay_ms(100, 2) != 400 { return false; }

    if !should_trip(5, 5) { return false; }
    if should_trip(4, 5) { return false; }

    if !half_open_allowed(3, 0) { return false; }
    if half_open_allowed(3, 3) { return false; }

    if !in_failure_window(990, 1000, 20) { return false; }
    if in_failure_window(900, 1000, 20) { return false; }

    let sd = state_duration_s(5000, 8000);
    if sd != 3 { return false; }

    if (fallback_value(true, 10.0, 99.0) - 10.0).abs() > 0.01 { return false; }
    if (fallback_value(false, 10.0, 99.0) - 99.0).abs() > 0.01 { return false; }

    if !circuit_should_reset(true, true) { return false; }
    if circuit_should_reset(false, true) { return false; }

    // ── auth checks ──
    if !authorize_command("flight_operator", "c", "fire_thruster") { return false; }
    if authorize_command("observer", "c", "fire_thruster") { return false; }

    if !validate_token_format("abc123") { return false; }
    if validate_token_format("") { return false; }

    if password_strength("abcdefgh") != "medium" { return false; }
    if password_strength("abcdefghijkl") != "strong" { return false; }
    if password_strength("abc") != "weak" { return false; }

    if !mask_sensitive("abcdefgh").ends_with("efgh") { return false; }

    if !rate_limit_key("192.168.1.1", "/api").contains("192.168.1.1") { return false; }

    if session_expired(1000, 300, 1200) { return false; }
    if !session_expired(1000, 300, 1400) { return false; }

    let sanitized = sanitize_header("foo\r\nbar");
    if sanitized.contains('\r') || sanitized.contains('\n') { return false; }

    if !permission_check(&["read", "write"], &["read", "write", "admin"]) { return false; }
    if permission_check(&["read", "write"], &["read"]) { return false; }

    if ip_in_allowlist("10.0.0.10", &["10.0.0.1"]) { return false; }
    if !ip_in_allowlist("10.0.0.1", &["10.0.0.1"]) { return false; }

    if hash_credential("pass", "salt") != "hash(salt:pass)" { return false; }

    let te = token_expiry(1000, 300);
    if te != 1300 { return false; }

    if scope_includes("read", "readwrite") { return false; }
    if !scope_includes("read", "read") { return false; }

    if role_hierarchy("admin") <= role_hierarchy("observer") { return false; }

    // ── events checks ──
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 300, kind: "X".into(), payload: "".into() },
        SatEvent { id: "b".into(), timestamp: 100, kind: "Y".into(), payload: "".into() },
    ];
    let sorted = sort_events_by_time(&events);
    if sorted[0].timestamp != 100 { return false; }

    let dup_events = vec![
        SatEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "first".into() },
        SatEvent { id: "a".into(), timestamp: 200, kind: "X".into(), payload: "second".into() },
    ];
    let deduped = dedup_events(&dup_events);
    if deduped.len() != 1 || deduped[0].payload != "first" { return false; }

    let filtered = filter_time_window(&events, 100, 300);
    if filtered.len() != 2 { return false; }

    if detect_gaps(&events, 201) { return false; }
    if !detect_gaps(&events, 200) { return false; }

    let counts = count_by_kind(&events);
    if *counts.get("X").unwrap() != 1 { return false; }

    // ── planner check ──
    let plan = BurnPlan { delta_v_mps: 44.5, burn_seconds: 310.0, fuel_margin_kg: 8.0 };
    if !validate_plan(&plan) { return false; }

    // ── new orbit checks ──
    let j2_drift = j2_raan_drift_deg_per_day(7000.0, 51.6);
    if j2_drift >= 0.0 { return false; } // prograde orbit should have negative drift

    let n = mean_motion_rad_s(6771.0);
    if n < 0.001 || n > 0.002 { return false; } // ~0.00113 rad/s

    let v_peri = periapsis_velocity(6771.0, 0.0);
    let v_circ = velocity_at_altitude(400.0);
    if (v_peri - v_circ).abs() > 0.1 { return false; } // circular orbit check

    let footprint = ground_footprint_radius_km(400.0);
    if footprint < 1500.0 || footprint > 3000.0 { return false; }

    // ── new safety checks ──
    let d3d = miss_distance_3d(0.0, 0.0, 0.0, 3.0, 4.0, 12.0);
    if (d3d - 13.0).abs() > 0.1 { return false; }

    let cum_prob = cumulative_collision_prob(&[0.1, 0.2, 0.3]);
    if (cum_prob - 0.496).abs() > 0.01 { return false; }

    let threats = prioritize_threats(&[(0.1, 10.0, 1.0), (0.9, 0.5, 5.0), (0.5, 1.0, 2.0)]);
    if threats[0] != 1 { return false; } // highest threat first

    // ── new power checks ──
    let margin = power_margin_pct(200.0, 100.0);
    if (margin - 100.0).abs() > 1.0 { return false; }

    let t_eq = thermal_equilibrium_k(0.3, 1361.0, 0.9);
    if t_eq < 200.0 || t_eq > 300.0 { return false; }

    // ── new routing checks ──
    let eirp = eirp_dbw(20.0, 35.0, 2.0);
    if (eirp - 53.0).abs() > 0.01 { return false; }

    let best_ant = select_best_antenna(&[
        ("low".to_string(), 5.0, 2.0),
        ("high".to_string(), 35.0, 12.0),
    ]);
    if best_ant.as_deref() != Some("high") { return false; }

    // ── new resilience checks ──
    let cb = circuit_breaker_next_state("half_open", false, false, true);
    if cb != "closed" { return false; }

    let cb2 = circuit_breaker_next_state("half_open", false, false, false);
    if cb2 != "open" { return false; }

    let (hq, _) = health_check_quorum(&[true, true, true, false], 0.75);
    if !hq { return false; }

    // ── new auth checks ──
    if validate_claims(100, 200, 150, 120) { return false; } // now < nbf
    if !validate_claims(100, 200, 50, 150) { return false; }

    if !mfa_check(&[true, true, false], 2) { return false; }

    if rotate_key_index(0, 3) != 1 { return false; }
    if rotate_key_index(2, 3) != 0 { return false; }

    // ── new orbit domain checks ──
    let prec = nodal_precession_period_days(6778.0, 51.6);
    if prec.abs() < 50.0 || prec.abs() > 100.0 { return false; } // ~72 days

    let u = argument_of_latitude(1.0, 1.0);
    if u < 0.0 || u >= std::f64::consts::TAU { return false; }

    let rho_300 = atmospheric_density_kg_m3(300.0);
    let rho_500 = atmospheric_density_kg_m3(500.0);
    if rho_300 <= rho_500 { return false; } // density decreases with altitude

    // density continuity at 400km band boundary
    let rho_399 = atmospheric_density_kg_m3(399.0);
    let rho_401 = atmospheric_density_kg_m3(401.0);
    let ratio = rho_399 / rho_401;
    if ratio < 0.5 || ratio > 2.0 { return false; }

    // ── new safety domain checks ──
    let md = mahalanobis_distance(3.0, 4.0, 0.0, 1.0, 1.0, 1.0);
    if (md - 5.0).abs() > 0.1 { return false; } // equals Euclidean with unit cov

    // ── new power domain checks ──
    let eol = end_of_life_power(1000.0, 0.0, 3.0);
    if (eol - 1000.0).abs() > 1.0 { return false; } // 0 years = BOL

    let eol15 = end_of_life_power(1000.0, 15.0, 3.0);
    let expected_eol = 1000.0 * 0.97_f64.powf(15.0);
    if (eol15 - expected_eol).abs() > 10.0 { return false; }

    // ── new resilience domain checks ──
    let timeout = adaptive_timeout_ms(&[10, 20, 30, 40, 50], 90.0, 50, 5000);
    if timeout < 50 || timeout > 5000 { return false; }

    let (shed_low, _) = load_shedding(50.0, 100.0, &[1, 2, 3]);
    if shed_low { return false; } // below 80% should not shed

    let (shed_high, cutoff) = load_shedding(95.0, 100.0, &[1, 2, 3]);
    if !shed_high { return false; }
    if cutoff == 0 { return false; }

    // ── new auth domain checks ──
    let rbac_admin = evaluate_rbac("admin", "admin", &[], &[]);
    if !rbac_admin { return false; }

    let rbac_observer = evaluate_rbac("observer", "admin", &[], &[]);
    if rbac_observer { return false; }

    let rbac_denied = evaluate_rbac("operator", "deploy", &[("operator", "deploy")], &[("operator", "deploy")]);
    if rbac_denied { return false; } // denial overrides grant

    // ── parametric variation per idx ──
    let alt = 200.0 + (idx % 500) as f64;
    let sma_var = semi_major_axis_km(alt);
    if sma_var < 6500.0 || sma_var > 7500.0 { return false; }

    let sev = (idx % 4) as u32;
    let prob = (idx % 4) as u32;
    let _ = risk_matrix_score(sev, prob);

    let prio = schedule_priority(10.0, 5.0);
    if prio <= 0.0 { return false; }

    true
}

#[test]
fn hyper_matrix_scenarios() {
    let mut passed = 0usize;
    let mut failed = 0usize;

    for idx in 0..TOTAL_CASES {
        if run_case(idx) {
            passed += 1;
        } else {
            failed += 1;
        }
    }

    println!("TB_SUMMARY total={} passed={} failed={}", TOTAL_CASES, passed, failed);
    assert_eq!(failed, 0, "hyper matrix had {} failing scenarios", failed);
}
