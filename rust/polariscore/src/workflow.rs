use std::collections::HashMap;

use crate::allocator::{allocate_shipments, unallocated_units};
use crate::economics::{margin_ratio, projected_cost_cents};
use crate::models::{FulfillmentWindow, Incident, Shipment, ShipmentState};
use crate::policy::{compliance_tier, requires_hold, risk_score};

#[derive(Clone, Debug, PartialEq)]
pub struct CycleReport {
    pub allocations: usize,
    pub unallocated_units: u32,
    pub risk_score: f64,
    pub hold: bool,
    pub compliance_tier: String,
    pub projected_cost_cents: u64,
    pub margin_ratio: f64,
    pub selected_hub: String,
}

pub fn orchestrate_cycle(
    shipments: Vec<Shipment>,
    windows: &[FulfillmentWindow],
    incidents: &[Incident],
    temperature_c: f64,
    hubs: &HashMap<String, u32>,
) -> CycleReport {
    let allocations = allocate_shipments(shipments.clone(), windows);
    let unallocated = unallocated_units(&shipments, &allocations);
    let score = risk_score(&shipments, incidents, temperature_c);
    let hold = requires_hold(score, false);

    let projected_cost = projected_cost_cents(&shipments, 145.0, 1.08);
    let revenue = projected_cost + 75_000;

    let selected_hub = hubs
        .iter()
        .min_by_key(|(hub, latency)| (**latency, (*hub).clone()))
        .map(|(hub, _)| hub.clone())
        .unwrap_or_else(|| "fallback-hub".to_string());

    CycleReport {
        allocations: allocations.len(),
        unallocated_units: unallocated,
        risk_score: score,
        hold,
        compliance_tier: compliance_tier(score).to_string(),
        projected_cost_cents: projected_cost,
        margin_ratio: margin_ratio(revenue, projected_cost),
        selected_hub,
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct FulfillmentPlan {
    pub total_allocations: usize,
    pub total_unallocated: u32,
    pub combined_risk: f64,
    pub requires_hold: bool,
    pub total_cost_cents: u64,
    pub overall_margin: f64,
    pub primary_hub: String,
}

pub fn plan_fulfillment(
    shipment_batches: &[Vec<Shipment>],
    windows: &[FulfillmentWindow],
    incidents: &[Incident],
    temperature_c: f64,
    hubs: &HashMap<String, u32>,
) -> FulfillmentPlan {
    let mut total_allocations = 0;
    let mut total_unallocated = 0;
    let mut total_cost = 0_u64;
    let mut total_revenue = 0_u64;
    let mut risk_scores = Vec::new();

    for batch in shipment_batches {
        let allocs = allocate_shipments(batch.clone(), windows);
        total_allocations += allocs.len();
        total_unallocated += unallocated_units(batch, &allocs);

        let cost = projected_cost_cents(batch, 145.0, 1.08);
        total_cost += cost;
        total_revenue += cost + 75_000;

        let score = risk_score(batch, incidents, temperature_c);
        risk_scores.push(score);
    }

    let combined_risk = risk_scores.iter().copied().fold(0.0_f64, f64::max);

    let hold = requires_hold(combined_risk, false);

    let overall_margin = if total_cost == 0 {
        0.0
    } else {
        (total_revenue - total_cost) as f64 / total_cost as f64
    };

    let primary_hub = hubs
        .iter()
        .min_by_key(|(_, latency)| **latency)
        .map(|(hub, _)| hub.clone())
        .unwrap_or_else(|| "fallback".to_string());

    FulfillmentPlan {
        total_allocations,
        total_unallocated,
        combined_risk,
        requires_hold: hold,
        total_cost_cents: total_cost,
        overall_margin,
        primary_hub,
    }
}

#[derive(Clone, Debug)]
pub struct ShipmentStateMachine {
    pub state: ShipmentState,
    pub history: Vec<ShipmentState>,
}

impl ShipmentStateMachine {
    pub fn new() -> Self {
        ShipmentStateMachine {
            state: ShipmentState::Pending,
            history: vec![ShipmentState::Pending],
        }
    }

    pub fn transition(&mut self, new_state: ShipmentState) -> Result<(), String> {
        let valid = matches!(
            (&self.state, &new_state),
            (ShipmentState::Pending, ShipmentState::Queued)
                | (ShipmentState::Pending, ShipmentState::Rejected)
                | (ShipmentState::Queued, ShipmentState::Allocated)
                | (ShipmentState::Queued, ShipmentState::Rejected)
                | (ShipmentState::Allocated, ShipmentState::InTransit)
                | (ShipmentState::Allocated, ShipmentState::Held)
                | (ShipmentState::InTransit, ShipmentState::Delivered)
                | (ShipmentState::InTransit, ShipmentState::Held)
                | (ShipmentState::Held, ShipmentState::Queued)
                | (ShipmentState::Held, ShipmentState::Delivered)
        );

        if valid {
            self.state = new_state;
            self.history.push(new_state);
            Ok(())
        } else {
            Err(format!(
                "Invalid transition from {:?} to {:?}",
                self.state, new_state
            ))
        }
    }

    pub fn can_deliver(&self) -> bool {
        self.state == ShipmentState::Allocated || self.state == ShipmentState::InTransit
    }
}

use crate::allocator::Allocation;

pub fn multi_batch_schedule(
    batches: &[Vec<Shipment>],
    windows: &[FulfillmentWindow],
) -> Vec<(usize, Vec<Allocation>)> {
    let mut caps: Vec<(String, u32)> = windows
        .iter()
        .map(|w| (w.id.clone(), w.capacity))
        .collect();

    batches
        .iter()
        .enumerate()
        .map(|(idx, batch)| {
            let mut sorted = batch.clone();
            sorted.sort_by_key(|s| (u8::MAX - s.priority, s.id.clone()));
            let mut allocs = Vec::new();
            for s in &sorted {
                let mut rem = s.units;
                for (wid, cap) in caps.iter_mut() {
                    if rem == 0 {
                        break;
                    }
                    if *cap == 0 {
                        continue;
                    }
                    let a = rem.min(*cap);
                    *cap -= a;
                    rem -= a;
                    allocs.push(Allocation {
                        shipment_id: s.id.clone(),
                        window_id: wid.clone(),
                        units: a,
                    });
                }
            }
            (idx, allocs)
        })
        .collect()
}
