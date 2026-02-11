use aerolith::config::{
    default_orbit_altitude, default_pool_size, validate_config, validate_endpoint,
    normalize_env_name, constellation_size, max_burn_duration, parse_feature_flags,
    is_operational, config_priority, build_connection_string, heartbeat_interval_ms,
};
use aerolith::orbit::{
    orbital_period_minutes, semi_major_axis_km, velocity_at_altitude,
    inclination_change_dv, hohmann_transfer_dv, time_to_node_s,
    ground_track_shift_deg, eclipse_fraction, relative_velocity,
    altitude_decay_rate_km_per_day, orbit_energy, apoapsis_from_elements,
};
use aerolith::safety::{
    collision_probability, in_keep_out_zone, debris_density, maneuver_risk,
    safe_separation_m, sort_conjunctions, is_reentry, fragmentation_risk,
    collision_avoidance_window, threat_level, max_debris_count,
    exclusion_zone_radius_m, is_safe_for_eva, risk_matrix_score,
};
use aerolith::sequencing::{
    Command, priority_sort, deduplicate_commands, batch_commands,
    command_in_window, merge_queues, is_critical_sequence, command_rate,
    execution_gap, sequence_checksum, reorder_by_dependency,
    command_timeout_ms, validate_epoch,
};
use aerolith::routing::{
    link_margin_db, free_space_loss, ground_station_visible, antenna_gain,
    best_ground_station, data_rate_mbps, slant_range_km, doppler_shift_hz,
    contact_duration_s, handover_station, link_budget_db, normalize_azimuth,
    is_line_of_sight, route_failover,
};
use aerolith::scheduling::{
    contact_window_end, eclipse_start_fraction, next_pass_delta_s,
    mission_overlap, schedule_priority, merge_windows, eclipse_duration_s,
    optimal_downlink_elevation, slot_available, recurring_passes,
    time_to_next_eclipse, contact_gap_s,
};
use aerolith::power::{
    solar_panel_output_watts, battery_soc, power_budget_watts,
    charge_time_hours, depth_of_discharge, battery_health,
    eclipse_drain_wh, solar_flux_w_per_m2, power_mode,
    heater_power_watts, panel_degradation, total_power_watts,
};
use aerolith::telemetry::{
    is_anomaly, latency_bucket, error_rate, throughput, uptime_percentage,
    format_metric, should_alert, aggregate_mean, is_within_threshold,
    jitter_score, staleness_s, telemetry_summary,
};
use aerolith::resilience::{
    checkpoint_interval_s, degradation_level, bulkhead_remaining,
    cascade_failure_check, recovery_rate, retry_delay_ms, should_trip,
    half_open_allowed, in_failure_window, state_duration_s,
    fallback_value, circuit_should_reset,
};
use aerolith::auth::{
    validate_token_format, password_strength, mask_sensitive, rate_limit_key,
    session_expired, sanitize_header, permission_check, ip_in_allowlist,
    hash_credential, token_expiry, scope_includes, role_hierarchy,
};
use aerolith::events::{
    SatEvent, sort_events_by_time, dedup_events, filter_time_window,
    detect_gaps, count_by_kind, merge_event_streams, batch_events, event_rate,
};

// ── config tests ──

#[test]
fn config_default_altitude() {
    assert_eq!(default_orbit_altitude(), 550.0);
}

#[test]
fn config_pool_size() {
    assert_eq!(default_pool_size(), 32);
}

#[test]
fn config_validate_port() {
    assert!(!validate_config(0, "test"));
    assert!(validate_config(1, "test"));
}

#[test]
fn config_endpoint() {
    assert!(validate_endpoint("http://localhost:8080"));
    assert!(validate_endpoint("https://api.example.com"));
    assert!(!validate_endpoint("ftp://bad"));
    assert!(!validate_endpoint("data:http://evil"));
}

#[test]
fn config_env_normalize() {
    assert_eq!(normalize_env_name("Production"), "production");
    assert_eq!(normalize_env_name("STAGING"), "staging");
}

// ── orbit tests ──

#[test]
fn orbit_semi_major_axis() {
    assert!((semi_major_axis_km(400.0) - 6771.0).abs() < 1.0);
}

#[test]
fn orbit_velocity() {
    let v = velocity_at_altitude(400.0);
    assert!(v > 7000.0 && v < 8000.0, "velocity should be ~7670 m/s, got {v}");
}

#[test]
fn orbit_period() {
    let p = orbital_period_minutes(400.0);
    assert!(p > 90.0 && p < 95.0, "period should be ~92 min, got {p}");
}

#[test]
fn orbit_apoapsis() {
    let ap = apoapsis_from_elements(7000.0, 0.1);
    assert!((ap - 7700.0).abs() < 1.0);
}

#[test]
fn orbit_energy_negative() {
    let e = orbit_energy(7000.0);
    assert!(e < 0.0, "orbital energy should be negative");
}

// ── safety tests ──

#[test]
fn safety_keep_out_zone_boundary() {
    assert!(in_keep_out_zone(1.0, 1.0));
    assert!(in_keep_out_zone(0.5, 1.0));
    assert!(!in_keep_out_zone(1.1, 1.0));
}

#[test]
fn safety_reentry_threshold() {
    assert!(is_reentry(119.0));
    assert!(!is_reentry(120.0));
    assert!(!is_reentry(150.0));
}

#[test]
fn safety_threat_level_boundaries() {
    assert_eq!(threat_level(0.75), 4);
    assert_eq!(threat_level(0.50), 3);
    assert_eq!(threat_level(0.25), 2);
    assert_eq!(threat_level(0.10), 1);
}

#[test]
fn safety_debris_filter() {
    let sizes = vec![0.5, 1.0, 2.0, 5.0, 10.0];
    assert_eq!(max_debris_count(&sizes, 2.0), 3);
}

#[test]
fn safety_risk_matrix() {
    assert_eq!(risk_matrix_score(3, 2), 32);
}

// ── sequencing tests ──

#[test]
fn seq_priority_sort_descending() {
    let mut cmds = vec![
        Command { id: "a".into(), epoch: 10, critical: false },
        Command { id: "b".into(), epoch: 30, critical: false },
        Command { id: "c".into(), epoch: 20, critical: false },
    ];
    priority_sort(&mut cmds);
    assert_eq!(cmds[0].epoch, 30);
    assert_eq!(cmds[2].epoch, 10);
}

#[test]
fn seq_dedup_keeps_first() {
    let cmds = vec![
        Command { id: "x".into(), epoch: 1, critical: false },
        Command { id: "x".into(), epoch: 2, critical: true },
    ];
    let result = deduplicate_commands(&cmds);
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].epoch, 1);
}

#[test]
fn seq_batch_size() {
    let cmds: Vec<Command> = (0..10).map(|i| Command { id: format!("c{i}"), epoch: i, critical: false }).collect();
    let batches = batch_commands(&cmds, 3);
    assert_eq!(batches.len(), 4); // ceil(10/3) = 4
    assert_eq!(batches[0].len(), 3);
}

#[test]
fn seq_window_inclusive() {
    assert!(command_in_window(100, 100, 200));
    assert!(command_in_window(200, 100, 200));
}

#[test]
fn seq_validate_epoch_boundary() {
    assert!(validate_epoch(100, 100));
    assert!(!validate_epoch(0, 100));
    assert!(!validate_epoch(101, 100));
}

// ── routing tests ──

#[test]
fn routing_link_margin() {
    assert!((link_margin_db(-70.0, -100.0) - 30.0).abs() < 0.01);
}

#[test]
fn routing_ground_visible_boundary() {
    assert!(ground_station_visible(10.0, 10.0));
    assert!(ground_station_visible(15.0, 10.0));
    assert!(!ground_station_visible(5.0, 10.0));
}

#[test]
fn routing_best_station() {
    let stations = vec![
        ("alpha".into(), 50.0),
        ("beta".into(), 10.0),
        ("gamma".into(), 30.0),
    ];
    assert_eq!(best_ground_station(&stations).unwrap(), "beta");
}

#[test]
fn routing_line_of_sight() {
    assert!(is_line_of_sight(5.0));
    assert!(!is_line_of_sight(-5.0));
}

#[test]
fn routing_normalize_azimuth_wrap() {
    assert!((normalize_azimuth(450.0) - 90.0).abs() < 0.01);
    assert!((normalize_azimuth(-90.0) - 270.0).abs() < 0.01);
}

// ── scheduling tests ──

#[test]
fn sched_contact_window() {
    assert!((contact_window_end(1000.0, 300.0) - 1300.0).abs() < 0.01);
}

#[test]
fn sched_next_pass_delta() {
    assert!((next_pass_delta_s(100.0, 600.0) - 500.0).abs() < 0.01);
}

#[test]
fn sched_mission_overlap_check() {
    assert!(mission_overlap(0.0, 10.0, 5.0, 15.0));
    assert!(!mission_overlap(0.0, 5.0, 10.0, 15.0));
}

#[test]
fn sched_optimal_downlink() {
    assert!((optimal_downlink_elevation(&[10.0, 45.0, 30.0]) - 45.0).abs() < 0.01);
}

#[test]
fn sched_contact_gap() {
    assert!((contact_gap_s(1000.0, 4600.0) - 3600.0).abs() < 0.01);
}

// ── power tests ──

#[test]
fn power_solar_output() {
    let output = solar_panel_output_watts(100.0, 0.0);
    assert!((output - 100.0).abs() < 0.01);
    let output30 = solar_panel_output_watts(100.0, 30.0);
    assert!((output30 - 86.6).abs() < 1.0);
}

#[test]
fn power_battery_soc_calc() {
    assert!((battery_soc(50.0, 100.0) - 0.5).abs() < 0.01);
}

#[test]
fn power_budget() {
    assert!((power_budget_watts(200.0, 150.0) - 50.0).abs() < 0.01);
}

#[test]
fn power_depth_of_discharge() {
    assert!((depth_of_discharge(0.8) - 0.2).abs() < 0.01);
}

#[test]
fn power_mode_thresholds() {
    assert_eq!(power_mode(0.05), "critical");
    assert_eq!(power_mode(0.2), "low");
    assert_eq!(power_mode(0.5), "normal");
}

// ── telemetry tests ──

#[test]
fn telem_anomaly_boundary() {
    assert!(is_anomaly(100.0, 100.0));
    assert!(is_anomaly(101.0, 100.0));
    assert!(!is_anomaly(99.0, 100.0));
}

#[test]
fn telem_latency_bucket_boundary() {
    assert_eq!(latency_bucket(49), "fast");
    assert_eq!(latency_bucket(50), "normal");
    assert_eq!(latency_bucket(199), "normal");
    assert_eq!(latency_bucket(200), "slow");
}

#[test]
fn telem_error_rate_calc() {
    let rate = error_rate(100, 5);
    assert!((rate - 0.05).abs() < 0.01);
}

#[test]
fn telem_should_alert_check() {
    assert!(should_alert(95.0, 90.0));
    assert!(!should_alert(80.0, 90.0));
}

#[test]
fn telem_summary_units() {
    let s = telemetry_summary(85.0, 23.5);
    assert!(s.contains("%"), "should contain percent unit");
    assert!(s.contains("C") || s.contains("°"), "should contain temperature unit");
}

// ── resilience tests ──

#[test]
fn resil_degradation() {
    assert_eq!(degradation_level(0.05), "minor");
    assert_eq!(degradation_level(0.3), "moderate");
    assert_eq!(degradation_level(0.8), "critical");
}

#[test]
fn resil_retry_exponential() {
    assert_eq!(retry_delay_ms(100, 0), 100);
    assert_eq!(retry_delay_ms(100, 1), 200);
    assert_eq!(retry_delay_ms(100, 2), 400);
}

#[test]
fn resil_should_trip_boundary() {
    assert!(should_trip(5, 5));
    assert!(!should_trip(4, 5));
}

#[test]
fn resil_cascade_any() {
    assert!(cascade_failure_check(&[true, false, false]));
    assert!(!cascade_failure_check(&[false, false, false]));
}

#[test]
fn resil_fallback() {
    assert!((fallback_value(true, 10.0, 99.0) - 10.0).abs() < 0.01);
    assert!((fallback_value(false, 10.0, 99.0) - 99.0).abs() < 0.01);
}

// ── auth tests ──

#[test]
fn auth_token_format() {
    assert!(validate_token_format("abc123"));
    assert!(!validate_token_format(""));
}

#[test]
fn auth_password_strength_boundaries() {
    assert_eq!(password_strength("abcdefgh"), "medium");
    assert_eq!(password_strength("abcdefghijkl"), "strong");
    assert_eq!(password_strength("abc"), "weak");
}

#[test]
fn auth_mask() {
    let masked = mask_sensitive("abcdefgh");
    assert!(masked.ends_with("efgh"));
    assert!(masked.starts_with("*"));
}

#[test]
fn auth_rate_limit() {
    let key = rate_limit_key("192.168.1.1", "/api");
    assert!(key.contains("192.168.1.1"));
    assert!(key.contains("/api"));
}

#[test]
fn auth_permissions() {
    assert!(permission_check(&["read", "write"], &["read", "write", "admin"]));
    assert!(!permission_check(&["read", "write"], &["read"]));
}

// ── events tests ──

#[test]
fn events_sort_ascending() {
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 300, kind: "X".into(), payload: "".into() },
        SatEvent { id: "b".into(), timestamp: 100, kind: "Y".into(), payload: "".into() },
    ];
    let sorted = sort_events_by_time(&events);
    assert_eq!(sorted[0].timestamp, 100);
    assert_eq!(sorted[1].timestamp, 300);
}

#[test]
fn events_dedup_earliest() {
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "first".into() },
        SatEvent { id: "a".into(), timestamp: 200, kind: "X".into(), payload: "second".into() },
    ];
    let deduped = dedup_events(&events);
    assert_eq!(deduped.len(), 1);
    assert_eq!(deduped[0].payload, "first");
}

#[test]
fn events_filter_window_inclusive() {
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "".into() },
        SatEvent { id: "b".into(), timestamp: 200, kind: "Y".into(), payload: "".into() },
        SatEvent { id: "c".into(), timestamp: 300, kind: "Z".into(), payload: "".into() },
    ];
    let filtered = filter_time_window(&events, 100, 200);
    assert_eq!(filtered.len(), 2);
}

#[test]
fn events_detect_gaps_threshold() {
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "".into() },
        SatEvent { id: "b".into(), timestamp: 200, kind: "Y".into(), payload: "".into() },
    ];
    assert!(detect_gaps(&events, 100));
    assert!(!detect_gaps(&events, 101));
}

#[test]
fn events_count_by_kind_check() {
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "".into() },
        SatEvent { id: "b".into(), timestamp: 200, kind: "X".into(), payload: "".into() },
        SatEvent { id: "c".into(), timestamp: 300, kind: "Y".into(), payload: "".into() },
    ];
    let counts = count_by_kind(&events);
    assert_eq!(*counts.get("X").unwrap(), 2);
    assert_eq!(*counts.get("Y").unwrap(), 1);
}
