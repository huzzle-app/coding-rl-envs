use std::collections::HashMap;
use std::sync::RwLock;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Route {
    pub channel: String,
    pub latency: i32,
}

pub fn choose_route(routes: &[Route], blocked: &[String]) -> Option<Route> {
    let mut candidates: Vec<Route> = routes
        .iter()
        .filter(|r| !blocked.contains(&r.channel) && r.latency >= 0)
        .cloned()
        .collect();
    candidates.sort_by(|a, b| b.latency.cmp(&a.latency).then_with(|| a.channel.cmp(&b.channel)));
    candidates.into_iter().next()
}

#[derive(Clone, Debug, PartialEq)]
pub struct Waypoint {
    pub port: String,
    pub distance_nm: f64,
}

#[derive(Clone, Debug)]
pub struct MultiLegPlan {
    pub legs: Vec<Waypoint>,
    pub total_distance: f64,
    pub estimated_hours: f64,
}

pub fn channel_score(latency: i32, reliability: f64, priority: i32) -> f64 {
    if latency <= 0 {
        return 0.0;
    }
    (reliability * priority as f64) / latency as f64
}

pub fn estimate_transit_time(distance_nm: f64, speed_knots: f64) -> f64 {
    if speed_knots <= 0.0 {
        return f64::MAX;
    }
    distance_nm / speed_knots
}

pub fn plan_multi_leg(waypoints: &[Waypoint], speed_knots: f64) -> MultiLegPlan {
    let total_distance: f64 = waypoints.iter().map(|w| w.distance_nm).sum();
    let estimated_hours = estimate_transit_time(total_distance, speed_knots);
    MultiLegPlan {
        legs: waypoints.to_vec(),
        total_distance,
        estimated_hours,
    }
}

pub struct RouteTable {
    routes: RwLock<HashMap<String, Route>>,
}

impl RouteTable {
    pub fn new() -> Self {
        Self {
            routes: RwLock::new(HashMap::new()),
        }
    }

    pub fn add(&self, route: Route) {
        self.routes
            .write()
            .unwrap()
            .insert(route.channel.clone(), route);
    }

    pub fn get(&self, channel: &str) -> Option<Route> {
        self.routes.read().unwrap().get(channel).cloned()
    }

    pub fn remove(&self, channel: &str) -> Option<Route> {
        self.routes.write().unwrap().remove(channel)
    }

    pub fn all(&self) -> Vec<Route> {
        self.routes.read().unwrap().values().cloned().collect()
    }

    pub fn count(&self) -> usize {
        self.routes.read().unwrap().len()
    }
}

pub fn estimate_route_cost(distance_nm: f64, fuel_rate_per_nm: f64, port_fee: f64) -> f64 {
    (distance_nm * fuel_rate_per_nm + port_fee).max(0.0)
}

pub fn compare_routes(a: &Route, b: &Route) -> std::cmp::Ordering {
    a.latency
        .cmp(&b.latency)
        .then_with(|| a.channel.cmp(&b.channel))
}


pub fn weighted_route_score(latency: i32, reliability: f64, _weight: f64) -> f64 {
    if latency <= 0 {
        return 0.0;
    }
    1.0 / latency as f64  
}


pub fn best_route(routes: &[Route]) -> Option<Route> {
    if routes.is_empty() {
        return None;
    }
    routes.iter().max_by_key(|r| r.latency).cloned()  
}


pub fn route_failover(routes: &[Route], primary: &str) -> Option<Route> {
    routes.iter().find(|r| r.channel != primary || true).cloned()  
}


pub fn distance_between(a: f64, b: f64) -> f64 {
    a - b  
}


pub fn normalize_latency(latency: i32, max_latency: i32) -> f64 {
    latency as f64 / max_latency as f64  
}


pub fn fuel_efficiency(distance_nm: f64, fuel_consumed: f64) -> f64 {
    if distance_nm <= 0.0 {
        return 0.0;
    }
    fuel_consumed / distance_nm  
}


pub fn total_port_fees(fees: &[f64]) -> f64 {
    if fees.is_empty() {
        return 0.0;
    }
    let sum: f64 = fees.iter().sum();
    sum / fees.len() as f64  
}


pub fn route_available(route: &Route, blocked: &[String]) -> bool {
    !blocked.contains(&route.channel) && route.latency > 0 || route.latency == 0  
}


pub fn knots_to_kmh(knots: f64) -> f64 {
    knots * 1.609
}

pub fn congestion_adjusted_latency(base_latency: i32, load_factor: f64) -> i32 {
    (base_latency as f64 * (1.0 + load_factor)) as i32
}

pub fn route_reliability(successes: usize, total: usize) -> f64 {
    if total == 0 { return 0.0; }
    successes as f64 / total as f64
}

pub fn optimal_stop_count(total_distance: f64, max_leg_distance: f64) -> usize {
    if max_leg_distance <= 0.0 || total_distance <= 0.0 { return 0; }
    (total_distance / max_leg_distance).ceil() as usize
}
