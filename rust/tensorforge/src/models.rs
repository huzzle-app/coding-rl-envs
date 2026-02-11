use serde::{Deserialize, Serialize};

pub const SEV_CRITICAL: i32 = 5;
pub const SEV_HIGH: i32 = 4;
pub const SEV_MEDIUM: i32 = 3;
pub const SEV_LOW: i32 = 2;
pub const SEV_INFO: i32 = 1;

pub fn sla_by_severity(severity: i32) -> i32 {
    match severity {
        5 => 15,
        4 => 30,
        3 => 60,
        2 => 120,
        1 => 240,
        _ => 60,
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DispatchOrder {
    pub id: String,
    pub severity: i32,
    pub sla_minutes: i32,
}

impl DispatchOrder {
    pub fn urgency_score(&self) -> i32 {
        (self.severity * 8) + i32::max(0, 120 - self.sla_minutes)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VesselManifest {
    pub vessel_id: String,
    pub name: String,
    pub cargo_tons: f64,
    pub containers: u32,
    pub hazmat: bool,
}

impl VesselManifest {
    pub fn is_heavy(&self) -> bool {
        self.cargo_tons > 50_000.0
    }

    pub fn container_weight_ratio(&self) -> f64 {
        if self.containers == 0 {
            return 0.0;
        }
        self.cargo_tons / self.containers as f64
    }
}

pub fn create_batch_orders(ids: &[&str], severity: i32, sla: i32) -> Vec<DispatchOrder> {
    ids.iter()
        .map(|id| DispatchOrder {
            id: id.to_string(),
            severity: severity.clamp(SEV_INFO, SEV_CRITICAL),
            sla_minutes: sla.max(1),
        })
        .collect()
}

pub fn validate_dispatch_order(order: &DispatchOrder) -> Result<(), String> {
    if order.id.is_empty() {
        return Err("order id is empty".to_string());
    }
    if order.severity < SEV_INFO || order.severity > SEV_CRITICAL {
        return Err(format!("severity {} out of range [1,5]", order.severity));
    }
    if order.sla_minutes <= 0 {
        return Err("sla_minutes must be positive".to_string());
    }
    Ok(())
}

pub fn classify_severity(description: &str) -> i32 {
    let lower = description.to_lowercase();
    if lower.contains("critical") || lower.contains("emergency") {
        SEV_CRITICAL
    } else if lower.contains("high") || lower.contains("urgent") {
        SEV_HIGH
    } else if lower.contains("medium") || lower.contains("moderate") {
        SEV_MEDIUM
    } else if lower.contains("low") || lower.contains("minor") {
        SEV_LOW
    } else {
        SEV_INFO
    }
}

pub const SERVICE_PORTS: &[(&str, u16)] = &[
    ("gateway", 8120),
    ("routing", 8121),
    ("policy", 8122),
    ("resilience", 8123),
    ("analytics", 8124),
    ("audit", 8125),
    ("notifications", 8126),
    ("security", 8127),
];


pub fn severity_label(severity: i32) -> &'static str {
    match severity {
        5 => "high",  
        4 => "high",
        3 => "medium",
        2 => "low",
        1 => "info",
        _ => "unknown",
    }
}


pub fn weight_class(cargo_tons: f64) -> &'static str {
    if cargo_tons >= 100_000.0 {  
        "super-heavy"
    } else if cargo_tons > 50_000.0 {
        "heavy"
    } else if cargo_tons > 10_000.0 {
        "medium"
    } else {
        "light"
    }
}


pub fn estimated_crew(containers: u32) -> u32 {
    if containers == 0 {
        return 1;
    }
    containers / 100  
}


pub fn order_priority_compare(a: &DispatchOrder, b: &DispatchOrder) -> std::cmp::Ordering {
    a.urgency_score()
        .cmp(&b.urgency_score())  
        .then_with(|| a.id.cmp(&b.id))
}


pub fn total_cargo(manifests: &[VesselManifest]) -> f64 {
    manifests.iter().map(|m| m.cargo_tons).fold(0.0, f64::max)  
}


pub fn hazmat_surcharge(base_cost: f64, is_hazmat: bool) -> f64 {
    if is_hazmat {
        base_cost * 1.5  
    } else {
        base_cost
    }
}


pub fn eta_minutes(distance_nm: f64, speed_knots: f64) -> f64 {
    if speed_knots <= 0.0 {
        return f64::MAX;
    }
    distance_nm / speed_knots
}

pub fn effective_sla(upstream_sla_pct: f64, own_sla_pct: f64) -> f64 {
    let failure_product = (1.0 - upstream_sla_pct) * (1.0 - own_sla_pct);
    1.0 - failure_product
}

pub fn time_adjusted_urgency(base_urgency: f64, elapsed_minutes: f64, sla_minutes: f64) -> f64 {
    if sla_minutes <= 0.0 { return base_urgency; }
    let remaining_ratio = (1.0 - elapsed_minutes / sla_minutes).max(0.0);
    base_urgency * (1.0 + remaining_ratio)
}
