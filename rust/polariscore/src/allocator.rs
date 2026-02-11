use crate::models::{FulfillmentWindow, Incident, Shipment, Zone};
use crate::policy::compound_risk;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Allocation {
    pub shipment_id: String,
    pub window_id: String,
    pub units: u32,
}

pub fn allocate_shipments(mut shipments: Vec<Shipment>, windows: &[FulfillmentWindow]) -> Vec<Allocation> {
    shipments.sort_by_key(|item| (u8::MAX - item.priority, item.id.clone()));

    let mut capacities: Vec<(String, u32)> = windows
        .iter()
        .map(|window| (window.id.clone(), window.capacity))
        .collect();

    let mut allocations = Vec::new();

    for shipment in shipments {
        let mut remaining = shipment.units;
        for (window_id, capacity) in capacities.iter_mut() {
            if remaining == 0 {
                break;
            }
            if *capacity == 0 {
                continue;
            }
            let assigned = remaining.min(*capacity);
            *capacity -= assigned;
            remaining -= assigned;
            allocations.push(Allocation {
                shipment_id: shipment.id.clone(),
                window_id: window_id.clone(),
                units: assigned,
            });
        }
    }

    allocations
}

pub fn unallocated_units(shipments: &[Shipment], allocations: &[Allocation]) -> u32 {
    let requested: u32 = shipments.iter().map(|item| item.units).sum();
    let assigned: u32 = allocations.iter().map(|item| item.units).sum();
    requested.saturating_sub(assigned)
}

pub fn allocate_to_zones(
    shipments: &[Shipment],
    zones: &[Zone],
    required_temp_c: f64,
) -> Vec<Allocation> {
    let mut eligible: Vec<&Zone> = zones
        .iter()
        .filter(|z| z.temp_min_c <= required_temp_c && required_temp_c <= z.temp_max_c)
        .collect();
    eligible.sort_by(|a, b| {
        let a_dist = ((a.temp_min_c + a.temp_max_c) / 2.0 - required_temp_c).abs();
        let b_dist = ((b.temp_min_c + b.temp_max_c) / 2.0 - required_temp_c).abs();
        a_dist
            .partial_cmp(&b_dist)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.id.cmp(&b.id))
    });

    let mut capacities: Vec<(String, u32)> = eligible
        .iter()
        .map(|z| (z.id.clone(), z.capacity))
        .collect();

    let mut sorted = shipments.to_vec();
    sorted.sort_by_key(|s| (u8::MAX - s.priority, s.id.clone()));

    let mut allocations = Vec::new();
    for shipment in &sorted {
        let mut remaining = shipment.units;
        for (zone_id, cap) in capacities.iter_mut() {
            if remaining == 0 {
                break;
            }
            if *cap == 0 {
                continue;
            }
            let assigned = remaining.min(*cap);
            *cap -= assigned;
            remaining -= assigned;
            allocations.push(Allocation {
                shipment_id: shipment.id.clone(),
                window_id: zone_id.clone(),
                units: assigned,
            });
        }
    }
    allocations
}

pub fn reallocate_on_overflow(
    shipments: &[Shipment],
    windows: &[FulfillmentWindow],
    overflow_window_id: &str,
) -> Vec<Allocation> {
    let non_overflow: Vec<&FulfillmentWindow> = windows
        .iter()
        .filter(|w| w.id != overflow_window_id)
        .collect();

    if non_overflow.is_empty() {
        return Vec::new();
    }

    let mut capacities: Vec<(String, u32, u32)> = non_overflow
        .iter()
        .map(|w| (w.id.clone(), w.capacity, w.start_minute))
        .collect();
    capacities.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let mut sorted = shipments.to_vec();
    sorted.sort_by_key(|s| (u8::MAX - s.priority, s.id.clone()));

    let mut allocations = Vec::new();
    for shipment in &sorted {
        let mut remaining = shipment.units;
        for (wid, cap, _start) in capacities.iter_mut() {
            if remaining == 0 {
                break;
            }
            if *cap == 0 {
                continue;
            }
            let assigned = remaining.min(*cap);
            *cap -= assigned;
            remaining -= assigned;
            allocations.push(Allocation {
                shipment_id: shipment.id.clone(),
                window_id: wid.clone(),
                units: assigned,
            });
        }
    }
    allocations
}

pub fn risk_adjusted_allocation(
    shipments: &[Shipment],
    zones: &[Zone],
    incidents: &[Incident],
    temperature_c: f64,
    required_temp_c: f64,
) -> Vec<Allocation> {
    let risk = compound_risk(shipments, incidents, temperature_c);

    let mut eligible: Vec<&Zone> = zones
        .iter()
        .filter(|z| z.temp_min_c <= required_temp_c && required_temp_c <= z.temp_max_c)
        .collect();

    if risk > 50.0 {
        eligible.sort_by(|a, b| b.capacity.cmp(&a.capacity).then_with(|| a.id.cmp(&b.id)));
    } else {
        eligible.sort_by(|a, b| {
            let a_dist = ((a.temp_min_c + a.temp_max_c) / 2.0 - required_temp_c).abs();
            let b_dist = ((b.temp_min_c + b.temp_max_c) / 2.0 - required_temp_c).abs();
            a_dist
                .partial_cmp(&b_dist)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.id.cmp(&b.id))
        });
    }

    let mut capacities: Vec<(String, u32)> =
        eligible.iter().map(|z| (z.id.clone(), z.capacity)).collect();

    let mut sorted = shipments.to_vec();
    sorted.sort_by_key(|s| (u8::MAX - s.priority, s.id.clone()));

    let mut allocations = Vec::new();
    for shipment in &sorted {
        let mut remaining = shipment.units;
        for (zone_id, cap) in capacities.iter_mut() {
            if remaining == 0 {
                break;
            }
            if *cap == 0 {
                continue;
            }
            let assigned = remaining.min(*cap);
            *cap -= assigned;
            remaining -= assigned;
            allocations.push(Allocation {
                shipment_id: shipment.id.clone(),
                window_id: zone_id.clone(),
                units: assigned,
            });
        }
    }
    allocations
}
