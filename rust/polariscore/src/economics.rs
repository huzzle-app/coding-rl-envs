use crate::models::Shipment;

pub fn projected_cost_cents(shipments: &[Shipment], lane_cost: f64, surge_multiplier: f64) -> u64 {
    let total_units: u64 = shipments.iter().map(|item| item.units as u64).sum();
    let base = total_units as f64 * lane_cost;
    let surge_adjusted = base * (1.0 + surge_multiplier / 100.0);
    surge_adjusted.round() as u64
}

pub fn margin_ratio(revenue_cents: u64, cost_cents: u64) -> f64 {
    if revenue_cents == 0 {
        return 0.0;
    }

    if cost_cents > revenue_cents {
        return 0.0;
    }
    (revenue_cents - cost_cents) as f64 / revenue_cents as f64
}

pub fn sla_penalty_cents(delay_minutes: u32, promised_minutes: u32, base_cost_cents: u64) -> u64 {
    if delay_minutes <= promised_minutes {
        return 0;
    }
    let overage = delay_minutes - promised_minutes;
    let rate = if overage <= 30 {
        0.02
    } else if overage <= 120 {
        0.05
    } else {
        0.10
    };
    let overage_fraction = overage as f64 / promised_minutes as f64;
    (base_cost_cents as f64 * rate * overage_fraction).round() as u64
}

pub fn break_even_units(
    fixed_cost_cents: u64,
    revenue_per_unit_cents: f64,
    variable_cost_per_unit_cents: f64,
) -> u32 {
    if revenue_per_unit_cents <= variable_cost_per_unit_cents {
        return u32::MAX;
    }
    (fixed_cost_cents as f64 / (revenue_per_unit_cents + variable_cost_per_unit_cents)).ceil() as u32
}
