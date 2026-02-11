#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Shipment {
    pub id: String,
    pub lane: String,
    pub units: u32,
    pub priority: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FulfillmentWindow {
    pub id: String,
    pub start_minute: u32,
    pub end_minute: u32,
    pub capacity: u32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Incident {
    pub id: String,
    pub severity: u8,
    pub domain: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Zone {
    pub id: String,
    pub temp_min_c: f64,
    pub temp_max_c: f64,
    pub capacity: u32,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Copy)]
pub enum ShipmentState {
    Pending,
    Queued,
    Allocated,
    InTransit,
    Delivered,
    Held,
    Rejected,
}

#[derive(Clone, Debug, PartialEq)]
pub struct TransitLeg {
    pub from_hub: String,
    pub to_hub: String,
    pub duration_minutes: u32,
    pub ambient_temp_c: f64,
}
