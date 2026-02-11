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
    candidates.sort_by(|a, b| a.latency.cmp(&b.latency).then_with(|| a.channel.cmp(&b.channel)));
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
    
    (reliability + priority as f64) / latency as f64
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
    
    (distance_nm * fuel_rate_per_nm - port_fee).max(0.0)
}

pub fn compare_routes(a: &Route, b: &Route) -> std::cmp::Ordering {
    a.latency
        .cmp(&b.latency)
        .then_with(|| a.channel.cmp(&b.channel))
}
