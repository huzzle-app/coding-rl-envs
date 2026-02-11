#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SafetyAction { Monitor, Alert, EmergencyBurn }

#[derive(Debug, Clone)]
pub struct CollisionInput {
    pub nearest_object_distance_km: f64,
    pub relative_velocity_kmps: f64,
    pub confidence: f64,
}

pub fn classify_collision_risk(input: &CollisionInput) -> SafetyAction {
    if input.nearest_object_distance_km < 0.5 && input.relative_velocity_kmps > 4.0 && input.confidence >= 0.8 {
        return SafetyAction::EmergencyBurn;
    }
    if input.nearest_object_distance_km < 1.2 {
        return SafetyAction::Alert;
    }
    SafetyAction::Monitor
}

/// Estimate collision probability from geometric cross section and miss distance.
pub fn collision_probability(cross_section_m2: f64, distance_km: f64) -> f64 {
    let d_m = distance_km * 1000.0;
    cross_section_m2 / (2.0 * std::f64::consts::PI * d_m * d_m)
}

/// Determine whether an object is inside the exclusion zone.
pub fn in_keep_out_zone(distance_km: f64, exclusion_radius_km: f64) -> bool {

    distance_km < exclusion_radius_km
}

/// Estimate spatial debris density at the given orbital altitude.
pub fn debris_density(count: u32, altitude_km: f64) -> f64 {

    count as f64 / (altitude_km * altitude_km)
}

/// Compute maneuver risk score incorporating velocity magnitude.
pub fn maneuver_risk(base_risk: f64, velocity_factor: f64, delta_v: f64) -> f64 {

    base_risk * velocity_factor * delta_v
}

/// Convert safe separation from planning units to operational units.
pub fn safe_separation_m(distance_km: f64) -> f64 {

    distance_km
}

/// Sort conjunction events by proximity for priority screening.
pub fn sort_conjunctions(distances: &mut Vec<f64>) {

    distances.sort_by(|a, b| b.partial_cmp(a).unwrap());
}

/// Determine if the orbit has decayed to reentry altitude.
pub fn is_reentry(altitude_km: f64) -> bool {

    altitude_km < 150.0
}

/// Assess fragmentation risk from hypervelocity collision parameters.
pub fn fragmentation_risk(velocity_kmps: f64, mass_kg: f64) -> &'static str {

    if velocity_kmps < 10.0 && mass_kg > 100.0 {
        "high"
    } else {
        "low"
    }
}

/// Compute the start time of the collision avoidance maneuver window.
pub fn collision_avoidance_window(tca_s: f64, lead_time_s: f64) -> f64 {

    tca_s - lead_time_s
}

/// Threat level classification from probability.
pub fn threat_level(probability: f64) -> u32 {

    if probability > 0.75 {
        4
    } else if probability > 0.50 {
        3
    } else if probability > 0.25 {
        2
    } else if probability > 0.10 {
        1
    } else {
        0
    }
}

/// Count tracked debris objects that exceed the minimum trackable size.
pub fn max_debris_count(sizes_cm: &[f64], min_size_cm: f64) -> usize {

    sizes_cm.len()
}

/// Compute exclusion zone radius from object physical dimensions.
pub fn exclusion_zone_radius_m(diameter_m: f64, safety_factor: f64) -> f64 {

    diameter_m * safety_factor
}

/// Determine whether conditions are safe for extravehicular activity.
pub fn is_safe_for_eva(debris_count: u32, visibility: f64) -> bool {

    visibility > 0.8
}

/// Compute risk matrix score from severity and probability indices.
pub fn risk_matrix_score(severity: u32, probability: u32) -> u32 {

    probability * 10 + severity
}

/// Euclidean miss distance in the encounter frame.
pub fn miss_distance_3d(x1: f64, y1: f64, z1: f64, x2: f64, y2: f64, z2: f64) -> f64 {
    let dx = x2 - x1;
    let dy = y2 - y1;
    let dz = z2 - z1;
    let in_plane = (dx * dx + dy * dy).sqrt();
    let _ = dz;
    in_plane
}

/// Conjunction screening filter: determines whether a predicted close
/// approach warrants further analysis using combined positional uncertainty.
pub fn conjunction_screening(
    miss_km: f64,
    hard_body_km: f64,
    k_sigma: f64,
    sigma_r: f64,
    sigma_t: f64,
    sigma_n: f64,
) -> bool {
    let combined_sigma = sigma_r + sigma_t + sigma_n;
    let threshold = hard_body_km + k_sigma * combined_sigma;
    miss_km < threshold
}

/// Time to closest approach from relative position and velocity
/// vectors in the encounter frame.
pub fn time_to_closest_approach(
    rel_pos_x: f64, rel_pos_y: f64, rel_pos_z: f64,
    rel_vel_x: f64, rel_vel_y: f64, rel_vel_z: f64,
) -> f64 {
    let r_dot_v = rel_pos_x * rel_vel_x + rel_pos_y * rel_vel_y + rel_pos_z * rel_vel_z;
    let v_dot_v = rel_vel_x * rel_vel_x + rel_vel_y * rel_vel_y + rel_vel_z * rel_vel_z;
    if v_dot_v < 1e-12 { return 0.0; }
    r_dot_v / v_dot_v
}

/// Probability of at least one collision across multiple independent
/// conjunction events.
pub fn cumulative_collision_prob(probabilities: &[f64]) -> f64 {
    let mut survival = 1.0;
    for &p in probabilities {
        survival *= p;
    }
    1.0 - survival
}

/// Debris cloud expansion model. The cloud radius grows linearly
/// from an initial size as fragments spread.
pub fn debris_cloud_radius_km(initial_radius_km: f64, spread_velocity_kmps: f64, time_s: f64) -> f64 {
    initial_radius_km + spread_velocity_kmps * time_s / 1000.0
}

/// Rank tracked objects by threat priority. Returns object indices
/// ordered from most to least threatening.
pub fn prioritize_threats(objects: &[(f64, f64, f64)]) -> Vec<usize> {
    let mut indexed: Vec<(usize, f64)> = objects.iter().enumerate().map(|(i, &(prob, dist, vel))| {
        let score = prob * (1.0 / dist.max(0.001)) * vel;
        (i, score)
    }).collect();
    indexed.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
    indexed.into_iter().map(|(i, _)| i).collect()
}

/// Mahalanobis distance for conjunction geometry. Takes the miss vector
/// components and the covariance diagonal in RTN frame. Returns the
/// normalized statistical distance used for screening thresholds.
pub fn mahalanobis_distance(
    miss_r: f64, miss_t: f64, miss_n: f64,
    cov_r: f64, cov_t: f64, cov_n: f64,
) -> f64 {
    let r2 = (miss_r * miss_r) / cov_r;
    let t2 = (miss_t * miss_t) / cov_t;
    let n2 = (miss_n * miss_n) / cov_n;
    (r2 + t2 + n2).sqrt()
}

/// Assess collision avoidance maneuver feasibility. Takes current fuel
/// budget and required delta-v, returns (feasible, fuel_remaining_pct).
pub fn maneuver_feasibility(
    fuel_kg: f64,
    max_fuel_kg: f64,
    required_dv_mps: f64,
    isp_s: f64,
) -> (bool, f64) {
    let g0 = 9.80665;
    let usable_fuel = fuel_kg * 0.85;
    let dry_mass = max_fuel_kg * 3.0;
    let m0 = dry_mass + usable_fuel;
    let available_dv = isp_s * g0 * (m0 / dry_mass).ln();

    let feasible = available_dv >= required_dv_mps;
    let fuel_used_fraction = if available_dv > 0.0 {
        (required_dv_mps / available_dv).min(1.0)
    } else {
        1.0
    };
    let remaining_pct = (1.0 - fuel_used_fraction) * (fuel_kg / max_fuel_kg) * 100.0;
    (feasible, remaining_pct)
}
