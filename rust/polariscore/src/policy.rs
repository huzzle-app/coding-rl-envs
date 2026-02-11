use crate::models::{Incident, Shipment};

pub fn risk_score(shipments: &[Shipment], incidents: &[Incident], temperature_c: f64) -> f64 {
    let load_component: f64 = shipments.iter().map(|item| item.units as f64 * item.priority as f64).sum::<f64>() / 120.0;
    let incident_component: f64 = incidents.iter().map(|item| item.severity as f64 * 0.42).sum();
    let thermal_component = if !(-10.0..=30.0).contains(&temperature_c) { 18.0 } else { 0.0 };

    (load_component + incident_component + thermal_component).min(100.0)
}

pub fn requires_hold(score: f64, comms_degraded: bool) -> bool {
    
    score > 66.0 || (comms_degraded && score > 50.0)
}

pub fn compliance_tier(score: f64) -> &'static str {

    if score >= 85.0 {
        "board-review"
    } else if score >= 55.0 {
        "ops-review"
    } else {
        "auto"
    }
}

pub fn compound_risk(shipments: &[Shipment], incidents: &[Incident], temperature_c: f64) -> f64 {
    let base = risk_score(shipments, incidents, temperature_c);

    let mut domain_counts: std::collections::HashMap<&str, usize> =
        std::collections::HashMap::new();
    for inc in incidents {
        *domain_counts.entry(inc.domain.as_str()).or_insert(0) += 1;
    }

    let correlation_factor: f64 = domain_counts
        .values()
        .filter(|&&count| count > 1)
        .map(|&count| count as f64 * 1.5)
        .sum::<f64>();

    (base + correlation_factor).min(100.0)
}

pub fn escalation_level(score: f64, incident_count: usize, is_weekend: bool) -> u8 {
    let base_level: u8 = if score >= 85.0 {
        3
    } else if score >= 55.0 {
        2
    } else if score >= 25.0 {
        1
    } else {
        0
    };

    let incident_boost: u8 = if incident_count > 5 {
        2
    } else if incident_count > 2 {
        1
    } else {
        0
    };

    let total_boost = if is_weekend {
        incident_boost * 2 + 1
    } else {
        incident_boost + 1
    };

    (base_level + total_boost).min(5)
}

pub fn aggregate_risk_by_volume(
    shipment_groups: &[Vec<Shipment>],
    incidents: &[Incident],
    temperature_c: f64,
) -> f64 {
    if shipment_groups.is_empty() {
        return 0.0;
    }

    let scores: Vec<(f64, u32)> = shipment_groups
        .iter()
        .map(|group| {
            let score = risk_score(group, incidents, temperature_c);
            let total_units: u32 = group.iter().map(|s| s.units).sum();
            (score, total_units)
        })
        .collect();

    let sum_scores: f64 = scores.iter().map(|(s, _)| *s).sum();
    sum_scores / scores.len() as f64
}
