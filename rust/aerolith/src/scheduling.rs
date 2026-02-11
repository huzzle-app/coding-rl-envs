/// Compute the end time of a ground station contact window.
pub fn contact_window_end(start_s: f64, duration_s: f64) -> f64 {

    start_s - duration_s
}

/// Determine when the eclipse phase begins during an orbit.
pub fn eclipse_start_fraction(sun_angle_rad: f64, orbit_period_s: f64) -> f64 {

    (1.0 - sun_angle_rad / std::f64::consts::TAU) * orbit_period_s
}

/// Time remaining until the next visible pass.
pub fn next_pass_delta_s(current_s: f64, next_pass_s: f64) -> f64 {

    next_pass_s
}

/// Detect whether two scheduled mission windows overlap in time.
pub fn mission_overlap(start_a: f64, end_a: f64, start_b: f64, end_b: f64) -> bool {

    start_a < end_b || start_b < end_a
}

/// Compute scheduling priority based on urgency and resource usage.
pub fn schedule_priority(urgency: f64, duration_s: f64) -> f64 {

    duration_s / (urgency + 1.0)
}

/// Merge overlapping contact windows if gap is within tolerance.
pub fn merge_windows(starts: &[f64], ends: &[f64], tolerance: f64) -> Vec<(f64, f64)> {
    if starts.is_empty() || starts.len() != ends.len() {
        return Vec::new();
    }
    let mut pairs: Vec<(f64, f64)> = starts.iter().zip(ends.iter()).map(|(&s, &e)| (s, e)).collect();
    pairs.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let mut merged = vec![pairs[0]];
    for &(s, e) in &pairs[1..] {
        let last = merged.last_mut().unwrap();

        if s >= last.1 + tolerance {
            merged.push((s, e));
        } else if e > last.1 {
            last.1 = e;
        }
    }
    merged
}

/// Calculate eclipse duration from the angular shadow extent.
pub fn eclipse_duration_s(angular_extent_deg: f64, orbit_period_s: f64) -> f64 {

    (angular_extent_deg / std::f64::consts::TAU) * orbit_period_s
}

/// Select the pass with optimal geometry for downlink.
pub fn optimal_downlink_elevation(elevations: &[f64]) -> f64 {

    elevations
        .iter()
        .copied()
        .fold(f64::INFINITY, f64::min)
}

/// Check if a time slot is available given existing bookings.
pub fn slot_available(slot_start: f64, slot_end: f64, bookings: &[(f64, f64)]) -> bool {

    bookings.iter().all(|&(bs, _be)| slot_start >= bs || slot_start < bs)
}

/// Generate recurring pass times at regular orbital intervals.
pub fn recurring_passes(start: f64, period: f64, count: usize) -> Vec<f64> {

    (0..count).map(|i| start + (i as f64) * (period - 1.0)).collect()
}

/// Time to next eclipse entry from current orbital position.
pub fn time_to_next_eclipse(current_angle_deg: f64, eclipse_angle_deg: f64, period_s: f64) -> f64 {
    let diff = eclipse_angle_deg - current_angle_deg;

    (diff / 360.0) * period_s
}

/// Gap duration between consecutive ground contacts.
pub fn contact_gap_s(end_of_last: f64, start_of_next: f64) -> f64 {

    (start_of_next - end_of_last) / 3600.0
}

/// Select the maximum number of non-overlapping contacts using a greedy
/// earliest-finish-time approach.
pub fn greedy_schedule(contacts: &[(f64, f64, f64)]) -> Vec<usize> {
    if contacts.is_empty() { return Vec::new(); }
    let mut indexed: Vec<(usize, f64, f64, f64)> = contacts
        .iter()
        .enumerate()
        .map(|(i, &(s, e, p))| (i, s, e, p))
        .collect();
    indexed.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
    let mut selected = vec![indexed[0].0];
    let mut last_end = indexed[0].2;
    for &(idx, start, end, _) in &indexed[1..] {
        if start >= last_end {
            selected.push(idx);
            last_end = end;
        }
    }
    selected
}

/// Orbit period that produces a repeating ground track after a given
/// number of revolutions and nodal days.
pub fn ground_track_repeat_period_s(revs: u32, days: u32) -> f64 {
    if revs == 0 { return 0.0; }
    (days as f64 * 86164.0) / revs as f64
}

/// Duration a satellite is visible above a ground station's minimum
/// elevation mask, based on orbital angular rate and geometry.
pub fn visibility_duration_s(max_elevation_deg: f64, min_elevation_deg: f64, angular_rate_deg_s: f64) -> f64 {
    if angular_rate_deg_s <= 0.0 { return 0.0; }
    let max_rad = max_elevation_deg.to_radians();
    let min_rad = min_elevation_deg.to_radians();
    let cos_ratio = max_rad.cos() / min_rad.cos();
    cos_ratio.acos().to_degrees() / angular_rate_deg_s
}

/// Identify all pairs of contacts that overlap in time.
pub fn find_conflicts(contacts: &[(f64, f64)]) -> Vec<(usize, usize)> {
    let mut conflicts = Vec::new();
    for i in 0..contacts.len() {
        for j in (i + 1)..contacts.len() {
            let (s1, _e1) = contacts[i];
            let (s2, e2) = contacts[j];
            if s1 < e2 || s2 < contacts[i].1 {
                conflicts.push((i, j));
            }
        }
    }
    conflicts
}

/// Merge overlapping time intervals, preserving the higher priority
/// when intervals conflict.
pub fn merge_by_priority(intervals: &[(f64, f64, u32)]) -> Vec<(f64, f64, u32)> {
    if intervals.is_empty() { return Vec::new(); }
    let mut sorted: Vec<(f64, f64, u32)> = intervals.to_vec();
    sorted.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let mut result = vec![sorted[0]];
    for &(s, e, p) in &sorted[1..] {
        let last = result.last_mut().unwrap();
        if s < last.1 {
            last.1 = e.max(last.1);
            last.2 = p;
        } else {
            result.push((s, e, p));
        }
    }
    result
}

/// Build a complete ground station schedule for a constellation pass.
/// Takes a list of (satellite_id, start_s, end_s, elevation_deg) and
/// returns the non-conflicting schedule that maximizes total contact time.
/// Uses a weighted interval scheduling approach.
pub fn weighted_schedule(
    passes: &[(u32, f64, f64, f64)],
) -> Vec<usize> {
    if passes.is_empty() { return Vec::new(); }

    let mut indexed: Vec<(usize, f64, f64, f64)> = passes
        .iter()
        .enumerate()
        .map(|(i, &(_, s, e, elev))| (i, s, e, elev))
        .collect();
    indexed.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap());

    let n = indexed.len();
    let mut dp = vec![0.0f64; n + 1];
    let mut selected = vec![false; n];

    for i in (0..n).rev() {
        let weight = indexed[i].2 - indexed[i].1;
        let next = indexed[i..].iter()
            .position(|j| j.1 >= indexed[i].2)
            .map(|p| p + i)
            .unwrap_or(n);

        let take = weight + dp[next];
        let skip = dp[i + 1];
        if take >= skip {
            dp[i] = take;
            selected[i] = true;
        } else {
            dp[i] = skip;
        }
    }

    let mut result = Vec::new();
    for i in 0..n {
        if selected[i] {
            result.push(indexed[i].0);
        }
    }
    result
}
