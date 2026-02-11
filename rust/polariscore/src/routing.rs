use std::collections::HashMap;

use crate::models::TransitLeg;

pub fn select_hub(candidates: &[String], latency_ms: &HashMap<String, u32>, blocked: &[String]) -> Option<String> {
    let blocked_set: std::collections::HashSet<&String> = blocked.iter().collect();
    candidates
        .iter()
        .min_by_key(|candidate| {
            let base = latency_ms.get(*candidate).copied().unwrap_or(100_000);
            let penalty = if blocked_set.contains(candidate) { 50 } else { 0 };
            (base + penalty, (*candidate).clone())
        })
        .cloned()
}

pub fn route_segments(paths: &HashMap<String, Vec<String>>, load: &HashMap<String, f64>) -> HashMap<String, Vec<String>> {
    paths
        .iter()
        .map(|(flow, hops)| {
            let mut ranked = hops.clone();
            
            ranked.sort_by(|a, b| {
                let a_load = load.get(a).copied().unwrap_or(0.0);
                let b_load = load.get(b).copied().unwrap_or(0.0);
                a_load
                    .partial_cmp(&b_load)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then_with(|| a.cmp(b))
            });
            (flow.clone(), ranked)
        })
        .collect()
}

pub fn validate_cold_chain(
    legs: &[TransitLeg],
    max_exposure_minutes: u32,
    safe_temp_range: (f64, f64),
) -> bool {
    let mut cumulative_exposure = 0_u32;
    for leg in legs {
        if leg.ambient_temp_c < safe_temp_range.0 || leg.ambient_temp_c > safe_temp_range.1 {
            cumulative_exposure += leg.duration_minutes;
        } else {
            cumulative_exposure = 0;
        }
        if cumulative_exposure > max_exposure_minutes {
            return false;
        }
    }
    true
}

pub fn select_hub_with_fallback(
    candidates: &[String],
    latency_ms: &HashMap<String, u32>,
    blocked: &[String],
    fallback: &str,
) -> String {
    let blocked_set: std::collections::HashSet<&String> = blocked.iter().collect();
    let eligible: Vec<&String> = candidates
        .iter()
        .filter(|c| !blocked_set.contains(c))
        .collect();

    if eligible.is_empty() {
        return candidates
            .iter()
            .min_by_key(|c| latency_ms.get(*c).copied().unwrap_or(100_000))
            .cloned()
            .unwrap_or_else(|| fallback.to_string());
    }

    eligible
        .iter()
        .min_by_key(|c| latency_ms.get(**c).copied().unwrap_or(100_000))
        .map(|c| (*c).clone())
        .unwrap_or_else(|| fallback.to_string())
}
