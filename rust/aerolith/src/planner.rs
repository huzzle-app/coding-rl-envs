#[derive(Debug, Clone)]
pub struct BurnPlan {
    pub delta_v_mps: f64,
    pub burn_seconds: f64,
    pub fuel_margin_kg: f64,
}

pub fn validate_plan(plan: &BurnPlan) -> bool {
    plan.delta_v_mps > 0.0 && plan.delta_v_mps <= 120.0 && plan.burn_seconds > 0.0 && plan.fuel_margin_kg >= 5.0
}
