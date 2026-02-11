use aerolith::orbit::{
    j2_raan_drift_deg_per_day, propagate_mean_anomaly, mean_motion_rad_s,
    true_anomaly_approx, periapsis_velocity, ground_footprint_radius_km,
    velocity_at_altitude, semi_major_axis_km, orbital_period_minutes,
    nodal_precession_period_days, argument_of_latitude,
    atmospheric_density_kg_m3, drag_decay_rate,
};
use aerolith::safety::{
    miss_distance_3d, conjunction_screening, time_to_closest_approach,
    cumulative_collision_prob, debris_cloud_radius_km, prioritize_threats,
    collision_probability, in_keep_out_zone, threat_level,
    mahalanobis_distance, maneuver_feasibility,
};
use aerolith::power::{
    battery_remaining_cycles, thermal_equilibrium_k, eclipse_battery_capacity_wh,
    solar_array_area_m2, power_margin_pct, solar_panel_output_watts,
    battery_soc, power_budget_watts, power_mode,
    end_of_life_power, charge_discharge_profile,
};
use aerolith::routing::{
    propagation_delay_ms, multi_hop_latency_ms, atmospheric_attenuation_db,
    eirp_dbw, carrier_to_noise_db_hz, select_best_antenna,
    link_margin_db, best_ground_station, is_line_of_sight,
    complete_link_budget, inter_satellite_link,
};
use aerolith::scheduling::{
    greedy_schedule, ground_track_repeat_period_s, visibility_duration_s,
    find_conflicts, merge_by_priority, contact_window_end, mission_overlap,
    optimal_downlink_elevation, recurring_passes, weighted_schedule,
};
use aerolith::sequencing::{
    topological_sort_commands, coalesce_commands, priority_insert_index,
    throttle_commands, Command, priority_sort, batch_commands,
    build_execution_plan,
};
use aerolith::telemetry::{
    exponential_moving_average, percentile, z_score_outliers,
    rate_of_change, composite_health_score, is_anomaly, should_alert,
    aggregate_mean, format_metric,
    mad_anomaly_detection, pearson_correlation,
};
use aerolith::resilience::{
    circuit_breaker_next_state, sliding_window_allow, backoff_with_jitter_ms,
    health_check_quorum, retry_budget, fallback_value, cascade_failure_check,
    should_trip, checkpoint_interval_s,
    adaptive_timeout_ms, load_shedding, bulkhead_assign,
};
use aerolith::auth::{
    validate_claims, secure_compare, mfa_check, rotate_key_index,
    path_matches_pattern, compute_signature, permission_check,
    validate_token_format, session_expired, role_hierarchy,
    evaluate_rbac, progressive_lockout,
};
use aerolith::events::{
    SatEvent, correlate_events, is_causally_ordered, dedup_within_window,
    event_throughput_buckets, sort_events_by_time, dedup_events,
    filter_time_window, detect_gaps,
    detect_event_pattern, join_event_streams,
};
use aerolith::concurrency::{TelemetryCounter, SatelliteState, CommandQueue, TokenBucket};
use aerolith::integration;

// ═══════════════════════════════════════════════════════════════
// ORBIT: Domain logic & latent bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn j2_raan_drift_prograde_orbit_should_be_negative() {
    // For prograde orbits (i < 90°), RAAN drifts westward (negative)
    let drift = j2_raan_drift_deg_per_day(7000.0, 51.6);
    assert!(drift < 0.0, "RAAN drift for prograde orbit should be negative, got {drift}");
}

#[test]
fn j2_raan_drift_sun_synchronous() {
    // Sun-sync orbit at ~98° inclination should have positive drift ~0.9856 deg/day
    let drift = j2_raan_drift_deg_per_day(7078.0, 98.0);
    assert!(drift > 0.0, "Sun-sync RAAN drift should be positive, got {drift}");
    assert!((drift - 0.9856).abs() < 0.1, "Sun-sync drift should be ~0.986 deg/day, got {drift}");
}

#[test]
fn propagate_mean_anomaly_wraps_correctly() {
    // Starting at 350°, advancing 20° should give ~10° (wraps past 360)
    let start = 350.0_f64.to_radians();
    let n = 0.001; // rad/s
    let dt = 20.0_f64.to_radians() / n;
    let result = propagate_mean_anomaly(start, n, dt);
    // Should be in [0, 2π)
    assert!(result >= 0.0, "Mean anomaly should be non-negative, got {result}");
    assert!(result < std::f64::consts::TAU, "Mean anomaly should be < 2π, got {result}");
    let expected = (10.0_f64).to_radians();
    assert!((result - expected).abs() < 0.01, "Expected ~{expected}, got {result}");
}

#[test]
fn propagate_mean_anomaly_negative_start_handled() {
    // Even with negative initial anomaly (from perturbation), result should be in [0, 2π)
    let start = -0.1;
    let result = propagate_mean_anomaly(start, 0.001, 100.0);
    assert!(result >= 0.0, "Result should be non-negative for negative input, got {result}");
}

#[test]
fn mean_motion_units_are_rad_per_second() {
    // For a ~400km orbit, mean motion should be ~0.00113 rad/s
    let n = mean_motion_rad_s(6771.0);
    assert!(n > 0.001 && n < 0.002, "Mean motion should be ~0.00113 rad/s, got {n}");
}

#[test]
fn true_anomaly_small_eccentricity_correction() {
    let e = 0.01;
    let m = 1.0; // 1 radian
    let v = true_anomaly_approx(m, e);
    // For small e: ν ≈ M + 2e*sin(M)
    let expected = m + 2.0 * e * m.sin();
    assert!((v - expected).abs() < 0.001, "Expected {expected}, got {v}");
}

#[test]
fn periapsis_velocity_circular_orbit() {
    // For circular orbit (e=0), periapsis velocity = orbital velocity
    let v_peri = periapsis_velocity(6771.0, 0.0);
    let v_circ = velocity_at_altitude(400.0);
    assert!((v_peri - v_circ).abs() < 0.1,
        "For circular orbit, periapsis v should equal circular v: {v_peri} vs {v_circ}");
}

#[test]
fn periapsis_velocity_eccentric_orbit_higher_than_circular() {
    // Periapsis velocity in eccentric orbit > circular velocity at same semi-major
    let v_peri = periapsis_velocity(7000.0, 0.1);
    let v_circ = (398600.4418 / 7000.0_f64).sqrt();
    assert!(v_peri > v_circ,
        "Periapsis v should exceed circular v: {v_peri} vs {v_circ}");
}

#[test]
fn ground_footprint_at_400km() {
    // At 400km altitude, footprint radius should be ~2200 km
    let radius = ground_footprint_radius_km(400.0);
    assert!(radius > 1500.0 && radius < 3000.0,
        "Footprint at 400km should be ~2200km, got {radius}");
}

#[test]
fn ground_footprint_increases_with_altitude() {
    let r_low = ground_footprint_radius_km(400.0);
    let r_high = ground_footprint_radius_km(800.0);
    assert!(r_high > r_low, "Higher altitude should give larger footprint");
}

// ═══════════════════════════════════════════════════════════════
// SAFETY: Domain logic & multi-step bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn miss_distance_3d_includes_z_component() {
    // If objects differ only in Z, distance should be non-zero
    let d = miss_distance_3d(0.0, 0.0, 0.0, 0.0, 0.0, 5.0);
    assert!((d - 5.0).abs() < 0.01, "Pure Z separation = 5.0, got {d}");
}

#[test]
fn miss_distance_3d_pythagorean() {
    let d = miss_distance_3d(0.0, 0.0, 0.0, 3.0, 4.0, 12.0);
    assert!((d - 13.0).abs() < 0.01, "3-4-12 triangle diagonal = 13, got {d}");
}

#[test]
fn conjunction_screening_uses_rss_of_sigmas() {
    // RSS(1,1,1) = sqrt(3) ≈ 1.732, not 1+1+1 = 3
    // miss = 2.5, hard_body = 0.1, k = 1.0
    // Correct threshold = 0.1 + 1.0 * sqrt(3) = 1.832 → miss(2.5) > threshold → false
    // With sum: threshold = 0.1 + 1.0 * 3.0 = 3.1 → miss(2.5) < threshold → true (wrong)
    let result = conjunction_screening(2.5, 0.1, 1.0, 1.0, 1.0, 1.0);
    assert!(!result, "Miss distance 2.5 should be outside RSS threshold ~1.83");
}

#[test]
fn time_to_closest_approach_positive_for_converging() {
    // Objects moving toward each other should have positive TCA
    // Position: (10, 0, 0), Velocity: (-1, 0, 0) → approaching origin
    let tca = time_to_closest_approach(10.0, 0.0, 0.0, -1.0, 0.0, 0.0);
    assert!(tca > 0.0, "TCA should be positive for converging objects, got {tca}");
    assert!((tca - 10.0).abs() < 0.01, "TCA should be 10s, got {tca}");
}

#[test]
fn cumulative_collision_prob_independent_events() {
    // P_cum = 1 - (1-0.1)(1-0.2)(1-0.3) = 1 - 0.504 = 0.496
    let probs = vec![0.1, 0.2, 0.3];
    let cum = cumulative_collision_prob(&probs);
    assert!((cum - 0.496).abs() < 0.01, "Expected cumulative prob ~0.496, got {cum}");
}

#[test]
fn cumulative_collision_prob_single_event() {
    let cum = cumulative_collision_prob(&[0.5]);
    assert!((cum - 0.5).abs() < 0.01, "Single event should return its probability, got {cum}");
}

#[test]
fn debris_cloud_expands_over_time() {
    let r0 = debris_cloud_radius_km(1.0, 0.1, 0.0);
    let r1 = debris_cloud_radius_km(1.0, 0.1, 100.0);
    let r2 = debris_cloud_radius_km(1.0, 0.1, 1000.0);
    assert!((r0 - 1.0).abs() < 0.01, "At t=0, radius should be initial: {r0}");
    assert!((r1 - 11.0).abs() < 0.01, "At t=100s, radius should be 1+0.1*100=11: {r1}");
    assert!(r2 > r1, "Cloud should grow over time");
}

#[test]
fn prioritize_threats_highest_first() {
    // Object 0: prob=0.1, dist=10, vel=1 → score = 0.01
    // Object 1: prob=0.9, dist=0.5, vel=5 → score = 9.0
    // Object 2: prob=0.5, dist=1, vel=2 → score = 1.0
    let objects = vec![(0.1, 10.0, 1.0), (0.9, 0.5, 5.0), (0.5, 1.0, 2.0)];
    let order = prioritize_threats(&objects);
    assert_eq!(order[0], 1, "Highest threat should be first");
    assert_eq!(order[1], 2, "Medium threat second");
    assert_eq!(order[2], 0, "Lowest threat last");
}

// ═══════════════════════════════════════════════════════════════
// POWER: Domain logic bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn battery_remaining_exponential_model() {
    let remaining = battery_remaining_cycles(10000, 5000, 1.0);
    // Exponential: 10000 * exp(-0.001 * 5000 * 1.0) = 10000 * exp(-5) ≈ 67
    // Linear (bug): 10000 * (1 - 0.001 * 5000) = 10000 * (-4) = 0
    // At moderate cycles, linear overestimates; at high cycles, diverges
    let expected = (10000.0 * (-0.001 * 5000.0 * 1.0_f64).exp()) as u32;
    assert!((remaining as i32 - expected as i32).abs() < 100,
        "Expected exponential ~{expected}, got {remaining}");
}

#[test]
fn thermal_equilibrium_uses_fourth_root() {
    // T = (alpha * S / (epsilon * sigma))^(1/4)
    let temp = thermal_equilibrium_k(0.3, 1361.0, 0.9);
    // Correct: (0.3 * 1361 / (0.9 * 5.67e-8))^0.25 ≈ 254 K
    assert!(temp > 200.0 && temp < 300.0,
        "Equilibrium temp should be ~254 K, got {temp}");
}

#[test]
fn eclipse_battery_capacity_accounts_for_dod() {
    // Required capacity = P * t / (DoD * eta)
    // For 100W, 0.6h eclipse, 0.8 DoD, 0.95 efficiency:
    // C = 100 * 0.6 / (0.8 * 0.95) = 78.9 Wh
    let cap = eclipse_battery_capacity_wh(100.0, 0.6, 0.8, 0.95);
    let expected = 100.0 * 0.6 / (0.8 * 0.95);
    assert!((cap - expected).abs() < 1.0,
        "Expected ~{expected} Wh, got {cap}");
}

#[test]
fn solar_array_area_cosine_law() {
    // At 0° angle (sun directly overhead), area = P / (flux * eff)
    let area_0 = solar_array_area_m2(1000.0, 1361.0, 0.3, 0.001);
    // At 30° angle, area should be larger (1/cos(30°) = 1.155x)
    let area_30 = solar_array_area_m2(1000.0, 1361.0, 0.3, 30.0);
    let expected_30 = 1000.0 / (1361.0 * 0.3 * (30.0_f64).to_radians().cos());
    assert!((area_30 - expected_30).abs() < 0.1,
        "Expected ~{expected_30}, got {area_30}");
}

#[test]
fn power_margin_positive_when_excess() {
    // 200W available, 100W required → margin = 100%
    let margin = power_margin_pct(200.0, 100.0);
    assert!((margin - 100.0).abs() < 0.1, "Expected 100% margin, got {margin}");
}

#[test]
fn power_margin_negative_when_deficit() {
    // 80W available, 100W required → margin = -20%
    let margin = power_margin_pct(80.0, 100.0);
    assert!((margin - (-20.0)).abs() < 0.1, "Expected -20% margin, got {margin}");
}

// ═══════════════════════════════════════════════════════════════
// ROUTING: Domain logic bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn propagation_delay_geo_orbit() {
    // GEO distance ≈ 35786 km, one-way delay ≈ 119.4 ms
    let delay = propagation_delay_ms(35786.0);
    assert!((delay - 119.4).abs() < 1.0,
        "GEO propagation delay should be ~119.4 ms, got {delay}");
}

#[test]
fn multi_hop_latency_includes_all_processing() {
    // 3 hops at 1000km each, 5ms processing per hop
    // Propagation per hop = 1000/299792.458 * 1000 ≈ 3.34 ms
    // Total = 3 * 3.34 + 3 * 5 = 10.02 + 15 = 25.02 ms
    let latency = multi_hop_latency_ms(&[1000.0, 1000.0, 1000.0], 5.0);
    assert!((latency - 25.0).abs() < 1.0,
        "3-hop latency should be ~25ms, got {latency}");
}

#[test]
fn atmospheric_attenuation_decreases_with_elevation() {
    let atten_10 = atmospheric_attenuation_db(3.0, 10.0);
    let atten_45 = atmospheric_attenuation_db(3.0, 45.0);
    let atten_90 = atmospheric_attenuation_db(3.0, 90.0);
    assert!(atten_10 > atten_45, "Lower elevation should have more attenuation");
    assert!(atten_45 > atten_90, "Mid elevation should have more attenuation than zenith");
    assert!((atten_90 - 3.0).abs() < 0.1, "At zenith, attenuation = base: {atten_90}");
}

#[test]
fn eirp_subtracts_cable_loss() {
    // EIRP = 20 + 35 - 2 = 53 dBW
    let eirp = eirp_dbw(20.0, 35.0, 2.0);
    assert!((eirp - 53.0).abs() < 0.01, "EIRP should be 53 dBW, got {eirp}");
}

#[test]
fn carrier_to_noise_includes_g_over_t() {
    // C/N0 = EIRP - FSPL + G/T - k = 50 - 200 + 25 + 228.6 = 103.6
    let cn0 = carrier_to_noise_db_hz(50.0, 200.0, 25.0);
    assert!((cn0 - 103.6).abs() < 0.1, "C/N0 should be ~103.6, got {cn0}");
}

#[test]
fn select_best_antenna_by_gain() {
    let antennas = vec![
        ("low_gain".to_string(), 5.0, 2.0),
        ("high_gain".to_string(), 35.0, 12.0),
        ("mid_gain".to_string(), 15.0, 8.0),
    ];
    let best = select_best_antenna(&antennas).unwrap();
    assert_eq!(best, "high_gain", "Should select highest gain antenna, got {best}");
}

// ═══════════════════════════════════════════════════════════════
// SCHEDULING: Multi-step & integration bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn greedy_schedule_optimal_selection() {
    // Classic interval scheduling:
    // Contact 0: [1, 4, 1]  Contact 1: [3, 5, 1]  Contact 2: [0, 6, 1]
    // Contact 3: [5, 7, 1]  Contact 4: [8, 9, 1]  Contact 5: [5, 9, 1]
    // Optimal by end time: {0, 3, 4} = 3 contacts
    let contacts = vec![
        (1.0, 4.0, 1.0), (3.0, 5.0, 1.0), (0.0, 6.0, 1.0),
        (5.0, 7.0, 1.0), (8.0, 9.0, 1.0), (5.0, 9.0, 1.0),
    ];
    let selected = greedy_schedule(&contacts);
    assert_eq!(selected.len(), 3, "Optimal schedule should select 3 contacts, got {}", selected.len());
}

#[test]
fn ground_track_repeat_uses_solar_day() {
    // ISS-like: 15 revs per day → period = 86400/15 = 5760s
    let period = ground_track_repeat_period_s(15, 1);
    assert!((period - 5760.0).abs() < 1.0,
        "1-day repeat period should be 86400/15=5760s, got {period}");
}

#[test]
fn visibility_duration_full_arc() {
    // visibility should account for both ascending and descending arcs
    let dur = visibility_duration_s(60.0, 10.0, 0.5);
    // Full arc = 2 * arccos(cos(60)/cos(10)) / omega
    let expected = 2.0 * (60.0_f64.to_radians().cos() / 10.0_f64.to_radians().cos()).acos().to_degrees() / 0.5;
    assert!((dur - expected).abs() < 1.0, "Expected ~{expected}s, got {dur}s");
}

#[test]
fn find_conflicts_correct_overlap() {
    // [0,5] and [10,15] don't overlap
    // [0,5] and [3,8] overlap
    // [10,15] and [3,8] don't overlap
    let contacts = vec![(0.0, 5.0), (10.0, 15.0), (3.0, 8.0)];
    let conflicts = find_conflicts(&contacts);
    assert_eq!(conflicts.len(), 1, "Should find exactly 1 conflict, got {}", conflicts.len());
    assert!(conflicts.contains(&(0, 2)), "Conflict should be between 0 and 2");
}

#[test]
fn merge_by_priority_keeps_higher() {
    // Overlapping intervals: [0,10] prio=5 and [5,15] prio=10
    // Should keep priority 10 (higher)
    let intervals = vec![(0.0, 10.0, 5), (5.0, 15.0, 10)];
    let merged = merge_by_priority(&intervals);
    assert_eq!(merged.len(), 1);
    assert_eq!(merged[0].2, 10, "Should keep higher priority, got {}", merged[0].2);
}

// ═══════════════════════════════════════════════════════════════
// SEQUENCING: Multi-step & state machine bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn topological_sort_detects_cycle() {
    // A -> B -> C -> A (cycle)
    let deps = vec![vec![2], vec![0], vec![1]]; // 0 depends on 2, 1 on 0, 2 on 1
    let result = topological_sort_commands(3, &deps);
    assert!(result.is_none(), "Should detect cycle and return None");
}

#[test]
fn topological_sort_linear_chain() {
    // 0 -> 1 -> 2 (linear dependency)
    let deps = vec![vec![], vec![0], vec![1]];
    let result = topological_sort_commands(3, &deps).unwrap();
    assert_eq!(result.len(), 3);
    // 0 should come before 1, 1 before 2
    let pos_0 = result.iter().position(|&x| x == 0).unwrap();
    let pos_1 = result.iter().position(|&x| x == 1).unwrap();
    let pos_2 = result.iter().position(|&x| x == 2).unwrap();
    assert!(pos_0 < pos_1 && pos_1 < pos_2);
}

#[test]
fn coalesce_commands_includes_last_group() {
    let types = vec!["A", "A", "B", "B", "B", "C"];
    let groups = coalesce_commands(&types);
    assert_eq!(groups.len(), 3, "Should have 3 groups, got {}", groups.len());
    assert_eq!(groups[2], vec![5], "Last group should be [5]");
}

#[test]
fn coalesce_commands_single_type() {
    let types = vec!["A", "A", "A"];
    let groups = coalesce_commands(&types);
    assert_eq!(groups.len(), 1, "All same type = 1 group, got {}", groups.len());
    assert_eq!(groups[0].len(), 3);
}

#[test]
fn priority_insert_descending_order() {
    // Existing descending list: [100, 80, 60, 40, 20]
    // Insert 50 → should go at index 3
    let existing = vec![100i64, 80, 60, 40, 20];
    let idx = priority_insert_index(&existing, 50);
    assert_eq!(idx, 3, "Priority 50 should insert at index 3, got {idx}");
}

#[test]
fn throttle_respects_window_boundary() {
    // Commands at t=0, 5, 10, 15, 20. Window=10s, max=2 per window.
    let epochs = vec![0i64, 5, 10, 15, 20];
    let allowed = throttle_commands(&epochs, 10, 2);
    // With correct windowing: 0 OK, 5 OK (window [−10,0]→1), 10 depends on window
    assert!(allowed.len() >= 2, "Should allow at least 2 commands");
    // Check that we don't exceed rate limit
    for i in 0..allowed.len() {
        let epoch = epochs[allowed[i]];
        let count_in_window: usize = allowed[..=i]
            .iter()
            .filter(|&&j| epochs[j] > epoch - 10 && epochs[j] <= epoch)
            .count();
        assert!(count_in_window <= 2,
            "At epoch {epoch}, {count_in_window} cmds in window exceeds max 2");
    }
}

// ═══════════════════════════════════════════════════════════════
// TELEMETRY: Latent & domain logic bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn ema_responds_to_recent_values() {
    // High alpha = more weight on recent values
    let values = vec![0.0, 0.0, 0.0, 0.0, 100.0];
    let ema = exponential_moving_average(&values, 0.9);
    // With alpha=0.9, last EMA should be close to 100
    let last = *ema.last().unwrap();
    assert!(last > 80.0, "With alpha=0.9, EMA should respond quickly to 100, got {last}");
}

#[test]
fn ema_low_alpha_smooths() {
    let values = vec![0.0, 0.0, 0.0, 0.0, 100.0];
    let ema = exponential_moving_average(&values, 0.1);
    let last = *ema.last().unwrap();
    // With alpha=0.1, response should be slow
    assert!(last < 20.0, "With alpha=0.1, EMA should barely respond, got {last}");
}

#[test]
fn percentile_median_of_sorted() {
    let data = vec![10.0, 20.0, 30.0, 40.0, 50.0];
    let p50 = percentile(&data, 50.0);
    assert!((p50 - 30.0).abs() < 0.01, "Median of [10,20,30,40,50] should be 30, got {p50}");
}

#[test]
fn percentile_interpolation() {
    let data = vec![10.0, 20.0, 30.0, 40.0];
    let p25 = percentile(&data, 25.0);
    // rank = 0.25 * 3 = 0.75, interpolate between 10 and 20: 10*0.25 + 20*0.75 = 17.5
    assert!((p25 - 17.5).abs() < 0.01, "P25 should be 17.5, got {p25}");
}

#[test]
fn z_score_outliers_detects_extreme() {
    let values = vec![10.0, 10.0, 10.0, 10.0, 10.0, 100.0];
    let outliers = z_score_outliers(&values, 2.0);
    assert!(outliers.contains(&5), "100.0 should be detected as outlier");
}

#[test]
fn rate_of_change_positive_slope() {
    let values = vec![0.0, 1.0, 2.0, 3.0];
    let roc = rate_of_change(&values, 1.0);
    assert_eq!(roc.len(), 3);
    for r in &roc {
        assert!((r - 1.0).abs() < 0.01, "Rate of change should be 1.0, got {r}");
    }
}

#[test]
fn composite_health_weighted_correctly() {
    // Subsystem A: value=80, weight=3, range [0,100] → normalized = 0.8
    // Subsystem B: value=50, weight=1, range [0,100] → normalized = 0.5
    // Weighted: (0.8*3 + 0.5*1) / 4 = 2.9/4 = 0.725
    let subsystems = vec![(80.0, 3.0, 0.0, 100.0), (50.0, 1.0, 0.0, 100.0)];
    let score = composite_health_score(&subsystems);
    assert!((score - 0.725).abs() < 0.01,
        "Weighted composite score should be 0.725, got {score}");
}

// ═══════════════════════════════════════════════════════════════
// RESILIENCE: State machine bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn circuit_breaker_half_open_success_closes() {
    let next = circuit_breaker_next_state("half_open", false, false, true);
    assert_eq!(next, "closed", "Successful probe in half_open should close circuit, got {next}");
}

#[test]
fn circuit_breaker_half_open_failure_opens() {
    let next = circuit_breaker_next_state("half_open", false, false, false);
    assert_eq!(next, "open", "Failed probe in half_open should open circuit, got {next}");
}

#[test]
fn circuit_breaker_full_lifecycle() {
    // closed → open (failures) → half_open (cooldown) → closed (probe success)
    let s1 = circuit_breaker_next_state("closed", true, false, false);
    assert_eq!(s1, "open");
    let s2 = circuit_breaker_next_state(s1, false, true, false);
    assert_eq!(s2, "half_open");
    let s3 = circuit_breaker_next_state(s2, false, false, true);
    assert_eq!(s3, "closed", "Full lifecycle should return to closed, got {s3}");
}

#[test]
fn sliding_window_boundary_exclusion() {
    // Events at 90, 95, 100. Window=10, now=100.
    // Cutoff should be >90 (exclusive), so events at 95, 100 count = 2
    let events = vec![90u64, 95, 100];
    let allow = sliding_window_allow(&events, 100, 10, 3);
    assert!(allow, "2 events in window, limit 3, should allow");
    // With limit 2, exactly 2 events → should NOT allow (need strictly < max)
    let allow2 = sliding_window_allow(&events, 100, 10, 2);
    // The event at exactly the cutoff (90) should be excluded
    assert!(!allow2, "2 events in window, limit 2, should not allow more");
}

#[test]
fn backoff_with_jitter_always_increases() {
    // Backoff should always be >= base_ms regardless of jitter
    let b0 = backoff_with_jitter_ms(100, 0, 0.99);
    assert!(b0 >= 100, "Backoff at attempt 0 should be >= base, got {b0}");
    let b1 = backoff_with_jitter_ms(100, 1, 0.99);
    assert!(b1 >= 100, "Backoff at attempt 1 should be >= base, got {b1}");
}

#[test]
fn health_check_quorum_exact_match() {
    // 3 of 4 pass = 75%. Quorum = 0.75 → should be healthy
    let results = vec![true, true, true, false];
    let (healthy, ratio) = health_check_quorum(&results, 0.75);
    assert!(healthy, "75% pass rate meets 75% quorum, should be healthy");
    assert!((ratio - 0.75).abs() < 0.01);
}

#[test]
fn retry_budget_allows_when_error_rate_high() {
    // Should retry when error rate exceeds threshold (service is failing)
    let (should, remaining) = retry_budget(5, 2, 0.8, 0.5);
    assert!(should, "Should retry when error rate (0.8) > threshold (0.5)");
    assert_eq!(remaining, 3);
}

#[test]
fn retry_budget_blocks_when_healthy() {
    // Should not waste retries when service is healthy
    let (should, _) = retry_budget(5, 0, 0.01, 0.5);
    assert!(!should, "Should not retry when error rate (0.01) < threshold (0.5)");
}

// ═══════════════════════════════════════════════════════════════
// AUTH: Security & latent bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn validate_claims_checks_not_before() {
    // Token with nbf in the future should be invalid
    let valid = validate_claims(100, 200, 150, 120);
    // iat=100, exp=200, nbf=150, now=120
    // now >= iat (120>=100) ✓, now <= exp (120<=200) ✓, but now < nbf (120<150) ✗
    assert!(!valid, "Token should be invalid when now < nbf");
}

#[test]
fn validate_claims_happy_path() {
    let valid = validate_claims(100, 200, 50, 150);
    assert!(valid, "Token should be valid when iat<=now<=exp and nbf<=now");
}

#[test]
fn mfa_two_of_three_required() {
    let factors = vec![true, false, true];
    assert!(mfa_check(&factors, 2), "2 of 3 factors should satisfy requirement of 2");
}

#[test]
fn mfa_exact_match() {
    let factors = vec![true, true];
    assert!(mfa_check(&factors, 2), "Exactly meeting requirement should pass");
}

#[test]
fn rotate_key_advances() {
    assert_eq!(rotate_key_index(0, 3), 1, "Should advance from 0 to 1");
    assert_eq!(rotate_key_index(2, 3), 0, "Should wrap from 2 to 0");
}

#[test]
fn path_pattern_prefix_only() {
    // "/admin*" should match "/admin/users" but NOT "/not-admin/foo"
    assert!(path_matches_pattern("/admin/users", &["/admin*"]));
    assert!(!path_matches_pattern("/not-admin/foo", &["/admin*"]),
        "Prefix pattern should not match paths containing the prefix in the middle");
}

#[test]
fn compute_signature_key_dependent() {
    // Different keys with same message should produce different signatures
    let sig1 = compute_signature("key1", "message");
    let sig2 = compute_signature("key2", "message");
    // Also, swapping key and message should differ
    let sig3 = compute_signature("message", "key1");
    assert_ne!(sig1, sig2, "Different keys should produce different signatures");
    assert_ne!(sig1, sig3, "Swapping key/message should produce different signature");
}

// ═══════════════════════════════════════════════════════════════
// EVENTS: Concurrency & integration bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn correlate_events_window_chaining() {
    // Events at 0, 5, 10. Window=6.
    // 0 and 5 are within 6ms of each other → same group
    // 10 is within 6ms of 5 but NOT within 6ms of 0
    // Correct: two groups {0,5} and {10} (sliding window from first event)
    // OR three groups if using pairwise window
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 0, kind: "X".into(), payload: "".into() },
        SatEvent { id: "b".into(), timestamp: 5, kind: "X".into(), payload: "".into() },
        SatEvent { id: "c".into(), timestamp: 10, kind: "X".into(), payload: "".into() },
    ];
    let groups = correlate_events(&events, 6);
    // With fixed-window from group start: {0,5} (10-0=10 > 6) then {10}
    assert_eq!(groups.len(), 2, "Should have 2 groups, got {}", groups.len());
}

#[test]
fn causal_ordering_same_timestamp_violation() {
    // Parent and child at same timestamp violates causality (should be strictly before)
    let events = vec![
        ("parent".to_string(), 100u64, None),
        ("child".to_string(), 100u64, Some("parent".to_string())),
    ];
    let ordered = is_causally_ordered(&events);
    assert!(!ordered, "Same timestamp as parent should violate causal ordering");
}

#[test]
fn causal_ordering_valid_chain() {
    let events = vec![
        ("a".to_string(), 100u64, None),
        ("b".to_string(), 200u64, Some("a".to_string())),
        ("c".to_string(), 300u64, Some("b".to_string())),
    ];
    assert!(is_causally_ordered(&events));
}

#[test]
fn dedup_within_window_allows_after_window() {
    let events = vec![
        SatEvent { id: "x".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        SatEvent { id: "x".into(), timestamp: 150, kind: "A".into(), payload: "".into() },
        SatEvent { id: "x".into(), timestamp: 200, kind: "A".into(), payload: "".into() },
    ];
    // Window = 100ms. First at 100, second at 150 (within window, suppressed),
    // third at 200 (200-100 = 100 = exactly at boundary, should be allowed)
    let result = dedup_within_window(&events, 100);
    assert_eq!(result.len(), 2, "Should keep first and third (at window boundary), got {}", result.len());
}

#[test]
fn event_throughput_uniform_distribution() {
    // 10 events evenly distributed, bucket_size=10
    let timestamps: Vec<u64> = (0..10).map(|i| i * 10).collect();
    let buckets = event_throughput_buckets(&timestamps, 10);
    // Each bucket should have exactly 1 event
    for (i, &count) in buckets.iter().enumerate() {
        assert_eq!(count, 1, "Bucket {i} should have 1 event, got {count}");
    }
}

// ═══════════════════════════════════════════════════════════════
// CONCURRENCY: Thread safety bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn telemetry_counter_concurrent_accuracy() {
    use std::sync::Arc;
    use std::thread;

    let counter = Arc::new(TelemetryCounter::new());
    let mut handles = vec![];

    for _ in 0..10 {
        let c = Arc::clone(&counter);
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                c.record(10);
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(counter.count(), 10000, "Should have exactly 10000 records");
    assert!((counter.average() - 10.0).abs() < 0.01,
        "Average should be 10.0, got {}", counter.average());
}

#[test]
fn command_queue_priority_ordering() {
    let queue = CommandQueue::new(10);
    queue.enqueue("low".to_string(), 1);
    queue.enqueue("high".to_string(), 100);
    queue.enqueue("mid".to_string(), 50);

    // Dequeue should return highest priority first
    let first = queue.dequeue().unwrap();
    assert_eq!(first.0, "high", "Should dequeue highest priority first, got {}", first.0);
    let second = queue.dequeue().unwrap();
    assert_eq!(second.0, "mid", "Should dequeue mid priority second, got {}", second.0);
}

#[test]
fn command_queue_capacity_limit() {
    let queue = CommandQueue::new(2);
    assert!(queue.enqueue("a".to_string(), 1));
    assert!(queue.enqueue("b".to_string(), 2));
    assert!(!queue.enqueue("c".to_string(), 3), "Should reject when at capacity");
}

#[test]
fn satellite_state_mode_transition() {
    let state = SatelliteState::new();
    assert_eq!(state.get_mode(), "nominal");

    // Fail a subsystem → should transition to safe mode
    state.set_subsystem("power", false);
    state.update_mode();
    assert_eq!(state.get_mode(), "safe");

    // Recover subsystem → should transition back to nominal
    state.set_subsystem("power", true);
    state.update_mode();
    assert_eq!(state.get_mode(), "nominal");
}

#[test]
fn token_bucket_refill_rate() {
    let bucket = TokenBucket::new(10.0, 1.0); // 1 token per second
    // Consume all tokens
    for _ in 0..10 {
        assert!(bucket.try_consume(0));
    }
    assert!(!bucket.try_consume(0), "Should be empty");

    // After 5 seconds, should have ~5 tokens
    assert!(bucket.try_consume(5000)); // 5000ms = 5s
    let tokens = bucket.available_tokens();
    assert!(tokens > 3.0 && tokens < 6.0,
        "After 5s refill at 1/s, should have ~4 tokens, got {tokens}");
}

// ═══════════════════════════════════════════════════════════════
// INTEGRATION: Cross-module pipeline bugs
// ═══════════════════════════════════════════════════════════════

#[test]
fn conjunction_pipeline_unit_consistency() {
    // Two satellites at 400km and 410km, miss distance 1km
    let (threat, action) = integration::conjunction_assessment_pipeline(400.0, 410.0, 1.0, 0.9);
    // With correct velocity computation, relative velocity should be small
    // and threat should be low for 1km miss distance
    assert!(threat <= 2, "Low relative velocity at similar altitudes should give low threat, got {threat}");
}

#[test]
fn power_aware_contact_rejects_low_power() {
    // Very low battery, no solar, high comms power → should reject
    let feasible = integration::power_aware_contact_feasible(
        0.0, 600.0, 0.0, 5.0, 100.0, 50.0,
    );
    assert!(!feasible, "Should reject contact with no solar and 5% SOC");
}

#[test]
fn orbit_maintenance_small_correction_valid() {
    // Small correction: 0.5km altitude, 0.1° inclination
    let (stable, dv, plan_valid) = integration::orbit_maintenance_check(
        400.0, 53.0, 1.0, 400.5, 53.1,
    );
    assert!(stable, "Within station-keeping bounds");
    assert!(dv < 120.0, "Small correction should have dv < 120 m/s, got {dv}");
    assert!(plan_valid, "Small correction burn plan should be valid, got dv={dv}");
}

#[test]
fn telemetry_mode_healthy_satellite() {
    // Good telemetry → nominal mode
    let mode = integration::telemetry_mode_decision(90.0, 25.0, 0.5);
    assert_eq!(mode, "nominal", "Healthy satellite should be in nominal mode, got {mode}");
}

#[test]
fn should_execute_pass_all_conditions_met() {
    let (execute, reason) = integration::should_execute_pass(45.0, 10.0, 0.8, "observer");
    assert!(execute, "All conditions met, should execute pass. Reason: {reason}");
}

#[test]
fn should_execute_pass_low_power_blocks() {
    let (execute, reason) = integration::should_execute_pass(45.0, 10.0, 0.05, "observer");
    assert!(!execute, "Low power should block pass execution");
    assert_eq!(reason, "low_power");
}

#[test]
fn plan_downlink_auth_for_operator() {
    let stations = vec![("station_a".to_string(), 30.0), ("station_b".to_string(), 50.0)];
    let result = integration::plan_downlink(&stations, "flight_operator", 20.0, 35.0);
    assert!(result.is_some());
    let (_, _, authorized) = result.unwrap();
    // flight_operator should be able to downlink data
    assert!(authorized, "Flight operator should be authorized for downlink");
}

// ═══════════════════════════════════════════════════════════════
// MULTI-STEP: Bugs that chain together
// ═══════════════════════════════════════════════════════════════

#[test]
fn orbit_to_safety_pipeline_velocity_units() {
    // orbit::velocity_at_altitude returns km/s
    // This test verifies the velocity feeds correctly into safety functions
    let v = velocity_at_altitude(400.0);
    // v should be ~7.67 km/s
    assert!(v > 7.0 && v < 8.0, "Velocity should be ~7.67 km/s, got {v}");

    // Now use in collision assessment — the relative_velocity function
    // should give |v1 - v2| in km/s
    let v2 = velocity_at_altitude(410.0);
    let rel = aerolith::orbit::relative_velocity(v, v2);
    assert!(rel < 1.0, "Small altitude difference → small relative v, got {rel}");
}

#[test]
fn scheduling_power_chain() {
    // Schedule a contact, then check power feasibility
    let window_end = contact_window_end(1000.0, 600.0);
    assert!((window_end - 1600.0).abs() < 1.0, "Contact window end should be 1600");

    let solar = solar_panel_output_watts(100.0, 0.0);
    let soc = battery_soc(50.0, 100.0);
    let budget = power_budget_watts(solar, 80.0);

    // Power budget should be positive (solar > consumption)
    assert!(budget > 0.0, "Power budget should be positive: solar={solar}, budget={budget}");
    assert!((soc - 0.5).abs() < 0.01, "SOC should be 0.5");
}

#[test]
fn event_sort_then_dedup_consistency() {
    // Sort events, then dedup — should preserve earliest occurrence
    let events = vec![
        SatEvent { id: "a".into(), timestamp: 300, kind: "X".into(), payload: "late".into() },
        SatEvent { id: "a".into(), timestamp: 100, kind: "X".into(), payload: "early".into() },
        SatEvent { id: "b".into(), timestamp: 200, kind: "Y".into(), payload: "only".into() },
    ];
    let sorted = sort_events_by_time(&events);
    let deduped = dedup_events(&sorted);
    assert_eq!(deduped.len(), 2);
    let a_event = deduped.iter().find(|e| e.id == "a").unwrap();
    assert_eq!(a_event.payload, "early", "Should keep earliest 'a' event");
}

#[test]
fn auth_then_scheduling_integration() {
    // Verify authorization before scheduling a pass
    let authorized = aerolith::auth::authorize_command("flight_operator", "cluster", "read_telemetry");
    assert!(authorized, "Operator should be able to read telemetry");

    let visible = aerolith::routing::ground_station_visible(15.0, 10.0);
    assert!(visible, "Station should be visible at 15° elevation");

    let los = aerolith::routing::is_line_of_sight(15.0);
    assert!(los, "Should have line of sight at positive elevation");

    let mode = power_mode(0.6);
    assert_eq!(mode, "normal", "SOC 0.6 should be normal mode");
}

// ═══════════════════════════════════════════════════════════════
// ORBIT: Complex domain logic (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn nodal_precession_period_iss_orbit() {
    // ISS-like: sma ~ 6778 km, inc 51.6°
    // RAAN drift ~-5 deg/day → precession period ~72 days
    let period = nodal_precession_period_days(6778.0, 51.6);
    assert!(period.abs() > 50.0 && period.abs() < 100.0,
        "ISS nodal precession should be ~72 days, got {period}");
}

#[test]
fn nodal_precession_chains_raan_drift_sign() {
    // For prograde orbits, RAAN drift is negative, so precession period should be negative
    // (or we take abs). The key is that this function chains through j2_raan_drift.
    let period_prograde = nodal_precession_period_days(7000.0, 45.0);
    let period_retro = nodal_precession_period_days(7000.0, 135.0);
    // Prograde: negative drift → negative period; retrograde: positive drift → positive period
    assert!(period_prograde < 0.0 || period_retro > 0.0,
        "Should distinguish prograde vs retrograde precession direction");
}

#[test]
fn argument_of_latitude_wraps_correctly() {
    // 350° + 20° = 370° → should wrap to 10°
    let ta = 350.0_f64.to_radians();
    let omega = 20.0_f64.to_radians();
    let u = argument_of_latitude(ta, omega);
    assert!(u >= 0.0, "Argument of latitude should be non-negative, got {u}");
    assert!(u < std::f64::consts::TAU, "Should be < 2π, got {u}");
    let expected = 10.0_f64.to_radians();
    assert!((u - expected).abs() < 0.01, "Expected ~{expected} rad, got {u}");
}

#[test]
fn argument_of_latitude_negative_input() {
    // Negative true anomaly (from perturbation) should still give valid result
    let u = argument_of_latitude(-0.5, 1.0);
    assert!(u >= 0.0, "Should handle negative input, got {u}");
}

#[test]
fn atmospheric_density_decreases_with_altitude() {
    let rho_300 = atmospheric_density_kg_m3(300.0);
    let rho_400 = atmospheric_density_kg_m3(400.0);
    let rho_500 = atmospheric_density_kg_m3(500.0);
    assert!(rho_300 > rho_400, "Density should decrease: 300km ({rho_300}) > 400km ({rho_400})");
    assert!(rho_400 > rho_500, "Density should decrease: 400km ({rho_400}) > 500km ({rho_500})");
}

#[test]
fn atmospheric_density_continuity_at_400km() {
    // Density should be continuous at the altitude band boundary
    let rho_399 = atmospheric_density_kg_m3(399.0);
    let rho_401 = atmospheric_density_kg_m3(401.0);
    let ratio = rho_399 / rho_401;
    assert!(ratio > 0.5 && ratio < 2.0,
        "Density should be continuous at 400km: {rho_399} vs {rho_401} (ratio {ratio})");
}

#[test]
fn atmospheric_density_realistic_at_500km() {
    // At 500 km, density is typically ~1e-12 to ~5e-13 kg/m³
    let rho = atmospheric_density_kg_m3(500.0);
    assert!(rho > 1e-14 && rho < 1e-11,
        "Density at 500km should be ~1e-12 kg/m³, got {rho}");
}

#[test]
fn drag_decay_rate_negative_at_low_orbit() {
    // Drag causes orbit to decay (altitude decreases), so rate should be negative
    let rate = drag_decay_rate(350.0, 100.0);
    assert!(rate < 0.0, "Drag decay should be negative (altitude loss), got {rate}");
}

#[test]
fn drag_decay_rate_stronger_at_lower_altitude() {
    let rate_300 = drag_decay_rate(300.0, 100.0).abs();
    let rate_500 = drag_decay_rate(500.0, 100.0).abs();
    assert!(rate_300 > rate_500,
        "Decay should be faster at 300km ({rate_300}) than 500km ({rate_500})");
}

// ═══════════════════════════════════════════════════════════════
// SAFETY: Complex domain logic (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn mahalanobis_distance_unit_covariance() {
    // With unit covariance (sigma=1, so variance=1), should equal Euclidean distance
    let d = mahalanobis_distance(3.0, 4.0, 0.0, 1.0, 1.0, 1.0);
    assert!((d - 5.0).abs() < 0.01, "With unit covariance, should equal Euclidean: got {d}");
}

#[test]
fn mahalanobis_distance_scales_with_covariance() {
    // Larger covariance → smaller Mahalanobis distance (miss is less significant)
    let d_small_cov = mahalanobis_distance(1.0, 1.0, 1.0, 0.01, 0.01, 0.01);
    let d_large_cov = mahalanobis_distance(1.0, 1.0, 1.0, 100.0, 100.0, 100.0);
    assert!(d_small_cov > d_large_cov,
        "Smaller covariance should give larger Mahalanobis distance");
}

#[test]
fn maneuver_feasibility_sufficient_fuel() {
    // 50 kg fuel, 100 kg max, small delta-v, good Isp
    let (feasible, remaining) = maneuver_feasibility(50.0, 100.0, 10.0, 300.0);
    assert!(feasible, "Should be feasible with plenty of fuel");
    assert!(remaining > 0.0, "Should have fuel remaining");
}

#[test]
fn maneuver_feasibility_insufficient_fuel() {
    // Very little fuel, huge delta-v requirement
    let (feasible, _) = maneuver_feasibility(1.0, 100.0, 5000.0, 300.0);
    assert!(!feasible, "Should not be feasible with 1kg fuel for 5km/s delta-v");
}

#[test]
fn maneuver_feasibility_reserves_margin() {
    // The function should reserve 15% of fuel, so usable = 85%
    // Edge case: just enough fuel before margin, not enough after
    let (_, remaining_full) = maneuver_feasibility(100.0, 100.0, 1.0, 300.0);
    assert!(remaining_full < 100.0, "Should account for margin, not show 100% remaining");
}

// ═══════════════════════════════════════════════════════════════
// POWER: Complex domain logic (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn end_of_life_power_3_percent_degradation() {
    // 1000W BOL, 3% annual degradation, 15 years
    // P_eol = 1000 * (1 - 0.03)^15 = 1000 * 0.97^15 ≈ 633 W
    let eol = end_of_life_power(1000.0, 15.0, 3.0);
    let expected = 1000.0 * 0.97_f64.powf(15.0);
    assert!((eol - expected).abs() < 10.0,
        "Expected ~{expected}W after 15yr at 3%/yr, got {eol}");
}

#[test]
fn end_of_life_power_zero_years_equals_bol() {
    let eol = end_of_life_power(500.0, 0.0, 5.0);
    assert!((eol - 500.0).abs() < 0.01,
        "Zero mission years should return BOL power, got {eol}");
}

#[test]
fn end_of_life_power_small_degradation_bounds() {
    // 2% degradation for 10 years should give ~82% of BOL
    let eol = end_of_life_power(1000.0, 10.0, 2.0);
    assert!(eol > 700.0 && eol < 900.0,
        "10yr at 2%/yr should be 800-820W, got {eol}");
}

#[test]
fn charge_discharge_profile_sums_to_orbit_period() {
    let (charge_h, discharge_h) = charge_discharge_profile(1.5, 0.35, 0.92, 0.95);
    let total = charge_h + discharge_h;
    assert!((total - 1.5).abs() < 0.01,
        "Charge + discharge should equal orbit period: {total}");
}

#[test]
fn charge_discharge_profile_eclipse_fraction() {
    let (charge_h, discharge_h) = charge_discharge_profile(1.5, 0.4, 0.9, 0.9);
    assert!((discharge_h - 0.6).abs() < 0.01, "40% eclipse of 1.5h = 0.6h, got {discharge_h}");
    assert!((charge_h - 0.9).abs() < 0.01, "60% sunlit of 1.5h = 0.9h, got {charge_h}");
}

// ═══════════════════════════════════════════════════════════════
// ROUTING: Integration chain bugs (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn complete_link_budget_positive_margin_close_range() {
    // High power, close range, good antennas → should have positive margin
    let (margin, rate) = complete_link_budget(
        30.0,   // tx_power_dbw
        40.0,   // tx_antenna_gain
        1.5,    // cable_loss
        1000.0, // distance_km (LEO)
        12.0,   // freq_ghz
        30.0,   // rx_antenna_gain
        300.0,  // rx_noise_temp_k
        10.0,   // required_eb_n0
    );
    assert!(margin > 0.0, "Close-range LEO link should have positive margin, got {margin}");
    assert!(rate > 0.0, "Should achieve positive data rate, got {rate}");
}

#[test]
fn complete_link_budget_margin_decreases_with_distance() {
    let (margin_near, _) = complete_link_budget(20.0, 30.0, 1.0, 500.0, 12.0, 25.0, 300.0, 10.0);
    let (margin_far, _) = complete_link_budget(20.0, 30.0, 1.0, 5000.0, 12.0, 25.0, 300.0, 10.0);
    assert!(margin_near > margin_far,
        "Closer range should give better margin: {margin_near} vs {margin_far}");
}

#[test]
fn inter_satellite_link_delay_speed_of_light() {
    // 1000km between satellites → delay = 1000/299792.458*1000 ≈ 3.34ms
    let (delay, _bw) = inter_satellite_link(1000.0, 10.0, 60.0);
    assert!((delay - 3.34).abs() < 0.5,
        "1000km ISL delay should be ~3.34ms, got {delay}");
}

#[test]
fn inter_satellite_link_bandwidth_decreases_with_distance() {
    let (_, bw_near) = inter_satellite_link(500.0, 10.0, 60.0);
    let (_, bw_far) = inter_satellite_link(5000.0, 10.0, 60.0);
    assert!(bw_near > bw_far,
        "Bandwidth should decrease with distance: {bw_near} vs {bw_far}");
}

// ═══════════════════════════════════════════════════════════════
// SCHEDULING: Complex DP bugs (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn weighted_schedule_non_overlapping_selects_all() {
    // All passes are non-overlapping → should select all
    let passes = vec![
        (1, 0.0, 10.0, 45.0),
        (2, 20.0, 30.0, 60.0),
        (3, 40.0, 50.0, 30.0),
    ];
    let selected = weighted_schedule(&passes);
    assert_eq!(selected.len(), 3, "All non-overlapping should be selected, got {}", selected.len());
}

#[test]
fn weighted_schedule_overlapping_picks_longer() {
    // Two overlapping passes: one short high-elev, one long
    // Should pick the one that maximizes total contact time
    let passes = vec![
        (1, 0.0, 100.0, 30.0),  // 100s duration
        (2, 50.0, 60.0, 80.0),  // 10s duration, overlaps
    ];
    let selected = weighted_schedule(&passes);
    // Should not include both (they overlap)
    let sel_starts: Vec<f64> = selected.iter().map(|&i| passes[i].1).collect();
    for i in 0..sel_starts.len() {
        for j in (i+1)..sel_starts.len() {
            let si = selected[i];
            let sj = selected[j];
            assert!(passes[si].2 <= passes[sj].1 || passes[sj].2 <= passes[si].1,
                "Selected passes should not overlap: {:?} and {:?}",
                passes[si], passes[sj]);
        }
    }
}

#[test]
fn weighted_schedule_classic_problem() {
    // Classic weighted interval scheduling:
    // Pass 0: [0, 6] duration=6   Pass 1: [1, 4] duration=3
    // Pass 2: [5, 7] duration=2   Pass 3: [3, 5] duration=2
    // Optimal: {1, 3, 2} = duration 7, or {0} = duration 6
    // So optimal is {1, 3, 2} with total duration 7
    let passes = vec![
        (10, 0.0, 6.0, 45.0),
        (20, 1.0, 4.0, 50.0),
        (30, 5.0, 7.0, 60.0),
        (40, 3.0, 5.0, 55.0),
    ];
    let selected = weighted_schedule(&passes);
    let total_duration: f64 = selected.iter().map(|&i| passes[i].2 - passes[i].1).sum();
    assert!(total_duration >= 6.0,
        "Should achieve at least 6s total contact, got {total_duration}");
}

// ═══════════════════════════════════════════════════════════════
// SEQUENCING: Complex dependency bugs (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn build_execution_plan_respects_dependencies() {
    let commands = vec![
        ("deploy".to_string(), 10, vec![]),       // 0: no deps
        ("configure".to_string(), 5, vec![0]),     // 1: depends on 0
        ("verify".to_string(), 3, vec![1]),        // 2: depends on 1
    ];
    let plan = build_execution_plan(&commands);
    assert_eq!(plan.len(), 3, "Should include all commands");
    let pos_0 = plan.iter().position(|&x| x == 0).unwrap();
    let pos_1 = plan.iter().position(|&x| x == 1).unwrap();
    let pos_2 = plan.iter().position(|&x| x == 2).unwrap();
    assert!(pos_0 < pos_1, "deploy must come before configure");
    assert!(pos_1 < pos_2, "configure must come before verify");
}

#[test]
fn build_execution_plan_prefers_higher_priority() {
    // Two independent commands with different priorities
    let commands = vec![
        ("low_prio".to_string(), 1, vec![]),
        ("high_prio".to_string(), 100, vec![]),
    ];
    let plan = build_execution_plan(&commands);
    assert_eq!(plan.len(), 2);
    assert_eq!(plan[0], 1, "Higher priority should execute first");
}

#[test]
fn build_execution_plan_handles_cycle() {
    // Cycle: 0 → 1 → 2 → 0
    let commands = vec![
        ("a".to_string(), 1, vec![2]),
        ("b".to_string(), 2, vec![0]),
        ("c".to_string(), 3, vec![1]),
    ];
    let plan = build_execution_plan(&commands);
    // With a cycle, the function should return empty or handle gracefully
    // The topological_sort_commands bug means it doesn't detect cycles
    assert!(plan.is_empty(), "Cyclic dependencies should return empty plan");
}

// ═══════════════════════════════════════════════════════════════
// TELEMETRY: Advanced analysis (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn mad_anomaly_detects_spike() {
    let history = vec![10.0, 10.1, 9.9, 10.0, 10.2, 9.8, 10.1, 9.9];
    let (is_anom, severity) = mad_anomaly_detection(&history, 50.0);
    assert!(is_anom, "50.0 should be anomalous given history around 10");
    assert!(severity > 0.5, "Severity should be high, got {severity}");
}

#[test]
fn mad_anomaly_normal_value_passes() {
    let history = vec![10.0, 10.1, 9.9, 10.0, 10.2, 9.8, 10.1, 9.9];
    let (is_anom, severity) = mad_anomaly_detection(&history, 10.05);
    assert!(!is_anom, "10.05 should not be anomalous given history around 10");
    assert!(severity < 0.5, "Severity should be low, got {severity}");
}

#[test]
fn pearson_correlation_perfect_positive() {
    let x = vec![1.0, 2.0, 3.0, 4.0, 5.0];
    let y = vec![2.0, 4.0, 6.0, 8.0, 10.0];
    let r = pearson_correlation(&x, &y);
    assert!((r - 1.0).abs() < 0.001, "Perfect positive correlation should give r=1, got {r}");
}

#[test]
fn pearson_correlation_perfect_negative() {
    let x = vec![1.0, 2.0, 3.0, 4.0, 5.0];
    let y = vec![10.0, 8.0, 6.0, 4.0, 2.0];
    let r = pearson_correlation(&x, &y);
    assert!((r - (-1.0)).abs() < 0.001, "Perfect negative correlation should give r=-1, got {r}");
}

#[test]
fn pearson_correlation_uncorrelated() {
    let x = vec![1.0, 2.0, 3.0, 4.0, 5.0];
    let y = vec![3.0, 1.0, 4.0, 1.0, 5.0]; // approximately random
    let r = pearson_correlation(&x, &y);
    assert!(r.abs() < 0.8, "Weakly correlated data should give low |r|, got {r}");
}

// ═══════════════════════════════════════════════════════════════
// RESILIENCE: Complex state & timing (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn adaptive_timeout_p99_latency() {
    // Latencies: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    // P99 should be near 100ms → timeout ≈ 150ms (1.5x safety)
    let latencies: Vec<u64> = (1..=10).map(|i| i * 10).collect();
    let timeout = adaptive_timeout_ms(&latencies, 99.0, 50, 5000);
    assert!(timeout > 100 && timeout < 300,
        "P99 timeout for [10..100] should be ~150ms, got {timeout}");
}

#[test]
fn adaptive_timeout_respects_bounds() {
    let latencies = vec![1, 2, 3, 4, 5];
    let timeout = adaptive_timeout_ms(&latencies, 50.0, 100, 500);
    assert!(timeout >= 100, "Should respect min_timeout, got {timeout}");

    let high_latencies = vec![1000, 2000, 3000];
    let timeout_high = adaptive_timeout_ms(&high_latencies, 90.0, 100, 500);
    assert!(timeout_high <= 500, "Should respect max_timeout, got {timeout_high}");
}

#[test]
fn load_shedding_below_threshold() {
    let (shed, cutoff) = load_shedding(50.0, 100.0, &[1, 2, 3, 4, 5]);
    assert!(!shed, "Below 80% utilization should not shed, got shed={shed}");
    assert_eq!(cutoff, 0);
}

#[test]
fn load_shedding_at_overload() {
    let (shed, cutoff) = load_shedding(95.0, 100.0, &[1, 2, 3, 4, 5]);
    assert!(shed, "95% utilization should trigger shedding");
    assert!(cutoff > 0, "Should set a priority cutoff, got {cutoff}");
}

#[test]
fn bulkhead_assign_picks_most_available() {
    let caps = vec![10, 10, 10];
    let usage = vec![8, 3, 6];
    let assigned = bulkhead_assign(&caps, &usage);
    assert_eq!(assigned, Some(1), "Should assign to partition 1 (most available), got {assigned:?}");
}

#[test]
fn bulkhead_assign_all_full() {
    let caps = vec![5, 5, 5];
    let usage = vec![5, 5, 5];
    let assigned = bulkhead_assign(&caps, &usage);
    assert_eq!(assigned, None, "All full partitions should return None");
}

// ═══════════════════════════════════════════════════════════════
// AUTH: Complex RBAC & lockout (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn evaluate_rbac_admin_can_do_anything() {
    let result = evaluate_rbac("admin", "admin", &[], &[]);
    assert!(result, "Admin role should be able to perform admin actions");
}

#[test]
fn evaluate_rbac_observer_cannot_admin() {
    let result = evaluate_rbac("observer", "admin", &[], &[]);
    assert!(!result, "Observer should not be able to perform admin actions");
}

#[test]
fn evaluate_rbac_explicit_denial_overrides() {
    let grants = vec![("operator", "deploy")];
    let denials = vec![("operator", "deploy")];
    let result = evaluate_rbac("operator", "deploy", &grants, &denials);
    assert!(!result, "Explicit denial should override explicit grant");
}

#[test]
fn evaluate_rbac_explicit_grant() {
    let grants = vec![("observer", "deploy")];
    let result = evaluate_rbac("observer", "deploy", &grants, &[]);
    assert!(result, "Explicit grant should allow the action");
}

#[test]
fn evaluate_rbac_hierarchy_operator_reads() {
    // Operator (level 2) should be able to read (action level 1)
    let result = evaluate_rbac("operator", "read", &[], &[]);
    assert!(result, "Operator should be able to read");
}

#[test]
fn progressive_lockout_allows_initial() {
    let failures: Vec<u64> = vec![];
    let (allowed, _) = progressive_lockout(&failures, 1000, 300, 5);
    assert!(allowed, "No failures should allow access");
}

#[test]
fn progressive_lockout_blocks_after_threshold() {
    // 6 failures in the last 60 seconds, threshold is 5
    let failures = vec![940, 945, 950, 955, 960, 965];
    let (allowed, remaining) = progressive_lockout(&failures, 1000, 300, 5);
    assert!(!allowed, "Should be locked out after 6 failures (threshold 5)");
    assert!(remaining > 0, "Should have lockout remaining");
}

#[test]
fn progressive_lockout_old_failures_ignored() {
    // Failures are old (outside window)
    let failures = vec![100, 200, 300, 400, 500, 600];
    let (allowed, _) = progressive_lockout(&failures, 10000, 300, 5);
    assert!(allowed, "Old failures outside window should be ignored");
}

// ═══════════════════════════════════════════════════════════════
// EVENTS: Complex pattern detection (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn detect_event_pattern_simple_abc() {
    let events = vec![
        SatEvent { id: "1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        SatEvent { id: "2".into(), timestamp: 200, kind: "B".into(), payload: "".into() },
        SatEvent { id: "3".into(), timestamp: 300, kind: "C".into(), payload: "".into() },
    ];
    let pattern = vec!["A", "B", "C"];
    let completions = detect_event_pattern(&events, &pattern, 500);
    assert!(!completions.is_empty(), "Should detect A→B→C pattern");
    assert!(completions.contains(&2), "Completion should be at event 2 (the C event)");
}

#[test]
fn detect_event_pattern_outside_window() {
    let events = vec![
        SatEvent { id: "1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        SatEvent { id: "2".into(), timestamp: 200, kind: "B".into(), payload: "".into() },
        SatEvent { id: "3".into(), timestamp: 900, kind: "C".into(), payload: "".into() },
    ];
    let pattern = vec!["A", "B", "C"];
    let completions = detect_event_pattern(&events, &pattern, 500);
    // A at 100, C at 900 → 800ms gap > 500ms window → should not match
    assert!(completions.is_empty(),
        "Pattern outside time window should not match");
}

#[test]
fn detect_event_pattern_multiple_completions() {
    let events = vec![
        SatEvent { id: "1".into(), timestamp: 100, kind: "A".into(), payload: "".into() },
        SatEvent { id: "2".into(), timestamp: 200, kind: "B".into(), payload: "".into() },
        SatEvent { id: "3".into(), timestamp: 300, kind: "C".into(), payload: "".into() },
        SatEvent { id: "4".into(), timestamp: 400, kind: "A".into(), payload: "".into() },
        SatEvent { id: "5".into(), timestamp: 500, kind: "B".into(), payload: "".into() },
        SatEvent { id: "6".into(), timestamp: 600, kind: "C".into(), payload: "".into() },
    ];
    let completions = detect_event_pattern(&events, &["A", "B", "C"], 500);
    assert!(completions.len() >= 2,
        "Should detect at least 2 A→B→C patterns, got {}", completions.len());
}

#[test]
fn join_event_streams_correlates_by_satellite() {
    let stream_a = vec![
        SatEvent { id: "1".into(), timestamp: 100, kind: "telemetry".into(), payload: "SAT1_temp=25".into() },
        SatEvent { id: "2".into(), timestamp: 200, kind: "telemetry".into(), payload: "SAT2_temp=30".into() },
    ];
    let stream_b = vec![
        SatEvent { id: "3".into(), timestamp: 110, kind: "command".into(), payload: "SAT1_adjust".into() },
        SatEvent { id: "4".into(), timestamp: 210, kind: "command".into(), payload: "SAT3_adjust".into() },
    ];
    let pairs = join_event_streams(&stream_a, &stream_b, 50);
    // SAT1 events should correlate (same satellite prefix, within window)
    assert!(!pairs.is_empty(), "Should find at least one correlated pair");
    assert!(pairs.contains(&(0, 0)), "SAT1 telemetry and SAT1 command should correlate");
}

#[test]
fn join_event_streams_respects_time_window() {
    let stream_a = vec![
        SatEvent { id: "1".into(), timestamp: 100, kind: "X".into(), payload: "SAT1_data".into() },
    ];
    let stream_b = vec![
        SatEvent { id: "2".into(), timestamp: 500, kind: "Y".into(), payload: "SAT1_data".into() },
    ];
    let pairs = join_event_streams(&stream_a, &stream_b, 50);
    assert!(pairs.is_empty(), "Events 400ms apart should not correlate with 50ms window");
}

// ═══════════════════════════════════════════════════════════════
// INTEGRATION: Complex cross-module pipelines (new functions)
// ═══════════════════════════════════════════════════════════════

#[test]
fn predict_orbit_evolution_altitude_decreases() {
    // Over time, drag causes altitude to decrease (at LEO)
    let (new_alt, _, _) = integration::predict_orbit_evolution(400.0, 51.6, 30.0);
    assert!(new_alt < 400.0,
        "Orbit should decay over 30 days at 400km, got new alt = {new_alt}");
}

#[test]
fn predict_orbit_evolution_period_realistic() {
    let (_, _, period_min) = integration::predict_orbit_evolution(400.0, 51.6, 0.0);
    // ISS period is ~92 minutes
    assert!(period_min > 85.0 && period_min < 100.0,
        "400km orbit period should be ~92 min, got {period_min}");
}

#[test]
fn predict_orbit_evolution_raan_shift_nonzero() {
    let (_, raan_shift, _) = integration::predict_orbit_evolution(400.0, 51.6, 10.0);
    assert!(raan_shift.abs() > 0.1,
        "RAAN should shift noticeably over 10 days, got {raan_shift}");
}

#[test]
fn full_conjunction_response_close_approach() {
    // Threat very close, moving fast → should trigger maneuver response
    let (response, tca) = integration::full_conjunction_response(
        (7000.0, 0.0, 0.0),   // own position
        (7001.0, 0.0, 0.0),   // threat 1km away in X
        (-5.0, 0.0, 0.0),     // approaching at 5 km/s
        50.0,                   // fuel
        100.0,                  // max fuel
    );
    assert_eq!(response, "maneuver", "Very close approach should trigger maneuver, got {response}");
    assert!(tca > 0.0, "TCA should be positive for converging objects, got {tca}");
}

#[test]
fn full_conjunction_response_distant_object() {
    // Threat very far away → nominal
    let (response, _) = integration::full_conjunction_response(
        (7000.0, 0.0, 0.0),
        (7500.0, 500.0, 500.0),  // ~700km away
        (0.0, 0.0, 0.0),         // stationary relative
        50.0,
        100.0,
    );
    assert_eq!(response, "nominal", "Distant object should be nominal, got {response}");
}
