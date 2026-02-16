"""Aerolith reward model - ultra-principal tier (8-threshold)."""

THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]

TOTAL_TESTS = 1362

def sparse_reward(pass_rate: float) -> float:
    for threshold, reward in reversed(list(zip(THRESHOLDS, REWARDS))):
        if pass_rate >= threshold:
            return reward
    return 0.0

def total_tests() -> int:
    return TOTAL_TESTS

# Bug-to-test mapping: maps each bug ID to the test function names that detect it.
# Test names are the Rust test function names (no module prefix).
# hyper_matrix_scenarios detects ALL bugs since it's an all-or-nothing monolithic test.
BUG_TEST_MAPPING = {
    # === CFG: config.rs (CFG1-CFG11) ===
    "CFG1": ["config_default_altitude", "hyper_matrix_scenarios"],  # default_orbit_altitude returns 400 not 550
    "CFG2": ["config_pool_size", "hyper_matrix_scenarios"],  # default_pool_size returns 16 not 32
    "CFG3": ["config_validate_port", "hyper_matrix_scenarios"],  # validate_config port>=0 always true for u16
    "CFG4": ["config_env_normalize", "hyper_matrix_scenarios"],  # normalize_env_name to_uppercase not to_lowercase
    "CFG5": ["hyper_matrix_scenarios"],  # constellation_size returns 12 not 24
    "CFG6": ["hyper_matrix_scenarios"],  # max_burn_duration returns 600 not 300
    "CFG7": ["hyper_matrix_scenarios"],  # parse_feature_flags splits on ; not ,
    "CFG8": ["hyper_matrix_scenarios"],  # is_operational missing "nominal" case
    "CFG9": ["hyper_matrix_scenarios"],  # config_priority production<development (reversed)
    "CFG10": ["hyper_matrix_scenarios"],  # build_connection_string port and host swapped
    "CFG11": ["hyper_matrix_scenarios"],  # heartbeat_interval_ms returns 30000 not 5000

    # === ORB: orbit.rs (ORB1-ORB14) ===
    "ORB1": ["orbit_period", "hyper_matrix_scenarios"],  # orbital_period_minutes divides by mu twice
    "ORB2": ["orbit_semi_major_axis", "hyper_matrix_scenarios"],  # semi_major_axis_km double earth radius
    "ORB3": ["hyper_matrix_scenarios"],  # time_to_node_s divides by 60 incorrectly
    "ORB4": ["hyper_matrix_scenarios"],  # ground_track_shift_deg wrong coefficient (10 vs 15.04)
    "ORB5": ["orbit_to_safety_pipeline_velocity_units", "hyper_matrix_scenarios"],  # relative_velocity uses + not -
    "ORB6": ["hyper_matrix_scenarios"],  # altitude_decay_rate_km_per_day missing negative sign
    "ORB7": ["orbit_energy_negative", "hyper_matrix_scenarios"],  # orbit_energy missing negative sign
    "ORB8": ["orbit_apoapsis", "hyper_matrix_scenarios"],  # apoapsis_from_elements uses - not +
    "ORB9": ["j2_raan_drift_prograde_orbit_should_be_negative", "j2_raan_drift_sun_synchronous",
             "nodal_precession_chains_raan_drift_sign", "hyper_matrix_scenarios"],  # j2_raan_drift missing negative
    "ORB10": ["mean_motion_units_are_rad_per_second", "hyper_matrix_scenarios"],  # mean_motion_rad_s /60 extra
    "ORB11": ["true_anomaly_small_eccentricity_correction"],  # true_anomaly_approx e*e not 2*e
    "ORB12": ["periapsis_velocity_circular_orbit", "periapsis_velocity_eccentric_orbit_higher_than_circular",
              "hyper_matrix_scenarios"],  # periapsis_velocity formula inverted
    "ORB13": ["ground_footprint_at_400km", "ground_footprint_increases_with_altitude",
              "hyper_matrix_scenarios"],  # ground_footprint_radius_km returns radians not km
    "ORB14": ["atmospheric_density_continuity_at_400km", "atmospheric_density_decreases_with_altitude",
              "hyper_matrix_scenarios"],  # atmospheric_density discontinuity at 400km

    # === SAF: safety.rs (SAF1-SAF14) ===
    "SAF1": ["safety_keep_out_zone_boundary", "hyper_matrix_scenarios"],  # in_keep_out_zone < not <=
    "SAF2": ["hyper_matrix_scenarios"],  # safe_separation_m returns km not meters
    "SAF3": [],  # sort_conjunctions descending not ascending (no direct test)
    "SAF4": ["safety_reentry_threshold", "hyper_matrix_scenarios"],  # is_reentry threshold 150 vs 120
    "SAF5": ["hyper_matrix_scenarios"],  # fragmentation_risk velocity comparison inverted
    "SAF6": ["safety_debris_filter", "hyper_matrix_scenarios"],  # max_debris_count doesn't filter by min_size
    "SAF7": ["hyper_matrix_scenarios"],  # is_safe_for_eva ignores debris_count
    "SAF8": ["safety_risk_matrix", "hyper_matrix_scenarios"],  # risk_matrix_score operands swapped
    "SAF9": ["miss_distance_3d_includes_z_component", "miss_distance_3d_pythagorean",
             "hyper_matrix_scenarios"],  # miss_distance_3d ignores z component
    "SAF10": ["conjunction_screening_uses_rss_of_sigmas"],  # conjunction_screening sum instead of RSS
    "SAF11": ["time_to_closest_approach_positive_for_converging"],  # time_to_closest_approach missing negation
    "SAF12": ["cumulative_collision_prob_independent_events", "cumulative_collision_prob_single_event",
              "hyper_matrix_scenarios"],  # cumulative_collision_prob *= p not *= (1-p)
    "SAF13": ["debris_cloud_expands_over_time"],  # debris_cloud_radius_km wrong /1000
    "SAF14": ["prioritize_threats_highest_first", "hyper_matrix_scenarios"],  # prioritize_threats ascending not desc

    # === SEQ: sequencing.rs (SEQ1-SEQ13) ===
    "SEQ1": ["seq_priority_sort_descending"],  # priority_sort ascending not descending
    "SEQ2": ["seq_dedup_keeps_first"],  # deduplicate_commands keeps last not first
    "SEQ3": ["seq_batch_size"],  # batch_commands batch_size - 1
    "SEQ4": ["seq_window_inclusive", "hyper_matrix_scenarios"],  # command_in_window < not <=
    "SEQ5": [],  # merge_queues >= wrong for ascending merge
    "SEQ6": [],  # is_critical_sequence any instead of all
    "SEQ7": ["hyper_matrix_scenarios"],  # execution_gap subtraction order wrong
    "SEQ8": [],  # sequence_checksum skips first byte
    "SEQ9": [],  # reorder_by_dependency descending not ascending
    "SEQ10": ["hyper_matrix_scenarios"],  # command_timeout_ms ignores attempts
    "SEQ11": ["seq_validate_epoch_boundary", "hyper_matrix_scenarios"],  # validate_epoch < not <=
    "SEQ12": ["topological_sort_detects_cycle", "topological_sort_linear_chain",
              "build_execution_plan_handles_cycle"],  # topological_sort always returns Some
    "SEQ13": ["coalesce_commands_includes_last_group", "coalesce_commands_single_type"],  # missing final group push

    # === ROU: routing.rs (ROU1-ROU17) ===
    "ROU1": ["routing_link_margin", "hyper_matrix_scenarios"],  # link_margin_db subtraction reversed
    "ROU2": [],  # free_space_loss missing 20.0 multiplier
    "ROU3": ["routing_ground_visible_boundary", "hyper_matrix_scenarios"],  # ground_station_visible > not >=
    "ROU4": ["routing_best_station", "hyper_matrix_scenarios"],  # best_ground_station max not min
    "ROU5": [],  # slant_range_km cos not sin
    "ROU6": [],  # contact_duration_s multiplication not division
    "ROU7": [],  # handover_station always returns first
    "ROU8": ["hyper_matrix_scenarios"],  # link_budget_db adds losses not subtracts
    "ROU9": ["routing_normalize_azimuth_wrap", "hyper_matrix_scenarios"],  # normalize_azimuth % 180 not 360
    "ROU10": ["routing_line_of_sight", "hyper_matrix_scenarios"],  # is_line_of_sight <= not >
    "ROU11": ["hyper_matrix_scenarios"],  # route_failover doesn't filter primary
    "ROU12": ["propagation_delay_geo_orbit"],  # propagation_delay_ms c in m/s not km/s
    "ROU13": ["multi_hop_latency_includes_all_processing"],  # multi_hop_latency_ms adds processing once
    "ROU14": ["atmospheric_attenuation_decreases_with_elevation"],  # atmospheric_attenuation cos not sin
    "ROU15": ["eirp_subtracts_cable_loss", "hyper_matrix_scenarios"],  # eirp_dbw adds cable_loss not subtracts
    "ROU16": ["carrier_to_noise_includes_g_over_t"],  # carrier_to_noise subtracts g_over_t
    "ROU17": ["select_best_antenna_by_gain", "hyper_matrix_scenarios"],  # select_best_antenna min not max

    # === SCH: scheduling.rs (SCH1-SCH11) ===
    "SCH1": ["sched_contact_window", "scheduling_power_chain", "hyper_matrix_scenarios"],  # contact_window_end - not +
    "SCH2": ["sched_next_pass_delta", "hyper_matrix_scenarios"],  # next_pass_delta_s doesn't subtract current
    "SCH3": ["sched_mission_overlap_check", "hyper_matrix_scenarios"],  # mission_overlap || not &&
    "SCH4": [],  # schedule_priority formula inverted
    "SCH5": ["sched_optimal_downlink", "hyper_matrix_scenarios"],  # optimal_downlink_elevation min not max
    "SCH6": [],  # slot_available always returns true
    "SCH7": ["hyper_matrix_scenarios"],  # recurring_passes period - 1.0
    "SCH8": ["sched_contact_gap", "hyper_matrix_scenarios"],  # contact_gap_s divides by 3600
    "SCH9": ["greedy_schedule_optimal_selection"],  # greedy_schedule sorts by start not end
    "SCH10": ["visibility_duration_full_arc"],  # visibility_duration_s missing 2.0* for full arc
    "SCH11": ["find_conflicts_correct_overlap"],  # find_conflicts wrong overlap check

    # === POW: power.rs (POW1-POW15) ===
    "POW1": ["power_solar_output", "scheduling_power_chain", "hyper_matrix_scenarios"],  # solar_panel_output missing deg-to-rad
    "POW2": ["power_battery_soc_calc", "scheduling_power_chain", "hyper_matrix_scenarios"],  # battery_soc division inverted
    "POW3": ["power_budget", "scheduling_power_chain", "hyper_matrix_scenarios"],  # power_budget_watts + not -
    "POW4": ["power_depth_of_discharge", "hyper_matrix_scenarios"],  # depth_of_discharge + not -
    "POW5": ["hyper_matrix_scenarios"],  # battery_health threshold 500 vs 1000
    "POW6": [],  # eclipse_drain_wh uses 1.0 - eclipse_fraction
    "POW7": ["hyper_matrix_scenarios"],  # solar_flux_w_per_m2 single div not squared
    "POW8": ["power_mode_thresholds", "auth_then_scheduling_integration",
             "hyper_matrix_scenarios"],  # power_mode thresholds wrong order
    "POW9": [],  # panel_degradation positive exponent
    "POW10": ["hyper_matrix_scenarios"],  # total_power_watts - not +
    "POW11": ["thermal_equilibrium_uses_fourth_root", "hyper_matrix_scenarios"],  # thermal_equilibrium .cbrt not .powf(0.25)
    "POW12": ["eclipse_battery_capacity_accounts_for_dod"],  # eclipse_battery_capacity * dod not / dod
    "POW13": ["solar_array_area_cosine_law"],  # solar_array_area sin not cos
    "POW14": ["power_margin_positive_when_excess", "power_margin_negative_when_deficit",
              "hyper_matrix_scenarios"],  # power_margin divides by available not required
    "POW15": ["end_of_life_power_3_percent_degradation", "end_of_life_power_zero_years_equals_bol",
              "end_of_life_power_small_degradation_bounds", "hyper_matrix_scenarios"],  # end_of_life missing /100

    # === TEL: telemetry.rs (TEL1-TEL13) ===
    "TEL1": ["telem_error_rate_calc", "hyper_matrix_scenarios"],  # error_rate wrong denominator
    "TEL2": ["hyper_matrix_scenarios"],  # throughput subtraction not division
    "TEL3": ["hyper_matrix_scenarios"],  # uptime_percentage divides by downtime
    "TEL4": ["hyper_matrix_scenarios"],  # format_metric , not :
    "TEL5": ["telem_should_alert_check", "hyper_matrix_scenarios"],  # should_alert < not >
    "TEL6": ["hyper_matrix_scenarios"],  # aggregate_mean missing division
    "TEL7": ["hyper_matrix_scenarios"],  # jitter_score missing .abs()
    "TEL8": ["hyper_matrix_scenarios"],  # staleness_s returns now not difference
    "TEL9": ["telem_summary_units", "hyper_matrix_scenarios"],  # telemetry_summary missing % and temp unit
    "TEL10": ["ema_responds_to_recent_values", "ema_low_alpha_smooths"],  # ema alpha weights swapped
    "TEL11": ["percentile_median_of_sorted", "percentile_interpolation"],  # percentile interpolation swapped
    "TEL12": ["rate_of_change_positive_slope"],  # rate_of_change subtraction order wrong
    "TEL13": ["composite_health_weighted_correctly"],  # composite_health_score missing weight in sum

    # === RES: resilience.rs (RES1-RES15) ===
    "RES1": ["hyper_matrix_scenarios"],  # checkpoint_interval_s divides by 2
    "RES2": ["resil_degradation", "hyper_matrix_scenarios"],  # degradation_level levels reversed
    "RES3": ["hyper_matrix_scenarios"],  # bulkhead_remaining returns used not remaining
    "RES4": ["resil_cascade_any", "hyper_matrix_scenarios"],  # cascade_failure_check all not any
    "RES5": ["hyper_matrix_scenarios"],  # recovery_rate division inverted
    "RES6": ["resil_retry_exponential", "hyper_matrix_scenarios"],  # retry_delay_ms linear not exponential
    "RES7": ["resil_should_trip_boundary", "hyper_matrix_scenarios"],  # should_trip > not >=
    "RES8": ["hyper_matrix_scenarios"],  # half_open_allowed wrong comparison
    "RES9": ["hyper_matrix_scenarios"],  # in_failure_window > not <=
    "RES10": ["hyper_matrix_scenarios"],  # state_duration_s missing /1000
    "RES11": ["resil_fallback", "hyper_matrix_scenarios"],  # fallback_value values swapped
    "RES12": ["hyper_matrix_scenarios"],  # circuit_should_reset !is_open not is_open
    "RES13": ["circuit_breaker_half_open_success_closes", "circuit_breaker_half_open_failure_opens",
              "circuit_breaker_full_lifecycle", "hyper_matrix_scenarios"],  # circuit_breaker_next_state half_open swapped
    "RES14": ["health_check_quorum_exact_match", "hyper_matrix_scenarios"],  # health_check_quorum > not >=
    "RES15": ["retry_budget_allows_when_error_rate_high", "retry_budget_blocks_when_healthy"],  # retry_budget inverted

    # === AUT: auth.rs (AUT1-AUT16) ===
    "AUT1": ["auth_token_format", "hyper_matrix_scenarios"],  # validate_token_format len>=0 always true
    "AUT2": ["auth_password_strength_boundaries", "hyper_matrix_scenarios"],  # password_strength > not >=
    "AUT3": ["auth_mask", "hyper_matrix_scenarios"],  # mask_sensitive reveals first 4 not last 4
    "AUT4": ["auth_rate_limit", "hyper_matrix_scenarios"],  # rate_limit_key doesn't include IP
    "AUT5": ["hyper_matrix_scenarios"],  # session_expired subtraction not addition
    "AUT6": ["hyper_matrix_scenarios"],  # sanitize_header doesn't remove \r
    "AUT7": ["auth_permissions", "hyper_matrix_scenarios"],  # permission_check any not all
    "AUT8": ["hyper_matrix_scenarios"],  # ip_in_allowlist starts_with not ==
    "AUT9": ["hyper_matrix_scenarios"],  # hash_credential password:salt order wrong
    "AUT10": ["hyper_matrix_scenarios"],  # token_expiry subtraction not addition
    "AUT11": ["hyper_matrix_scenarios"],  # scope_includes contains not ==
    "AUT12": ["hyper_matrix_scenarios"],  # role_hierarchy hierarchy inverted
    "AUT13": ["validate_claims_checks_not_before", "validate_claims_happy_path",
              "hyper_matrix_scenarios"],  # validate_claims ignores nbf
    "AUT14": ["mfa_two_of_three_required", "mfa_exact_match", "hyper_matrix_scenarios"],  # mfa_check > not >=
    "AUT15": ["rotate_key_advances", "hyper_matrix_scenarios"],  # rotate_key_index missing +1
    "AUT16": ["path_pattern_prefix_only"],  # path_matches_pattern contains not starts_with

    # === EVT: events.rs (EVT1-EVT6) ===
    "EVT1": ["events_sort_ascending", "event_sort_then_dedup_consistency",
             "hyper_matrix_scenarios"],  # sort_events_by_time descending not ascending
    "EVT2": ["events_dedup_earliest", "event_sort_then_dedup_consistency",
             "hyper_matrix_scenarios"],  # dedup_events iterates in reverse
    "EVT3": ["events_filter_window_inclusive", "hyper_matrix_scenarios"],  # filter_time_window > not >=
    "EVT4": ["events_detect_gaps_threshold", "hyper_matrix_scenarios"],  # detect_gaps >= not >
    "EVT5": ["causal_ordering_same_timestamp_violation", "causal_ordering_valid_chain"],  # is_causally_ordered missing >=
    "EVT6": ["dedup_within_window_allows_after_window"],  # dedup_within_window > not >=

    # === CON: concurrency.rs (CON1) ===
    "CON1": ["command_queue_priority_ordering"],  # CommandQueue dequeue removes index 0 not highest prio

    # === INT: integration.rs (INT1-INT7) ===
    # Integration bugs cascade from upstream module bugs
    "INT1": ["conjunction_pipeline_unit_consistency"],  # conjunction_assessment_pipeline chains orbit+safety bugs
    "INT2": ["power_aware_contact_rejects_low_power"],  # power_aware_contact chains power bugs
    "INT3": ["orbit_maintenance_small_correction_valid"],  # orbit_maintenance chains orbit bugs
    "INT4": ["telemetry_mode_healthy_satellite"],  # telemetry_mode chains telemetry+power bugs
    "INT5": ["should_execute_pass_all_conditions_met", "should_execute_pass_low_power_blocks"],  # chains routing+power+auth
    "INT6": ["plan_downlink_auth_for_operator"],  # chains routing+auth bugs
    "INT7": ["predict_orbit_evolution_altitude_decreases", "predict_orbit_evolution_period_realistic",
             "predict_orbit_evolution_raan_shift_nonzero"],  # chains orbit bugs
}

# Bug dependency graph: a bug can only be considered "fixed" after its prerequisites are fixed.
# Maps bug_id -> list of prerequisite bug_ids.
BUG_DEPENDENCIES = {
    # Config bugs are foundational - many downstream bugs depend on correct config
    # No dependencies for CFG1-CFG11 (they are root bugs)

    # Orbit bugs: ORB2 (semi_major_axis) is prerequisite for several
    "ORB1": ["ORB2"],  # orbital_period depends on correct semi_major_axis
    "ORB3": ["ORB1"],  # time_to_node depends on correct period
    "ORB9": ["ORB2"],  # j2_raan_drift depends on semi_major_axis
    "ORB10": ["ORB2"],  # mean_motion depends on semi_major_axis
    "ORB12": ["ORB2", "ORB10"],  # periapsis_velocity depends on sma and mean_motion
    "ORB13": ["ORB2"],  # ground_footprint depends on semi_major_axis

    # Safety bugs depend on orbit computations
    "SAF2": ["ORB5"],  # safe_separation uses relative velocity
    "SAF9": [],  # miss_distance_3d is independent
    "SAF10": ["SAF9"],  # conjunction_screening depends on miss_distance
    "SAF11": ["SAF9"],  # time_to_closest_approach depends on miss_distance
    "SAF14": ["SAF12"],  # prioritize_threats uses collision probability

    # Sequencing: topological sort is prerequisite for execution plans
    "SEQ12": [],  # topological_sort is independent
    "SEQ13": [],  # coalesce is independent

    # Routing: link margin is foundational
    "ROU8": ["ROU1"],  # link_budget depends on link_margin
    "ROU13": ["ROU12"],  # multi_hop depends on propagation_delay
    "ROU15": ["ROU1"],  # eirp feeds into link budget
    "ROU16": ["ROU15"],  # carrier_to_noise depends on eirp
    "ROU17": ["ROU1"],  # select_best_antenna uses link margin logic

    # Scheduling depends on orbit and routing
    "SCH9": ["SCH1"],  # greedy_schedule uses contact windows
    "SCH10": ["ORB2"],  # visibility depends on orbital parameters
    "SCH11": ["SCH1"],  # find_conflicts uses contact windows

    # Power: solar output is foundational
    "POW3": ["POW1", "POW2"],  # power_budget depends on solar output and battery
    "POW8": ["POW2"],  # power_mode depends on battery SOC
    "POW11": ["POW1"],  # thermal equilibrium depends on solar flux
    "POW12": ["POW4"],  # eclipse_battery depends on depth_of_discharge
    "POW13": ["POW1"],  # solar_array depends on solar output
    "POW14": ["POW3"],  # power_margin depends on power_budget
    "POW15": ["POW1"],  # end_of_life depends on initial power

    # Telemetry: basic metrics are foundational
    "TEL9": ["TEL1", "TEL3"],  # summary depends on error_rate and uptime
    "TEL13": ["TEL6"],  # composite_health depends on aggregate_mean

    # Resilience: circuit breaker state machine has internal dependencies
    "RES13": ["RES7"],  # circuit_breaker_next_state depends on should_trip
    "RES14": ["RES4"],  # health_check_quorum relates to cascade_failure_check
    "RES15": ["RES5"],  # retry_budget depends on recovery_rate

    # Auth: token format is foundational
    "AUT5": ["AUT10"],  # session_expired depends on token_expiry logic
    "AUT7": ["AUT11"],  # permission_check depends on scope_includes
    "AUT13": ["AUT1"],  # validate_claims depends on token validation
    "AUT14": ["AUT1"],  # mfa_check depends on token validation
    "AUT16": ["AUT11"],  # path_matches depends on scope logic

    # Events: sort is foundational for dedup and filtering
    "EVT2": ["EVT1"],  # dedup depends on correct sort order
    "EVT3": ["EVT1"],  # filter depends on correct sort order
    "EVT5": ["EVT1"],  # causal ordering depends on sort

    # Integration bugs depend on their upstream module bugs
    "INT1": ["ORB2", "ORB5", "SAF1", "SAF8"],  # conjunction pipeline chains orbit+safety
    "INT2": ["POW1", "POW2", "POW3"],  # power_aware_contact chains power bugs
    "INT3": ["ORB2", "ORB7"],  # orbit_maintenance chains orbit bugs
    "INT4": ["TEL5", "POW8"],  # telemetry_mode chains telemetry+power
    "INT5": ["ROU3", "ROU10", "POW8", "AUT7"],  # should_execute chains routing+power+auth
    "INT6": ["ROU4", "AUT7", "AUT12"],  # plan_downlink chains routing+auth
    "INT7": ["ORB2", "ORB9", "ORB14"],  # predict_orbit chains orbit bugs
}
